"""R&D question B: retrieval quality of every RAG variant (V0-V8) against the dev-set gold.

Item-level metrics against gold.relevant_evidence_ids: Recall@5, MRR, nDCG@10, plus p50/p95
retrieval latency. Breakdowns: per persona, the >=4-requirement subset (gold.requirement_count),
per category and per stratum. Requirements for V1/V4/V8 come from the Job Analyst (cached).

Variants that need no LLM (V0, V2, V3, V5) run on every labelled job. LLM-backed variants (V1, V4
need the Job Analyst; V7 HyDE, V8 corrective grading) run on the first --llm-limit labelled jobs
per persona, and every variant is also reported on that same subset ("llm_sample") so the
comparison is like for like. V6 (an LLM call per chunk) is skipped unless --include-v6.

    python -m evals.runners.rag_eval [--persona ai_ml] [--limit 50] [--llm-limit 20]
Outputs: evals/results/rag_variants.json and rag_variants.csv
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import time
from collections import defaultdict

from evals.runners.common import (
    DailyLimitReached,
    RecordCache,
    add_common_args,
    cache_stats,
    exhausted_models,
    header,
    install_llm_cache,
    latency_stats,
    load_dev,
    personas_arg,
    row_job,
    setup,
    write_csv,
    write_json,
)

NO_LLM = ["v0_naive", "v2_hybrid", "v3_rerank", "v5_multivector"]
LLM = ["v1_decompose", "v4_outcome", "v7_hyde", "v8_corrective"]
ALL = ["v0_naive", "v1_decompose", "v2_hybrid", "v3_rerank", "v4_outcome", "v5_multivector", "v6_contextual",
       "v7_hyde", "v8_corrective"]
K = 5
K_NDCG = 10


def job_query_text(row: dict) -> str:
    return f"{row['title']}\n\n{row['description']}"


def corpus_fingerprint(persona: str) -> str:
    from rag.ingest.loaders import load_persona

    h = hashlib.sha256()
    for d in sorted(load_persona(persona), key=lambda d: d.evidence_id):
        h.update(d.evidence_id.encode())
        h.update(hashlib.sha256(d.text.encode()).digest())
    return h.hexdigest()[:16]


async def job_requirements(row: dict) -> tuple[list[str], dict]:
    """The Job Analyst's requirements for one job: exactly the analyst node's prompt and model."""
    from agent import llm
    from agent.handoffs import JobSpec
    from agent.nodes.common import job_text

    stats = {"llm_cache_hits": 0, "llm_calls_cold": 0}
    usage = llm.Usage()
    t1, t2 = cache_stats.set(stats), llm.current_usage.set(usage)
    try:
        spec = await llm.structured("analyst", JobSpec, llm.prompt_messages("analyst", job_text(row_job(row))))
    finally:
        cache_stats.reset(t1)
        llm.current_usage.reset(t2)
    return spec.requirements, {"usage": usage.as_dict(), **stats}


def metric_row(ranked: list[str], gold: list[str]) -> dict:
    from evals.metrics import mrr, ndcg_at_k, recall_at_k

    return {"recall@5": recall_at_k(ranked, gold, K), "mrr": mrr(ranked, gold), "ndcg@10": ndcg_at_k(ranked, gold, K_NDCG)}


def summarise(recs: list[dict]) -> dict:
    from evals.metrics import bootstrap_ci, mean

    if not recs:
        return {"n": 0}
    out = {"n": len(recs)}
    for m in ("recall@5", "mrr", "ndcg@10"):
        out[m] = mean(r[m] for r in recs)
    out["recall@5_ci95"] = bootstrap_ci([r["recall@5"] for r in recs])
    lat = latency_stats(recs)
    out["latency_p50_s"], out["latency_p95_s"], out["latency_n_cold"] = lat["p50_s"], lat["p95_s"], lat["n_cold"]
    return out


def breakdown(recs: list[dict]) -> dict:
    by_p, by_cat, by_str = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in recs:
        by_p[r["persona"]].append(r)
        by_cat[r["category"]].append(r)
        by_str[r["stratum"]].append(r)
    return {
        "overall": summarise(recs),
        "requirements_ge4": summarise([r for r in recs if (r["requirement_count"] or 0) >= 4]),
        "requirements_lt4": summarise([r for r in recs if (r["requirement_count"] or 0) < 4]),
        "by_persona": {k: summarise(v) for k, v in sorted(by_p.items())},
        "by_category": {k: summarise(v) for k, v in sorted(by_cat.items())},
        "by_stratum": {k: summarise(v) for k, v in sorted(by_str.items())},
    }


async def main(args) -> None:
    setup(args.gigsim)
    install_llm_cache()
    from agent.settings import config
    from evals.runners.common import use_profile

    use_profile(args.profile)
    from rag.retriever import aget_index, pipeline
    from rag.variants.base import Query, Retriever

    personas = personas_arg(args.persona)
    rows_all = load_dev(personas, None, args.dataset_dir)
    labelled = [r for r in rows_all if (r.get("gold") or {}).get("relevant_evidence_ids")]
    per_p: dict[str, list[dict]] = defaultdict(list)
    for r in labelled:
        if args.limit is None or len(per_p[r["persona_id"]]) < args.limit:
            per_p[r["persona_id"]].append(r)
    rows = [r for p in personas for r in per_p[p]]
    llm_ids = {r["job_id"] for p in personas for r in per_p[p][: args.llm_limit]}
    variants = [v for v in (args.variants.split(",") if args.variants else ALL)]
    skipped: dict[str, str] = {}
    if "v6_contextual" in variants and not args.include_v6:
        variants.remove("v6_contextual")
        from rag.ingest.chunking import structured_chunks
        from rag.ingest.loaders import load_persona

        n_chunks = sum(len(structured_chunks(d, config()["rag"]["chunk_size"], multivector=True))
                       for p in personas for d in load_persona(p))
        skipped["v6_contextual"] = (
            f"not run: needs one LLM call per chunk ({n_chunks} chunks over {len(personas)} personas, each sending "
            "the whole source document) on openai/gpt-oss-20b, which exceeds the Groq free-tier daily token quota "
            "(200k TPD per model) shared with the other evals. Run with --include-v6 when quota allows.")

    cache = RecordCache("rag_eval")
    fps = {p: corpus_fingerprint(p) for p in personas}
    rag_cfg = {k: config()["rag"][k] for k in ("chunk_size", "chunk_overlap", "rrf_k", "rerank_candidates",
                                                "outcome_boost", "corrective_max_requeries")}
    reqs: dict[str, list[str]] = {}
    req_usage: list[dict] = []
    status: dict[str, str] = {}
    results: dict[str, list[dict]] = {}
    stop_llm = None

    async def ensure_reqs(todo: list[dict]) -> None:
        nonlocal stop_llm
        sem = asyncio.Semaphore(args.concurrency)

        async def one(r):
            nonlocal stop_llm
            if r["job_id"] in reqs or stop_llm:
                return
            async with sem:
                if stop_llm:
                    return
                try:
                    reqs[r["job_id"]], u = await job_requirements(r)
                    req_usage.append(u)
                except DailyLimitReached as exc:
                    stop_llm = str(exc)
                except Exception as exc:  # noqa: BLE001
                    print(f"  requirements failed for {r['job_id']}: {type(exc).__name__}: {str(exc)[:160]}")

        await asyncio.gather(*(one(r) for r in todo))

    from rag.index.embeddings import embed

    # Query embeddings are cached on disk, so whichever variant ran first would pay for them.
    # Embed every query text up front and time all variants with a warm query cache.
    t0 = time.perf_counter()
    await asyncio.to_thread(embed, [job_query_text(r) for r in rows], None, True)
    embed_s = (time.perf_counter() - t0) / max(1, len(rows))
    warmed: set[str] = set()

    ordered = [v for v in NO_LLM + LLM + ["v6_contextual"] if v in variants]
    for variant in ordered:
        cfg = pipeline(variant)
        needs_llm = variant in LLM or variant == "v6_contextual"
        needs_reqs = cfg.decompose or cfg.corrective
        retrieval_llm = cfg.hyde or cfg.corrective or cfg.contextual
        todo = [r for r in rows if not needs_llm or r["job_id"] in llm_ids]
        if needs_reqs:
            await ensure_reqs(todo)
            todo = [r for r in todo if r["job_id"] in reqs]
            fresh = [q for r in todo for q in reqs[r["job_id"]] if q not in warmed]
            if fresh:
                await asyncio.to_thread(embed, fresh, None, True)
                warmed.update(fresh)
        recs: list[dict] = []
        print(f"[{variant}] {len(todo)} jobs")
        for persona in personas:
            prow = [r for r in todo if r["persona_id"] == persona]
            if not prow:
                continue
            index = await aget_index(persona, cfg)
            retr = Retriever(cfg, index)
            await asyncio.to_thread(retr.retrieve, Query(persona, "warm up the embedding and reranker models", [], K))
            for r in prow:
                rq = reqs.get(r["job_id"], []) if needs_reqs else []
                key = cache.key(variant, persona, r["job_id"], fps[persona], rag_cfg, rq, K_NDCG,
                                config()["models"]["embeddings"])
                rec = cache.get(key)
                if rec is None:
                    if stop_llm and retrieval_llm:
                        continue
                    stats = {"llm_cache_hits": 0, "llm_calls_cold": 0}
                    tok = cache_stats.set(stats)
                    try:
                        t0 = time.perf_counter()
                        items = await retr.aretrieve(Query(persona, job_query_text(r), rq, K_NDCG))
                        lat = time.perf_counter() - t0
                    except DailyLimitReached as exc:
                        stop_llm = str(exc)
                        continue
                    finally:
                        cache_stats.reset(tok)
                    rec = cache.put(key, {"ranked": [i.evidence_id for i in items], "latency_s": round(lat, 4),
                                          **stats})
                g = r["gold"]
                recs.append({"job_id": r["job_id"], "persona": persona, "category": r.get("category"),
                             "stratum": r.get("stratum"), "requirement_count": g.get("requirement_count"),
                             "latency_s": rec["latency_s"], "llm_cache_hits": rec.get("llm_cache_hits", 0),
                             **metric_row(rec["ranked"], g["relevant_evidence_ids"])})
        expected = len([r for r in rows if not needs_llm or r["job_id"] in llm_ids])
        status[variant] = "complete" if len(recs) == expected and expected else "partial"
        results[variant] = recs

    # like-for-like subset: jobs every LLM variant that ran actually covered
    ran_llm = [v for v in results if v in LLM and results[v]]
    common = set(llm_ids)
    for v in ran_llm:
        common &= {r["job_id"] for r in results[v]}
    out_variants = {}
    csv_rows = []
    for v, recs in results.items():
        body = {"status": status[v], "n": len(recs), "uses_llm": v in LLM,
                "pipeline": pipeline(v).__dict__} | breakdown(recs)
        body["llm_sample"] = summarise([r for r in recs if r["job_id"] in common])
        out_variants[v] = body
        for subset, s in [("overall", body["overall"]), ("requirements_ge4", body["requirements_ge4"]),
                          ("llm_sample", body["llm_sample"])] + [(f"persona:{k}", s) for k, s in body["by_persona"].items()]:
            csv_rows.append({"variant": v, "subset": subset, "n": s.get("n"), "recall@5": s.get("recall@5"),
                             "mrr": s.get("mrr"), "ndcg@10": s.get("ndcg@10"),
                             "latency_p50_s": s.get("latency_p50_s"), "latency_p95_s": s.get("latency_p95_s")})

    # best variant: highest Recall@5 (tie: nDCG@10) on the like-for-like subset
    cands = {v: b["llm_sample"] for v, b in out_variants.items() if b["llm_sample"].get("n")}
    if not cands:
        cands = {v: b["overall"] for v, b in out_variants.items() if b["overall"].get("n")}
    best = max(cands, key=lambda v: (cands[v].get("recall@5") or 0, cands[v].get("ndcg@10") or 0)) if cands else None

    from evals.metrics import mean

    n_jobs = len(rows)
    overall_status = "complete" if all(s == "complete" for s in status.values()) and not skipped else "partial"
    payload = header("rag_eval", args, n_jobs, {"k": K, "k_ndcg": K_NDCG, "corpus_fingerprints": fps}) | {
        "status": overall_status,
        "gold": "gold.relevant_evidence_ids (llm_label_v1, qwen/qwen3.8-27b; past proposals not in the label catalogue)",
        "n_dev_rows": len(rows_all), "n_labelled_rows": len(labelled), "n_evaluated": n_jobs,
        "n_llm_sample": len(common) if ran_llm else 0, "llm_limit_per_persona": args.llm_limit,
        "requirement_extraction": {"n": len(reqs), "tokens_mean": mean(u["usage"]["tokens"] for u in req_usage),
                                   "cold_calls": sum(u["llm_calls_cold"] for u in req_usage)},
        "latency_note": ("retrieval only, per job, warm query-embedding cache (all variants alike); embedding one "
                         f"job text cold took {embed_s:.4f}s on average (CPU, batched), not included"),
        "best_variant": best,
        "best_variant_rule": "highest Recall@5 (tie: nDCG@10) on llm_sample, the jobs every LLM variant covered",
        "variants": out_variants, "skipped": skipped,
        "stopped_early": stop_llm, "exhausted_models": exhausted_models(),
    }
    write_json(f"rag_variants{args.tag}.json", payload, args.out_dir)
    write_csv(f"rag_variants{args.tag}.csv", csv_rows, args.out_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--variants", default=None, help="comma list (default all)")
    ap.add_argument("--llm-limit", type=int, default=20, help="jobs per persona for LLM-backed variants")
    ap.add_argument("--include-v6", action="store_true")
    from evals.runners.common import run

    run(main(ap.parse_args()))
