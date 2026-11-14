"""X2 signature extension: A/B test of two proposal strategies in GigSim.

Paired design: every job is drafted twice by the full bid graph (stopping at the approval interrupt,
nothing is ever submitted), once per strategy in agent/config.yaml `proposal_strategies`. Each draft is
scored by GigSim's stateless client model (POST /admin/score). Reply = replied/interview/hired.
Significance: exact McNemar test on the discordant pairs (paired binary outcomes), plus a
two-proportion z-test for reference.

    python -m evals.runners.ab_experiment --gigsim http://localhost:8092 --n 40 --profile paid
Needs a GigSim seeded with the dev jobs (data/processed/gigsim_seed).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import time
import uuid
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

import httpx

import common  # noqa: F401  (selector event loop on Windows; must run before asyncio.run)

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = {"ai_ml": ("acct_ai", "gigsim-token-ai"), "fullstack": ("acct_web", "gigsim-token-web"),
           "data_analyst": ("acct_data", "gigsim-token-data")}
REPLY = {"replied", "interview", "hired"}


def dev_jobs(persona: str) -> list[dict]:
    path = ROOT / "evals" / "datasets" / f"dev_{persona}.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    core = {"ai_ml": {"ml_ai"}, "fullstack": {"web_fullstack"}, "data_analyst": {"data_analysis", "data_engineering"}}[persona]
    # jobs in the persona's core categories, excluding constructed scams and injections; the graph's own
    # decision then filters out skips (recorded per row), so no gold bid/skip label is needed here
    return [r for r in rows if r.get("category") in core and not r["gold"].get("is_scam")
            and not r["gold"].get("has_injection")]


def mcnemar_exact(b: int, c: int) -> float:
    from scipy.stats import binomtest

    n = b + c
    return 1.0 if n == 0 else float(binomtest(min(b, c), n, 0.5).pvalue)


def two_prop_z(x1: int, n1: int, x2: int, n2: int) -> float:
    from math import sqrt

    from scipy.stats import norm

    p = (x1 + x2) / max(1, n1 + n2)
    se = sqrt(max(p * (1 - p) * (1 / max(1, n1) + 1 / max(1, n2)), 1e-12))
    return float(2 * (1 - norm.cdf(abs((x1 / max(1, n1) - x2 / max(1, n2)) / se))))


async def draft(graph, box, persona: str, job_id: str, strategy: str, profile_name: str):
    from agent.context import RunContext
    from agent.llm import Usage
    from agent.runner import start_bid

    ctx = RunContext(toolbox=box, usage=Usage(), trace_id=uuid.uuid4().hex)
    profile = {"hourly_floor": 30, "fixed_floor": 150, "weekly_connects_budget": 10_000, "strategy": strategy}
    out = await start_bid(graph, f"ab-{strategy}", persona, job_id, profile, ctx,
                          thread_id=f"ab-{strategy}-{job_id}-{uuid.uuid4().hex[:6]}", profile_name=profile_name)
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gigsim", default="http://localhost:8092")
    ap.add_argument("--n", type=int, default=40, help="jobs in total, spread across personas")
    ap.add_argument("--profile", default="paid")
    ap.add_argument("--personas", default="ai_ml,fullstack,data_analyst")
    a = ap.parse_args()
    os.environ["GIGSIM_BASE_URL"] = a.gigsim

    from agent.config_strategies import strategies  # noqa: F401 - documents which strategies exist
    from agent.graphs import bid_graph
    from agent.mcp_client import ToolBox
    from agent.memory.store import open_persistence
    from mcp_servers.marketplace import server as srv

    names = list(strategies())[:2]
    personas = a.personas.split(",")
    per = max(1, a.n // len(personas))
    rows, cost, latencies = [], 0.0, []
    async with AsyncExitStack() as stack:
        saver, store = await open_persistence(stack, durable=False)
        graph = bid_graph.build(saver, store)
        box = await ToolBox.in_memory(stack)
        async with httpx.AsyncClient(timeout=60) as http:
            for persona in personas:
                account, token = ACCOUNT[persona]
                os.environ["GIGSIM_DEFAULT_TOKEN"] = token
                srv._adapters.clear()
                for job in dev_jobs(persona)[:per]:
                    rec = {"persona": persona, "job_id": job["job_id"], "category": job.get("category")}
                    for strategy in names:
                        t0 = time.perf_counter()
                        try:
                            out = await draft(graph, box, persona, job["job_id"], strategy, a.profile)
                        except Exception as exc:  # noqa: BLE001
                            rec[strategy] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
                            continue
                        latencies.append(time.perf_counter() - t0)
                        cost += out["usage"]["cost_usd"]
                        dr = (out["state"] or {}).get("dry_run")
                        if out["status"] != "interrupted" or not dr:
                            rec[strategy] = {"status": out["status"], "decision": str((out["state"] or {}).get("decision"))}
                            continue
                        r = await http.post(f"{a.gigsim}/admin/score", headers={"X-Admin-Token": os.environ.get("GIGSIM_ADMIN_TOKEN", "gigsim-admin")},
                                            json={"job_id": job["job_id"], "cover_letter": dr["cover_letter"],
                                                  "screening_answers": dr["screening_answers"], "bid_amount": dr["bid_amount"],
                                                  "rate_type": dr["rate_type"], "account_id": account})
                        s = r.json()
                        rec[strategy] = {"outcome": s.get("outcome"), "p_reply": s.get("p_reply"),
                                         "quality": s.get("quality"), "words": len(dr["cover_letter"].split())}
                    rows.append(rec)
                    print(json.dumps(rec)[:220], flush=True)
    paired = [r for r in rows if all("outcome" in r.get(s, {}) for s in names)]
    A, B = names
    a_rep = [r[A]["outcome"] in REPLY for r in paired]
    b_rep = [r[B]["outcome"] in REPLY for r in paired]
    b_only = sum(1 for x, y in zip(a_rep, b_rep, strict=True) if x and not y)
    c_only = sum(1 for x, y in zip(a_rep, b_rep, strict=True) if y and not x)
    n = len(paired)
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
        "model_profile": a.profile, "strategies": {k: strategies()[k] for k in names},
        "n_jobs_attempted": len(rows), "n_paired": n,
        "reply_rate": {A: round(sum(a_rep) / n, 3) if n else None, B: round(sum(b_rep) / n, 3) if n else None},
        "mean_p_reply": {s: round(statistics.mean(r[s]["p_reply"] for r in paired), 4) if n else None for s in names},
        "discordant": {f"{A}_only": b_only, f"{B}_only": c_only},
        "mcnemar_exact_p": round(mcnemar_exact(b_only, c_only), 4),
        "two_proportion_z_p": round(two_prop_z(sum(a_rep), n, sum(b_rep), n), 4) if n else None,
        "cost_usd": round(cost, 4),
        "p50_latency_s": round(statistics.median(latencies), 1) if latencies else None,
        "rows": rows,
        "note": "Outcomes come from our own simulated clients (GigSim), not real clients.",
    }
    out = ROOT / "evals" / "results" / "ab_experiment.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
