"""Worker tasks. Each is idempotent: re-running after a crash never double-analyses or double-submits
(bid threads are keyed by job, marketplace writes carry idempotency keys, checkpoints resume)."""

from __future__ import annotations

import json
import logging
from typing import Any

from agent.handoffs import Job
from agent.marketplace_port import MarketplaceUnavailable
from agent.memory.promotion_rules import record_outcome
from agent.mcp_client import ToolBox
from agent.nodes.scout import fingerprint, scout
from agent.settings import config
from apps.api import runs
from common import db

log = logging.getLogger("gigbid.worker")

STAGE = {"proposal_viewed": "viewed", "client_replied": "replied", "interview_requested": "interview",
         "hired": "hired", "declined": "lost"}
ORDER = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]


async def _ensure_engine() -> None:
    if runs.engine.bid is None:
        await runs.engine.open()


async def _queue(user_id: str, kind: str, payload: dict) -> None:
    await db.execute("insert into work_queue (user_id, kind, payload) values (%s,%s,%s)", user_id, kind, json.dumps(payload))


async def run_start(ctx: dict, run_id: str, user_id: str, thread_id: str, start: dict, profile_name: str | None = None):
    await _ensure_engine()
    try:
        await runs.execute(run_id, user_id, thread_id, start=start, profile_name=profile_name)
    except MarketplaceUnavailable:
        await _queue(user_id, "run_start", {"run_id": run_id, "thread_id": thread_id, "start": start,
                                            "profile_name": profile_name})


async def run_resume(ctx: dict, run_id: str, user_id: str, thread_id: str, answer: dict, profile_name: str | None = None):
    await _ensure_engine()
    try:
        await runs.execute(run_id, user_id, thread_id, answer=answer, profile_name=profile_name)
    except MarketplaceUnavailable:
        await _queue(user_id, "run_resume", {"run_id": run_id, "thread_id": thread_id, "answer": answer,
                                             "profile_name": profile_name})


async def run_update(ctx: dict, run_id: str, user_id: str, thread_id: str, update: dict):
    await _ensure_engine()
    from agent.handoffs import ProposalDraft

    values = dict(update["values"])
    if "draft" in values:
        values["draft"] = ProposalDraft(**values["draft"])
    await runs.execute(run_id, user_id, thread_id, update={"values": values, "as_node": update["as_node"]})


async def scout_user(ctx: dict, user_id: str, run_id: str | None = None) -> dict:
    """Run the user's saved searches, de-duplicate against the inbox, queue new jobs, and auto-analyse."""
    await _ensure_engine()
    profile = (await db.fetchrow("select data from profiles where user_id=%s", user_id) or {}).get("data") or {}
    searches = [r["data"] for r in await db.fetch("select data from searches where user_id=%s", user_id)
                if r["data"].get("enabled", True)]
    seen = await db.fetch("select job_id, job->>'fingerprint' as fp from jobs where user_id=%s", user_id)
    box = await ToolBox.http(user_id)
    emit = None
    if run_id:
        emit, init = runs._emitter(run_id)
        await init()
        await emit("scout", "start", "running saved searches", None)
        await db.execute("update runs set status='running' where run_id=%s", run_id)
    try:
        new, stats = await scout(box.for_agent("scout"), searches, {r["job_id"] for r in seen},
                                 {r["fp"] for r in seen if r["fp"]}, profile.get("excluded_keywords"))
    except MarketplaceUnavailable as exc:
        if emit:
            await emit("scout", "error", f"marketplace unavailable ({exc.detail}); will retry", None)
            await db.execute("update runs set status='queued' where run_id=%s", run_id)
        await _queue(user_id, "scout_user", {})
        return {"queued": True}
    intake = box.for_agent("intake")
    for j in new:
        try:
            full = await intake.call("get_job", job_id=j["job_id"])
        except Exception:  # noqa: BLE001
            full = j
        full["fingerprint"] = j["fingerprint"]
        await db.execute(
            """insert into jobs (user_id, job_id, job, status, connects_cost, posted_at) values (%s,%s,%s,'new',%s,%s)
               on conflict (user_id, job_id) do nothing""",
            user_id, j["job_id"], json.dumps(full, default=str), full.get("connects_cost"), full.get("posted_at"))
    await db.execute("update searches set last_run_at=now() where user_id=%s", user_id)
    if emit:
        await emit("scout", "end", f"{len(new)} new jobs, {stats['duplicates']} duplicates skipped", stats)
        await emit("run", "done", "scout done", stats)
        await db.execute("update runs set status='done', finished_at=now() where run_id=%s", run_id)
    # analyse new jobs (bid graph; drafting stops at the approval interrupt, never sends)
    for j in new[: int(profile.get("auto_analyse_limit", 5))]:
        await analyse_job({}, user_id, j["job_id"])
    return {"new": len(new), **stats}


