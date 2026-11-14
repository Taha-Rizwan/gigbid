"""Ablation of the best retrieval pipeline: switch off one component at a time
(PipelineConfig.without) and record the change in Recall@5 / MRR / nDCG@10.

The best pipeline and its job set come from evals/results/rag_variants.json (best_variant; the
llm_sample jobs if it is an LLM-backed variant, else every labelled job). Requirements are the
cached Job Analyst requirements.

    python -m evals.runners.ablation [--variant v4_outcome] [--persona ai_ml]
Output: evals/results/ablation.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from evals.runners.common import (
    RESULTS_DIR,
    DailyLimitReached,
    RecordCache,
    add_common_args,
    cache_stats,
    exhausted_models,
    header,
    install_llm_cache,
    load_dev,
    personas_arg,
    setup,
    use_profile,
    write_json,
)
from evals.runners.rag_eval import (
    K_NDCG,
    LLM,
    K,
    corpus_fingerprint,
    job_query_text,
    job_requirements,
    metric_row,
    summarise,
)

FLAGS = ["decompose", "hybrid", "rerank", "outcome", "contextual", "hyde", "corrective"]


async def evaluate(cfg, rows: list[dict], reqs: dict[str, list[str]], fps: dict[str, str]) -> tuple[list[dict], str | None]:
    from agent.settings import config
    from rag.retriever import aget_index
    from rag.variants.base import Query, Retriever

    cache = RecordCache("ablation")
    recs, stop = [], None
    for persona in sorted({r["persona_id"] for r in rows}):
        retr = Retriever(cfg, await aget_index(persona, cfg))
        await asyncio.to_thread(retr.retrieve, Query(persona, "warm up", [], K))
        for r in [x for x in rows if x["persona_id"] == persona]:
            rq = reqs.get(r["job_id"], []) if (cfg.decompose or cfg.corrective) else []
            key = cache.key(cfg.__dict__, persona, r["job_id"], fps[persona], rq, config()["rag"])
            rec = cache.get(key)
            if rec is None:
                if stop:
                    continue
                stats = {"llm_cache_hits": 0, "llm_calls_cold": 0}
                tok = cache_stats.set(stats)
                try:
                    t0 = time.perf_counter()
                    items = await retr.aretrieve(Query(persona, job_query_text(r), rq, K_NDCG))
                    rec = cache.put(key, {"ranked": [i.evidence_id for i in items],
                                          "latency_s": round(time.perf_counter() - t0, 4), **stats})
                except DailyLimitReached as exc:
                    stop = str(exc)
                    continue
                finally:
                    cache_stats.reset(tok)
            g = r["gold"]
            recs.append({"job_id": r["job_id"], "persona": persona, "category": r.get("category"),
                         "stratum": r.get("stratum"), "requirement_count": g.get("requirement_count"),
                         "latency_s": rec["latency_s"], "llm_cache_hits": rec.get("llm_cache_hits", 0),
                         **metric_row(rec["ranked"], g["relevant_evidence_ids"])})
    return recs, stop


async def main(args) -> None:
    setup(args.gigsim)
    install_llm_cache()
    profile = use_profile(args.profile)
    from rag.retriever import pipeline

    rv_path = Path(args.out_dir) / "rag_variants.json"
    rv = json.loads((rv_path if rv_path.exists() else RESULTS_DIR / "rag_variants.json").read_text(encoding="utf-8")) \
        if (rv_path.exists() or (RESULTS_DIR / "rag_variants.json").exists()) else {}
    best = args.variant or rv.get("best_variant")
    if not best:
        write_json(f"ablation{args.tag}.json", header("ablation", args, 0) | {
            "status": "waiting", "reason": "no best_variant: run rag_eval first"}, args.out_dir)
        return
    personas = personas_arg(args.persona)
    labelled = [r for r in load_dev(personas, None, args.dataset_dir) if (r.get("gold") or {}).get("relevant_evidence_ids")]
    if best in LLM:
        llm_limit = rv.get("llm_limit_per_persona") or 20
        per: dict[str, list] = {}
        for r in labelled:
            per.setdefault(r["persona_id"], []).append(r)
        rows = [r for p in personas for r in per.get(p, [])[:llm_limit]]
    else:
        rows = labelled[:]
    if args.limit:
        rows = [r for p in personas for r in [x for x in rows if x["persona_id"] == p][: args.limit]]
    base = pipeline(best)
    fps = {p: corpus_fingerprint(p) for p in personas}
    reqs: dict[str, list[str]] = {}
    stop = None
    if base.decompose or base.corrective:
        for r in rows:
            try:
                reqs[r["job_id"]], _ = await job_requirements(r)
            except DailyLimitReached as exc:
                stop = str(exc)
                break
        rows = [r for r in rows if r["job_id"] in reqs]
    base_recs, s = await evaluate(base, rows, reqs, fps)
    stop = stop or s
    base_sum = summarise(base_recs)
    ablations = {}
    for flag in [f for f in FLAGS if getattr(base, f)]:
        cfg = base.without(**{flag: False})
        recs, s = await evaluate(cfg, rows, reqs, fps)
        stop = stop or s
        summ = summarise(recs)
        ablations[f"without_{flag}"] = summ | {"delta_vs_full": {
            m: (summ.get(m) - base_sum.get(m)) if summ.get(m) is not None and base_sum.get(m) is not None else None
            for m in ("recall@5", "mrr", "ndcg@10")}}
    if base.scheme != "fixed":
        from dataclasses import replace

        cfg = replace(base, name=f"{base.name}-fixedchunks", scheme="fixed")
        recs, s = await evaluate(cfg, rows, reqs, fps)
        summ = summarise(recs)
        ablations["fixed_chunks_instead_of_" + base.scheme] = summ | {"delta_vs_full": {
            m: (summ.get(m) - base_sum.get(m)) if summ.get(m) is not None and base_sum.get(m) is not None else None
            for m in ("recall@5", "mrr", "ndcg@10")}}
    payload = header("ablation", args, len(base_recs), {"best_variant": best}, profile) | {
        "status": "complete" if not stop and len(base_recs) == len(rows) else "partial",
        "best_variant": best, "pipeline": base.__dict__, "n_jobs": len(rows),
        "full": base_sum, "ablations": ablations, "stopped_early": stop, "exhausted_models": exhausted_models(),
        "note": "delta = metric without the component minus metric of the full pipeline (negative = the component helps)",
    }
    write_json(f"ablation{args.tag}.json", payload, args.out_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--variant", default=None, help="pipeline to ablate (default: best_variant from rag_variants.json)")
    from evals.runners.common import run

    run(main(ap.parse_args()))
