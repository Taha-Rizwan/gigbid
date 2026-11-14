"""End-to-end smoke test through the HTTP API (what the UI does):
login -> scout -> analyse a job -> stream the run -> studio -> approve -> pipeline.

    python scripts/smoke_api.py --base http://localhost:8000 --email reviewer@gigbid.dev --password ...
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx


def wait_run(c: httpx.Client, run_id: str, timeout: int = 900) -> dict:
    t0, seen = time.time(), 0
    while time.time() - t0 < timeout:
        r = c.get(f"/api/runs/{run_id}").json()
        for e in r["events"][seen:]:
            print(f"   {e['kind']:9} {e['node']:20} {e['summary'][:100]}")
        seen = len(r["events"])
        if r["status"] in ("done", "interrupted", "failed", "needs_attention"):
            return r
        time.sleep(3)
    raise TimeoutError(run_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--email", default="reviewer@gigbid.dev")
    ap.add_argument("--password", required=True)
    ap.add_argument("--job", default=None)
    ap.add_argument("--approve", action="store_true")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.base, timeout=60)
    assert c.post("/api/auth/login", json={"email": a.email, "password": a.password}).status_code == 200, "login failed"
    print("health:", c.get("/api/health").json()["status"])
    if not a.job:
        run = c.post("/api/jobs/scout").json()
        print("scout run", run["run_id"])
        wait_run(c, run["run_id"], 300)
        inbox = c.get("/api/jobs", params={"sort": "newest"}).json()
        print("inbox:", inbox["total"], "jobs")
        a.job = inbox["items"][0]["job_id"]
    started = c.post(f"/api/jobs/{a.job}/analyze")
    print("analyze", a.job, started.status_code, started.json())
    run = wait_run(c, started.json()["run_id"])
    print("run status:", run["status"], "tokens", run["tokens"], "cost", run["cost_usd"])
    detail = c.get(f"/api/jobs/{a.job}").json()
    print("decision:", detail["decision"], detail["decision_reasons"][:2])
    if run["status"] != "interrupted":
        return 0
    st = c.get(f"/api/proposals/{started.json()['thread_id']}").json()
    print("studio: version", st["version"], "| unsupported", st["unsupported_before"], "->", st["unsupported_after"],
          "| pending approval:", bool(st["pending_approval"]))
    print("\n".join(p["text"] for p in st["paragraphs"]))
    if a.approve:
        res = c.post(f"/api/approvals/{st['thread_id']}", json={"action": "approve"}).json()
        print("approval:", res)
        run = wait_run(c, res["run_id"])
        print("after approval:", run["status"])
        print("pipeline:", json.dumps({k: len(v) for k, v in c.get("/api/pipeline").json()["columns"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