async def analyse_job(ctx: dict, user_id: str, job_id: str) -> None:
    profile = (await db.fetchrow("select data from profiles where user_id=%s", user_id) or {}).get("data") or {}
    thread_id = f"bid-{user_id}-{job_id}"
    snap = await runs.engine.bid.aget_state({"configurable": {"thread_id": thread_id}})
    if snap.values:  # idempotent: a restarted worker never re-analyses the same job
        return
    run_id = await runs.new_run(user_id, thread_id, "bid", job_id, thread_id)
    await run_start(ctx, run_id, user_id, thread_id,
                    {"persona_id": profile.get("persona", "ai_ml"), "job_id": job_id, "profile": profile},
                    profile.get("model_profile"))
    if profile.get("autonomy") == "auto_skip_low_fit":
        row = await db.fetchrow("select recommendation from jobs where user_id=%s and job_id=%s", user_id, job_id)
        if row and row["recommendation"] == "skip":
            await db.execute("update jobs set status='skipped' where user_id=%s and job_id=%s", user_id, job_id)


async def sync_events(ctx: dict, user_id: str) -> dict:
    """Marketplace events -> pipeline stages, conversations, and outcome memory (aggregates only)."""
    await _ensure_engine()
    box = await ToolBox.http(user_id)
    tracker = box.for_agent("tracker")
    cur = await db.fetchrow("select cursor from events_cursor where user_id=%s", user_id)
    after = cur["cursor"] if cur else 0
    try:
        out = await tracker.call("get_events", after=after, limit=200)
    except MarketplaceUnavailable:
        return {"queued": True}
    n = 0
    for ev in out.get("events", []):
        n += 1
        pid = ev.get("proposal_id")
        stage = STAGE.get(ev["type"])
        if pid and stage:
            row = await db.fetchrow("select thread_id, stage, category from proposals where user_id=%s and proposal_id=%s",
                                    user_id, pid)
            if row and ORDER.index(stage) > ORDER.index(row["stage"]):
                await db.execute("update proposals set stage=%s, conversation_id=coalesce(%s, conversation_id), "
                                 "updated_at=now() where user_id=%s and proposal_id=%s",
                                 stage, ev.get("thread_id"), user_id, pid)
                if stage in ("replied", "interview", "hired", "lost"):
                    await record_outcome(runs.engine.store, user_id, row["category"] or "other",
                                         "declined" if stage == "lost" else stage)
        if ev.get("thread_id") and ev["type"] in ("client_replied", "interview_requested"):
            job_id = (await db.fetchrow("select job_id from proposals where user_id=%s and proposal_id=%s", user_id, pid)
                      or {}).get("job_id")
            await db.execute(
                """insert into conversations (user_id, conversation_id, job_id, proposal_id, state) values (%s,%s,%s,%s,%s)
                   on conflict (user_id, conversation_id) do update set updated_at=now(),
                   state=conversations.state || '{"unread": true}'::jsonb""",
                user_id, ev["thread_id"], job_id, pid, json.dumps({"unread": True}))
    await db.execute("""insert into events_cursor (user_id, cursor) values (%s,%s) on conflict (user_id)
                        do update set cursor=excluded.cursor, updated_at=now()""", user_id, out.get("next_cursor", after))
    return {"events": n}


async def retry_queued(ctx: dict) -> dict:
    """Degraded mode recovery: when the marketplace is back, replay queued work."""
    from apps.api.service import health

    if (await health()).status != "ok":
        return {"skipped": "still degraded"}
    rows = await db.fetch("update work_queue set status='running', attempts=attempts+1 where id in "
                          "(select id from work_queue where status='queued' and next_at <= now() order by id limit 10) "
                          "returning id, user_id, kind, payload")
    for r in rows:
        p = r["payload"]
        try:
            if r["kind"] == "run_start":
                await run_start(ctx, p["run_id"], r["user_id"], p["thread_id"], p["start"], p.get("profile_name"))
            elif r["kind"] == "run_resume":
                await run_resume(ctx, p["run_id"], r["user_id"], p["thread_id"], p["answer"], p.get("profile_name"))
            elif r["kind"] == "scout_user":
                await scout_user(ctx, r["user_id"])
            await db.execute("update work_queue set status='done' where id=%s", r["id"])
        except Exception as exc:  # noqa: BLE001
            await db.execute("update work_queue set status='queued', last_error=%s, next_at=now() + interval '2 minutes' "
                             "where id=%s", str(exc)[:300], r["id"])
    return {"replayed": len(rows)}


async def scheduled_scout(ctx: dict) -> dict:
    """Cron: run each user's saved searches when their interval has elapsed (conservative in live mode)."""
    mk = config()["marketplace"]
    rows = await db.fetch(
        """select s.user_id, min(coalesce((s.data->>'interval_minutes')::int, %s)) as every,
                  max(s.last_run_at) as last, max(p.data->>'marketplace_mode') as mode
           from searches s join profiles p on p.user_id=s.user_id group by s.user_id""", mk["scout_interval_minutes"])
    ran = 0
    for r in rows:
        every = max(r["every"], mk["live_scout_interval_minutes"]) if r["mode"] == "upwork_live" else r["every"]
        if r["last"] is None or (await db.fetchrow("select now() - %s::timestamptz > make_interval(mins => %s) as due",
                                                   r["last"], every))["due"]:
            await scout_user(ctx, r["user_id"])
            ran += 1
    return {"scouted": ran}


async def scheduled_sync(ctx: dict) -> dict:
    users = await db.fetch("select distinct user_id from proposals where stage not in ('hired','lost')")
    for u in users:
        await sync_events(ctx, u["user_id"])
    return {"users": len(users)}


_ = (Job, fingerprint, Any)
