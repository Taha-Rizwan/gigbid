"""Proposal quality: the full bid graph run to the approval interrupt (nothing is ever submitted).

On a fixed job set (gold "bid" jobs, deterministic sample) and for each RAG variant (V0 vs the best
variant from rag_variants.json, set in-process through rag.variant):
- unsupported claims per proposal before verification (first pass) and after (final pass);
- LLM judge rubric score (the `judge` tier, prompt agent/prompts/judge_proposal.md);
- GigSim simulated outcome via POST /admin/score (replied / interview / hired = reply), on the exact
  text the dry run would send (citations stripped);
- p50/p95 latency, tokens and USD per proposal.
Proposals are also saved to evals/results/proposals_samples.jsonl (human panel, judge calibration).

    python -m evals.runners.proposal_eval [--limit 10] [--variants v0_naive,best]
Output: evals/results/proposals.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, Field

from evals.runners.common import (
    REPLY_OUTCOMES,
    RESULTS_DIR,
    DailyLimitReached,
    Harness,
    RecordCache,
    add_common_args,
    admin_score,
    anthropic_spend,
    cache_stats,
    dump,
    exhausted_models,
    gold_labelled,
    header,
    latency_stats,
    load_dev,
    personas_arg,
    run_bid,
    sample_rows,
    seed_accounts,
    set_rag_variant,
    settings_hash,
    setup,
    usage_stats,
    use_profile,
    write_json,
)


class JudgeScore(BaseModel):
    relevance: int = Field(ge=1, le=5)
    evidence: int = Field(ge=1, le=5)
    personalisation: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    professionalism: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5, description="1 (would ignore) to 5 (would definitely reply)")
    justification: str = ""


async def judge(job, letter: str, answers: list[str]) -> tuple[dict | None, dict]:
    """Rubric score from the judge tier. Returns (score, usage)."""
    from agent import llm
    from agent.nodes.common import job_text

    usage = llm.Usage()
    tok = llm.current_usage.set(usage)
    try:
        user = (f"JOB POST:\n{job_text(job)}\n\nPROPOSAL (cover letter):\n{letter}\n\nSCREENING ANSWERS:\n"
                + ("\n---\n".join(answers) if answers else "(none)"))
        s = await llm.structured("judge", JudgeScore, llm.prompt_messages("judge_proposal", user))
        return s.model_dump(), usage.as_dict()
    finally:
        llm.current_usage.reset(tok)


def best_variant(out_dir: str) -> str | None:
    p = Path(out_dir) / "rag_variants.json"
    if not p.exists():
        p = RESULTS_DIR / "rag_variants.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("best_variant")
    except (OSError, ValueError):
        return None


def proposal_record(row: dict, out: dict) -> dict:
    st = out.get("state") or {}
    d, draft, ver, comp, dry = (st.get("decision"), st.get("draft"), st.get("verification") or {},
                                st.get("compliance"), st.get("dry_run"))
    price = st.get("price_quote")
    return {
        "job_id": row["job_id"], "persona": row["persona_id"], "category": row.get("category"),
        "stratum": row.get("stratum"), "status": out.get("status"), "next": out.get("next"),
        "decision": d.decision.value if d else None, "fit_score": d.fit_score if d else None,
        "risk_score": d.risk_score if d else None,
        "has_draft": draft is not None,
        "cover_letter_with_citations": draft.cover_letter if draft else None,
        "final_cover_letter": (dry or {}).get("cover_letter"), "final_screening_answers": (dry or {}).get("screening_answers"),
        "bid_amount": price.amount if price else None, "rate_type": price.rate_type if price else None,
        "unsupported_before": ver.get("first_before"), "unsupported_after": ver.get("after"),
        "claims": ver.get("claims"), "revisions": st.get("revisions"),
        "critiques": [c.model_dump(mode="json") for c in st.get("critiques") or []],
        "compliance": dump(comp) if comp else None, "evidence_ids": draft.evidence_ids if draft else [],
        "usage": out.get("usage"), "latency_s": out.get("wall_s"),
        "llm_cache_hits": out.get("llm_cache_hits", 0), "llm_calls_cold": out.get("llm_calls_cold", 0),
    }


def summarise(recs: list[dict]) -> dict:
    from evals.metrics import bootstrap_ci, mean

    drafted = [r for r in recs if r.get("final_cover_letter")]
    scored = [r for r in drafted if r.get("gigsim")]
    judged = [r for r in drafted if r.get("judge")]
    replies = [r["gigsim"]["outcome"] in REPLY_OUTCOMES for r in scored]
    return {
        "n_attempted": len(recs), "n_proposals": len(drafted),
        "decision_counts": {k: sum(1 for r in recs if r.get("decision") == k) for k in ("bid", "watch", "skip")},
        "status_counts": {s: sum(1 for r in recs if r.get("status") == s) for s in {r.get("status") for r in recs}},
        "unsupported_before_mean": mean(r.get("unsupported_before") for r in drafted),
        "unsupported_after_mean": mean(r.get("unsupported_after") for r in drafted),
        "judge_overall_mean": mean(r["judge"]["overall"] for r in judged), "n_judged": len(judged),
        "judge_overall_ci95": bootstrap_ci([r["judge"]["overall"] for r in judged]),
        "judge_criteria_mean": {c: mean(r["judge"][c] for r in judged) for c in
                                ("relevance", "evidence", "personalisation", "clarity", "professionalism")},
        "gigsim_reply_rate": (sum(replies) / len(replies)) if replies else None, "n_scored": len(scored),
        "gigsim_reply_rate_ci95": bootstrap_ci([1.0 if x else 0.0 for x in replies]),
        "gigsim_reply_rate_over_attempted": (sum(replies) / len(recs)) if recs else None,
        "gigsim_hire_rate": (sum(r["gigsim"]["outcome"] == "hired" for r in scored) / len(scored)) if scored else None,
        "gigsim_p_reply_mean": mean(r["gigsim"].get("p_reply") for r in scored),
        "outcomes": {o: sum(1 for r in scored if r["gigsim"]["outcome"] == o)
                     for o in ("ignored", "viewed", "replied", "interview", "hired")},
        "latency": latency_stats(drafted), "usage_per_proposal": usage_stats(drafted),
        "judge_usage": usage_stats([{"usage": r["judge_usage"]} for r in judged if r.get("judge_usage")]),
    }


async def main(args) -> None:
    url = setup(args.gigsim)
    from agent.handoffs import Job  # noqa: F401
    from agent.settings import config
    from evals.runners.common import row_job

    profile = use_profile(args.profile)
    personas = personas_arg(args.persona)
    rows = sample_rows(load_dev(personas, None, args.dataset_dir, gold_labelled), args.limit,
                       where=lambda r: r["gold"].get("bid_or_skip") == "bid")
    best = best_variant(args.out_dir)
    variants = []
    for v in args.variants.split(","):
        v = best if v == "best" else v
        if v and v not in variants:
            variants.append(v)
    accounts = seed_accounts()
    cache = RecordCache("proposal_eval")
    results: dict[str, list[dict]] = {}
    errors: list[dict] = []
    stop = None
    samples = []
    async with Harness() as h:
        graph = h.graph()
        for variant in variants:
            set_rag_variant(variant)
            sh = settings_hash(profile)
            recs: list[dict] = []
            for persona in personas:
                prow = [r for r in rows if r["persona_id"] == persona]
                if not prow:
                    continue
                h.use_persona(persona)
                acct = (accounts.get(persona) or {}).get("account_id", "acct_ai")
                sem = asyncio.Semaphore(args.concurrency)

                async def one(r, persona=persona, acct=acct, variant=variant, sh=sh):
                    nonlocal stop
                    key = cache.key(r["job_id"], persona, variant, sh, profile)
                    rec = cache.get(key)
                    if rec is None:
                        if stop:
                            return None
                        async with sem:  # noqa: B023 - awaited within this iteration
                            if stop:
                                return None
                            try:
                                out = await run_bid(h, graph, r, persona, f"prop-{variant}", profile)
                            except DailyLimitReached as exc:
                                stop = str(exc)
                                return None
                            except Exception as exc:  # noqa: BLE001
                                errors.append({"job_id": r["job_id"], "variant": variant,
                                               "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
                                return None
                            rec = cache.put(key, proposal_record(r, out) | {"variant": variant, "profile": profile})
                    if rec.get("final_cover_letter") and not rec.get("gigsim"):
                        try:
                            rec["gigsim"] = await admin_score(url, r["job_id"], rec["final_cover_letter"],
                                                              rec.get("final_screening_answers") or [],
                                                              rec["bid_amount"], rec["rate_type"], acct)
                            cache.put(key, rec)
                        except Exception as exc:  # noqa: BLE001
                            errors.append({"job_id": r["job_id"], "variant": variant, "error": f"score: {exc}"})
                    if rec.get("final_cover_letter") and not rec.get("judge") and not args.no_judge:
                        try:
                            stats = {"llm_cache_hits": 0, "llm_calls_cold": 0}
                            t = cache_stats.set(stats)
                            try:
                                rec["judge"], rec["judge_usage"] = await judge(
                                    row_job(r), rec["final_cover_letter"], rec.get("final_screening_answers") or [])
                            finally:
                                cache_stats.reset(t)
                            cache.put(key, rec)
                        except DailyLimitReached as exc:
                            stop = stop or str(exc)
                        except Exception as exc:  # noqa: BLE001
                            errors.append({"job_id": r["job_id"], "variant": variant,
                                           "error": f"judge: {type(exc).__name__}: {str(exc)[:200]}"})
                    print(f"  [{variant}] {persona} {r['job_id']}: {rec.get('status')} decision {rec.get('decision')} "
                          f"unsupported {rec.get('unsupported_before')}->{rec.get('unsupported_after')} "
                          f"judge {(rec.get('judge') or {}).get('overall')} "
                          f"gigsim {(rec.get('gigsim') or {}).get('outcome')} {rec.get('latency_s')}s")
                    return rec

                recs += [x for x in await asyncio.gather(*(one(r) for r in prow)) if x]
            results[variant] = recs
            for rec in recs:
                if rec.get("final_cover_letter"):
                    samples.append({k: rec.get(k) for k in (
                        "job_id", "persona", "variant", "profile", "category", "final_cover_letter",
                        "final_screening_answers", "cover_letter_with_citations", "bid_amount", "rate_type",
                        "unsupported_before", "unsupported_after", "evidence_ids")}
                        | {"judge_overall": (rec.get("judge") or {}).get("overall"),
                           "gigsim_outcome": (rec.get("gigsim") or {}).get("outcome")})

    by_variant = {}
    for v, recs in results.items():
        by_p = defaultdict(list)
        for r in recs:
            by_p[r["persona"]].append(r)
        by_variant[v] = summarise(recs) | {"by_persona": {p: summarise(rs) for p, rs in sorted(by_p.items())}}
    n_props = sum(b["n_proposals"] for b in by_variant.values())
    complete = all(len(results.get(v, [])) == len(rows) for v in variants) and not stop
    payload = header("proposal_eval", args, n_props, {"variants": variants}, profile) | {
        "status": "complete" if complete else "partial",
        "model_profile": profile, "variants": variants, "best_variant_from_rag_eval": best,
        "job_set": "gold bid jobs, seeded per-persona sample", "n_jobs_per_variant": len(rows),
        "job_ids": [r["job_id"] for r in rows],
        "reply_definition": "GigSim /admin/score outcome in {replied, interview, hired}",
        "unsupported_definition": "claim verifier labels: before = first verification pass on the first draft, "
                                  "after = final pass on the draft that reached approval",
        "judge": {"tier": "judge", "model": config()["models"]["profiles"][profile]["judge"]["model"],
                  "prompt": "agent/prompts/judge_proposal.md"},
        "results": by_variant, "n_errors": len(errors), "errors": errors[:30],
        "stopped_early": stop, "exhausted_models": exhausted_models(),
        "anthropic_spend_usd_all_evals": anthropic_spend(),
    }
    write_json(f"proposals{args.tag}.json", payload, args.out_dir)
    sp = Path(args.out_dir) / f"proposals_samples{args.tag}.jsonl"
    sp.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples), encoding="utf-8")
    print(f"wrote {sp} ({len(samples)} proposals)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--variants", default="v0_naive,best", help="comma list; 'best' = best_variant in rag_variants.json")
    ap.add_argument("--no-judge", action="store_true")
    from evals.runners.common import run

    run(main(ap.parse_args()))
