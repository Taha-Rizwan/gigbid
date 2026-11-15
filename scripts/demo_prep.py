"""Prepare the reviewer account for the demo video: analyse a scam, an injection and good-fit jobs,
approve some proposals, fast-forward GigSim so clients reply, and sync events into Messages."""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx
from dotenv import dotenv_values

import common  # noqa: F401

BASE = os.environ.get("DEMO_API", "http://localhost:8000")
SCAM, INJECTION = "~019e2c8db5f755e213", "~0129aadd2e6621b423"
GOOD = ["~019460153c0758bffc", "~01455edf8c19ca7862", "~015b50d8607e223177", "~016a62e44d04c402e7",
        "~0135fec6794f287609", "~012a92b5d971b4a860"]


def wait(c: httpx.Client, run_id: str, timeout: int = 600) -> str:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = c.get(f"/api/runs/{run_id}").json()["status"]
        if st in ("done", "interrupted", "failed", "needs_attention"):
            return st
        time.sleep(4)
    return "timeout"


def main() -> None:
    env = dotenv_values(".env")
    c = httpx.Client(base_url=BASE, timeout=60)
    c.post("/api/auth/login", json={"email": "reviewer@gigbid.dev", "password": env["REVIEWER_PASSWORD"]}).raise_for_status()
    p = c.get("/api/profile").json()
    body = {k: p[k] for k in ("persona", "display_title", "hourly_floor", "fixed_floor", "weekly_connects_budget",
                              "excluded_keywords", "autonomy", "marketplace_mode")} | {"model_profile": "paid", "hourly_floor": 20, "fixed_floor": 100}
    c.put("/api/profile", json=body).raise_for_status()
    runs = {}
    for job in [SCAM, INJECTION, *GOOD]:
        r = c.post(f"/api/jobs/{job}/analyze")
        if r.status_code == 200:
            runs[job] = r.json()
    status = {job: wait(c, r["run_id"]) for job, r in runs.items()}
    for job, st in status.items():
        d = c.get(f"/api/jobs/{job}").json()
        print(f"{job} {st:12} {d['decision']} fit={d['fit_report'] and d['fit_report']['score']} "
              f"risk={d['risk_report'] and d['risk_report']['score']} {d['title'][:50]}")
    ready = [j for j, st in status.items() if st == "interrupted"]
    keep = ready[:1]  # one left waiting for approval on camera
    for job in ready[1:]:
        tid = runs[job]["thread_id"]
        res = c.post(f"/api/approvals/{tid}", json={"action": "approve"}).json()
        print("approved", job, wait(c, res["run_id"]))
    print("left for the video (awaiting approval):", keep)
    # fast-forward the simulated clients, then pull marketplace events into the pipeline and Messages
    for _ in range(3):
        httpx.post("http://localhost:8081/admin/clock/advance", headers={"X-Admin-Token": env.get("GIGSIM_ADMIN_TOKEN") or "gigsim-admin"},
                   json={"minutes": 480}, timeout=30)
    from worker import tasks

    async def sync():
        await tasks._ensure_engine()
        return await tasks.sync_events({}, "u_reviewer")

    print("sync:", asyncio.run(sync()))
    print("pipeline:", {k: len(v) for k, v in c.get("/api/pipeline").json()["columns"].items()})
    print("conversations:", [x["conversation_id"] for x in c.get("/api/messages").json()])


if __name__ == "__main__":
    sys.exit(main())
