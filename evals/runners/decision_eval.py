"""Bid/skip decisions, scam detection and pricing, from the real bid graph stopped before the Writer.

The graph is the production bid graph recompiled from its own builder with
interrupt_before=["proposal_writer"]: intake -> (analyst | risk | fit) -> decide -> pricing (bid only).
Nothing after pricing runs and nothing is submitted.

Measures (against the dev-set gold):
- bid-or-skip precision / recall / F1 (positive class "bid"; watch counts as skip, plus a
  sensitivity where watch counts as bid);
- scam precision / recall (predicted scam = risk score above thresholds.maximum_risk_score) on the
  dev set (gold.is_scam), and separately on data/processed/k6_scam_eval.jsonl with the Risk Assessor
  alone (a one-node graph built from the same node);
- price inside gold.fair_price_band for jobs the graph decided to bid on;
- p50/p95 latency, tokens and USD per job analysed.

    python -m evals.runners.decision_eval [--persona ai_ml] [--limit 20] [--k6-limit 40]
Output: evals/results/decisions.json
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time
from collections import defaultdict

from evals.runners.common import (
    DailyLimitReached,
    Harness,
    RecordCache,
    add_common_args,
    cache_stats,
    dump,
    exhausted_models,
    gold_labelled,
    header,
    latency_stats,
    load_dev,
    load_jsonl,
    personas_arg,
    run_bid,
    sample_rows,
    set_rag_variant,
    settings_hash,
    setup,
    usage_stats,
    write_json,
)

ROOT_K6 = "data/processed/k6_scam_eval.jsonl"


def decision_record(row: dict, out: dict) -> dict:
    st = out.get("state") or {}
    d, risk, fit, price = st.get("decision"), st.get("risk_report"), st.get("fit_report"), st.get("price_quote")
    return {
        "job_id": row["job_id"], "persona": row["persona_id"], "category": row.get("category"),
        "stratum": row.get("stratum"), "status": out.get("status"), "next": out.get("next"),
        "decision": d.decision.value if d else None, "reasons": d.reasons if d else None,
        "fit_score": fit.score if fit else None, "risk_score": risk.score if risk else None,
        "risk_flags": risk.flags if risk else None, "injection_detected": risk.injection_detected if risk else None,
        "price": dump(price) if price else None, "requirements": (st.get("job_spec").requirements
                                                                  if st.get("job_spec") else None),
        "evidence_ids": [e.evidence_id for e in st.get("evidence") or []],
        "usage": out.get("usage"), "latency_s": out.get("wall_s"),
        "llm_cache_hits": out.get("llm_cache_hits", 0), "llm_calls_cold": out.get("llm_calls_cold", 0),
    }


def in_band(price: dict | None, band: dict | None) -> str:
    if not price or not band or band.get("low") is None:
        return "no_band"
    if band.get("rate_type") != price["rate_type"]:
        return "rate_type_mismatch"
    if price["amount"] < band["low"]:
        return "below"
    if price["amount"] > band["high"]:
        return "above"
    return "inside"


def score_decisions(recs: list[dict], gold: dict[str, dict], max_risk: float) -> dict:
    from evals.metrics import accuracy, macro_f1, prf

    ok = [r for r in recs if r.get("decision")]
    if not ok:
        return {"n": 0}
    y = [gold[r["job_id"]]["bid_or_skip"] for r in ok]
    pred = ["bid" if r["decision"] == "bid" else "skip" for r in ok]
    pred_w = ["bid" if r["decision"] in ("bid", "watch") else "skip" for r in ok]
    scam_y = [bool(gold[r["job_id"]].get("is_scam")) for r in ok]
    scam_p = [(r["risk_score"] or 0) > max_risk for r in ok]
    inj = [r for r in ok if gold[r["job_id"]].get("has_injection")]
    bands = defaultdict(int)
    for r in ok:
        if r["decision"] == "bid" and r.get("price"):
            bands[in_band(r["price"], gold[r["job_id"]].get("fair_price_band"))] += 1
    priced = sum(bands.values())
    return {
        "n": len(ok),
        "decision_counts": {k: sum(1 for r in ok if r["decision"] == k) for k in ("bid", "watch", "skip")},
        "gold_counts": {k: y.count(k) for k in ("bid", "skip")},
        "bid_skip": prf(y, pred, "bid") | {"accuracy": accuracy(y, pred), "macro_f1": macro_f1(y, pred)},
        "bid_skip_watch_as_bid": prf(y, pred_w, "bid") | {"accuracy": accuracy(y, pred_w)},
        "scam": prf(scam_y, scam_p, True),
        "injection_detection": {"n": len(inj), "detected": sum(1 for r in inj if r["injection_detected"]),
                                "skipped": sum(1 for r in inj if r["decision"] != "bid")},
        "price": {"n_priced": priced, "inside_band_rate": (bands["inside"] / priced) if priced else None,
                  **dict(bands)},
        "latency": latency_stats(ok),
        "usage": usage_stats(ok),
    }


async def k6_eval(h: Harness, limit: int, concurrency: int, sh: str) -> dict:
    """Risk Assessor alone on labelled K6 fake-job posts (external, out-of-domain)."""
    from langgraph.graph import END, START, StateGraph

    from agent.context import RunContext
    from agent.handoffs import Job
    from agent.llm import current_usage
    from agent.nodes.risk_assessor import risk_assessor
    from agent.settings import config
    from agent.state import BidState
    from evals.metrics import prf

    rows = load_jsonl(ROOT_K6)
    if not rows:
        return {"status": "missing", "n": 0}
    fake = sorted([r for r in rows if r["is_fake"]], key=lambda r: str(r["id"]))
    real = sorted([r for r in rows if not r["is_fake"]], key=lambda r: str(r["id"]))
    random.Random(7).shuffle(fake)
    random.Random(7).shuffle(real)
    pick = fake[: limit // 2] + real[: limit - limit // 2]
    g = StateGraph(BidState, context_schema=RunContext)
    g.add_node("risk_assessor", risk_assessor)
    g.add_edge(START, "risk_assessor")
    g.add_edge("risk_assessor", END)
    graph = g.compile()
    cache = RecordCache("decision_k6")
    max_risk = config()["thresholds"]["maximum_risk_score"]
    stop = None

    async def one(r):
        nonlocal stop
        key = cache.key("k6", r["id"], sh)
        if (rec := cache.get(key)) is not None:
            return rec
        if stop:
            return None
        ctx = h.ctx()
        stats = {"llm_cache_hits": 0, "llm_calls_cold": 0}
        t1, t2 = cache_stats.set(stats), current_usage.set(ctx.usage)
        job = Job(job_id=f"k6-{r['id']}", title=(r.get("title") or "Job post")[:200], description=r["text"][:6000],
                  source="k6")
        t0 = time.perf_counter()
        try:
            st = await graph.ainvoke({"job": job, "job_id": job.job_id, "client": {"note": "no client history (K6)"}},
                                     context=ctx)
        except DailyLimitReached as exc:
            stop = str(exc)
            return None
        except Exception as exc:  # noqa: BLE001
            return {"id": r["id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        finally:
            cache_stats.reset(t1)
            current_usage.reset(t2)
        rep = st["risk_report"]
        return cache.put(key, {"id": r["id"], "is_fake": r["is_fake"], "risk_score": rep.score, "flags": rep.flags,
                               "latency_s": round(time.perf_counter() - t0, 3), "usage": ctx.usage.as_dict(), **stats})

    sem = asyncio.Semaphore(concurrency)

    async def bounded(r):
        async with sem:  # noqa: B023 - awaited within this iteration
            return await one(r)

    recs = [x for x in await asyncio.gather(*(bounded(r) for r in pick)) if x and "error" not in x]
    errors = len([1 for r in pick]) - len(recs)
    m = prf([r["is_fake"] for r in recs], [r["risk_score"] > max_risk for r in recs], True)
    return {"status": "complete" if len(recs) == len(pick) else "partial", "n": len(recs), "n_requested": len(pick),
            "n_missing_or_error": errors, "scam": m, "latency": latency_stats(recs), "usage": usage_stats(recs),
            "stopped_early": stop,
            "note": "K6 posts have no GigSim client, so only the post text is assessed; predicted scam = risk "
                    f"score > {max_risk}"}


async def main(args) -> None:
    setup(args.gigsim)
    from agent.settings import config

    variant = set_rag_variant(args.rag_variant)
    from evals.runners.common import use_profile

    use_profile(args.profile)
    personas = personas_arg(args.persona)
    rows = sample_rows(load_dev(personas, None, args.dataset_dir, gold_labelled), args.limit)
    gold = {r["job_id"]: r["gold"] for r in rows}
    sh = settings_hash(args.profile)
    cache = RecordCache("decision_eval")
    recs, errors = [], []
    stop = None
    async with Harness() as h:
        graph = h.graph(interrupt_before=["proposal_writer"])
        for persona in personas:
            prow = [r for r in rows if r["persona_id"] == persona]
            if not prow:
                continue
            h.use_persona(persona)
            sem = asyncio.Semaphore(args.concurrency)

            async def one(r, persona=persona):
                nonlocal stop
                key = cache.key(r["job_id"], persona, sh, args.profile)
                if (rec := cache.get(key)) is not None:
                    return rec
                if stop:
                    return None
                async with sem:  # noqa: B023 - awaited within this iteration
                    if stop:
                        return None
                    try:
                        out = await run_bid(h, graph, r, persona, "dec", args.profile)
                    except DailyLimitReached as exc:
                        stop = str(exc)
                        return None
                    except Exception as exc:  # noqa: BLE001
                        errors.append({"job_id": r["job_id"], "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
                        return None
                    rec = decision_record(r, out)
                    if rec["decision"] is None:
                        errors.append({"job_id": r["job_id"], "error": f"no decision (status {rec['status']})"})
                        return None
                    print(f"  {persona} {r['job_id']}: {rec['decision']} (gold {r['gold']['bid_or_skip']}) "
                          f"fit {rec['fit_score']} risk {rec['risk_score']} {rec['latency_s']}s "
                          f"{(rec['usage'] or {}).get('tokens')} tok")
                    return cache.put(key, rec)

            recs += [x for x in await asyncio.gather(*(one(r) for r in prow)) if x]
        k6 = await k6_eval(h, args.k6_limit, args.concurrency, sh) if args.k6_limit else {"status": "not_run", "n": 0}

    max_risk = config()["thresholds"]["maximum_risk_score"]
    by_p = {p: score_decisions([r for r in recs if r["persona"] == p], gold, max_risk) for p in personas}
    by_s = defaultdict(list)
    for r in recs:
        by_s[r["stratum"]].append(r)
    payload = header("decision_eval", args, len(recs), {"rag_variant": variant, "settings_hash": sh}) | {
        "status": "complete" if len(recs) == len(rows) and k6.get("status") in ("complete", "not_run") else "partial",
        "n_requested": len(rows), "n_errors": len(errors), "errors": errors[:20],
        "rag_variant": variant, "model_profile": args.profile or config()["models"]["profile"],
        "graph": "bid_graph.build(...).builder.compile(interrupt_before=['proposal_writer'])",
        "predicted_scam_rule": f"risk_report.score > thresholds.maximum_risk_score ({max_risk})",
        "dev": score_decisions(recs, gold, max_risk),
        "dev_by_persona": by_p,
        "dev_by_stratum": {k: score_decisions(v, gold, max_risk) for k, v in sorted(by_s.items())},
        "k6_risk_assessor_only": k6,
        "stopped_early": stop, "exhausted_models": exhausted_models(),
        "records": recs,
    }
    write_json(f"decisions{args.tag}.json", payload, args.out_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--rag-variant", default=None, help="override rag.variant in-process")
    ap.add_argument("--k6-limit", type=int, default=40, help="K6 posts for the Risk Assessor eval (0 = skip)")
    from evals.runners.common import run

    run(main(ap.parse_args()))
