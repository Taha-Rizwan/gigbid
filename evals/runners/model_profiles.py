"""Model profile comparison (open vs open_alt vs paid) on a small fixed job sample.

For each profile (set through agent.llm.current_profile): the bid graph to the decision on the same
seeded sample of dev jobs (decision accuracy / F1), then the full graph to the approval interrupt on
the gold-bid jobs among them (judge score with the fixed judge, GigSim reply), with latency, tokens and
cost. Records are shared with decision_eval / proposal_eval (same cache keys), so overlapping runs
are not paid twice. The judge is the one in the *default* profile for every row, so scores are
comparable.

    python -m evals.runners.model_profiles [--profiles paid,open,open_alt] [--limit 5] [--proposal-limit 10]
Output: evals/results/model_profiles.json
"""

from __future__ import annotations

import argparse
import asyncio

from evals.runners.common import (
    REPLY_OUTCOMES,
    DailyLimitReached,
    Harness,
    RecordCache,
    add_common_args,
    admin_score,
    anthropic_spend,
    exhausted_models,
    gold_labelled,
    header,
    latency_stats,
    load_dev,
    personas_arg,
    row_job,
    run_bid,
    sample_rows,
    seed_accounts,
    settings_hash,
    setup,
    usage_stats,
    write_json,
)
from evals.runners.decision_eval import decision_record, score_decisions
from evals.runners.proposal_eval import judge, proposal_record


async def main(args) -> None:
    url = setup(args.gigsim)
    from agent.llm import current_profile
    from agent.settings import config

    personas = personas_arg(args.persona)
    rows = sample_rows(load_dev(personas, None, args.dataset_dir, gold_labelled), args.limit)
    gold = {r["job_id"]: r["gold"] for r in rows}
    prop_rows = [r for r in rows if r["gold"].get("bid_or_skip") == "bid"][: args.proposal_limit]
    variant = config()["rag"]["variant"]
    judge_profile = config()["models"]["profile"]
    accounts = seed_accounts()
    dcache, pcache = RecordCache("decision_eval"), RecordCache("proposal_eval")
    out: dict[str, dict] = {}
    errors = []
    async with Harness() as h:
        dgraph, pgraph = h.graph(interrupt_before=["proposal_writer"]), h.graph()
        for profile in args.profiles.split(","):
            current_profile.set(profile)
            sh = settings_hash(profile)
            stop = None
            drecs, precs = [], []
            for persona in personas:
                h.use_persona(persona)
                sem = asyncio.Semaphore(args.concurrency)

                async def dec(r, persona=persona, profile=profile, sh=sh):
                    nonlocal stop
                    key = dcache.key(r["job_id"], persona, sh, profile)
                    if (rec := dcache.get(key)) is not None:
                        return rec
                    if stop:
                        return None
                    async with sem:  # noqa: B023 - awaited within this iteration
                        try:
                            o = await run_bid(h, dgraph, r, persona, f"mp-{profile}", profile)
                        except DailyLimitReached as exc:
                            stop = str(exc)
                            return None
                        except Exception as exc:  # noqa: BLE001
                            errors.append({"profile": profile, "job_id": r["job_id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                            return None
                        rec = decision_record(r, o)
                        return dcache.put(key, rec) if rec["decision"] else None

                async def prop(r, persona=persona, profile=profile, sh=sh):
                    nonlocal stop
                    key = pcache.key(r["job_id"], persona, variant, sh, profile)
                    rec = pcache.get(key)
                    if rec is None:
                        if stop:
                            return None
                        async with sem:  # noqa: B023 - awaited within this iteration
                            try:
                                o = await run_bid(h, pgraph, r, persona, f"mpp-{profile}", profile)
                            except DailyLimitReached as exc:
                                stop = str(exc)
                                return None
                            except Exception as exc:  # noqa: BLE001
                                errors.append({"profile": profile, "job_id": r["job_id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                                return None
                            rec = pcache.put(key, proposal_record(r, o) | {"variant": variant, "profile": profile})
                    if rec.get("final_cover_letter") and not rec.get("gigsim"):
                        acct = (accounts.get(persona) or {}).get("account_id", "acct_ai")
                        rec["gigsim"] = await admin_score(url, r["job_id"], rec["final_cover_letter"],
                                                          rec.get("final_screening_answers") or [], rec["bid_amount"],
                                                          rec["rate_type"], acct)
                        pcache.put(key, rec)
                    if rec.get("final_cover_letter") and not rec.get("judge"):
                        tok = current_profile.set(judge_profile)
                        try:
                            rec["judge"], rec["judge_usage"] = await judge(row_job(r), rec["final_cover_letter"],
                                                                           rec.get("final_screening_answers") or [])
                            pcache.put(key, rec)
                        except Exception as exc:  # noqa: BLE001
                            errors.append({"profile": profile, "job_id": r["job_id"], "error": f"judge: {exc}"[:200]})
                        finally:
                            current_profile.reset(tok)
                    return rec

                drecs += [x for x in await asyncio.gather(*(dec(r) for r in rows if r["persona_id"] == persona)) if x]
                precs += [x for x in await asyncio.gather(*(prop(r) for r in prop_rows if r["persona_id"] == persona)) if x]
            from evals.metrics import mean

            drafted = [r for r in precs if r.get("final_cover_letter")]
            scored = [r for r in drafted if r.get("gigsim")]
            out[profile] = {
                "status": "complete" if len(drecs) == len(rows) and len(precs) == len(prop_rows) else "partial",
                "tiers": config()["models"]["profiles"][profile],
                "decisions": score_decisions(drecs, gold, config()["thresholds"]["maximum_risk_score"]),
                "proposals": {
                    "n_attempted": len(precs), "n_proposals": len(drafted),
                    "judge_overall_mean": mean((r.get("judge") or {}).get("overall") for r in drafted),
                    "n_judged": sum(1 for r in drafted if r.get("judge")),
                    "unsupported_after_mean": mean(r.get("unsupported_after") for r in drafted),
                    "gigsim_reply_rate": (sum(r["gigsim"]["outcome"] in REPLY_OUTCOMES for r in scored) / len(scored))
                    if scored else None,
                    "latency": latency_stats(drafted), "usage_per_proposal": usage_stats(drafted)},
                "stopped_early": stop,
            }
            print(f"[{profile}] decisions n={len(drecs)} proposals n={len(drafted)} stop={stop}")
    payload = header("model_profiles", args, len(rows), {"profiles": args.profiles.split(","), "rag_variant": variant}) | {
        "status": "complete" if all(v["status"] == "complete" for v in out.values()) else "partial",
        "n_decision_jobs": len(rows), "n_proposal_jobs": len(prop_rows), "rag_variant": variant,
        "judge_profile": judge_profile, "judge_model": config()["models"]["profiles"][judge_profile]["judge"]["model"],
        "profiles": out, "n_errors": len(errors), "errors": errors[:20],
        "exhausted_models": exhausted_models(), "anthropic_spend_usd_all_evals": anthropic_spend(),
    }
    write_json(f"model_profiles{args.tag}.json", payload, args.out_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.set_defaults(limit=5)
    ap.add_argument("--profiles", default="paid,open,open_alt")
    ap.add_argument("--proposal-limit", type=int, default=10)
    from evals.runners.common import run

    run(main(ap.parse_args()))
