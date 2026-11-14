"""Simulated clock: minute arithmetic, job release, event reveal and weekly Connects reset.

Sim time is `GIGSIM_START + clock_minute`. Outcome events are planned into `scheduled` at submit
time and only copied into `events` (which assigns the cursor id) when the clock reaches them, so the
event cursor is monotonic in reveal order.
"""

from __future__ import annotations

import asyncio
import logging
import math
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from gigsim.db import dumps, loads, meta_get, meta_set, next_id

log = logging.getLogger("gigsim.clock")

MINUTES_PER_WEEK = 7 * 24 * 60
STATUS_RANK = {"submitted": 0, "viewed": 1, "replied": 2, "interview": 3, "hired": 4}


def iso_at(start: datetime, minute: int) -> str:
    return (start + timedelta(minutes=int(minute))).strftime("%Y-%m-%dT%H:%M:%SZ")


def minute_of(start: datetime, when: datetime) -> float:
    return (when - start).total_seconds() / 60.0


def now_minute(conn: sqlite3.Connection) -> int:
    return int(meta_get(conn, "clock_minute", "0") or 0)


def resets_at(start: datetime, minute: int) -> str:
    week = math.floor(minute / MINUTES_PER_WEEK)
    return iso_at(start, (week + 1) * MINUTES_PER_WEEK)


def event_public(row: sqlite3.Row | dict[str, Any], start: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {"event_id": row["event_id"], "type": row["type"], "at": iso_at(start, row["at_minute"])}
    for key in ("job_id", "proposal_id", "thread_id"):
        if row[key] is not None:
            out[key] = row[key]
    out["data"] = loads(row["data"], {})
    return out


def _insert_event(conn: sqlite3.Connection, *, account_id: str | None, type_: str, at: int,
                  job_id: str | None = None, proposal_id: str | None = None,
                  thread_id: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    cur = conn.execute(
        "INSERT INTO events(account_id, type, at_minute, job_id, proposal_id, thread_id, data) VALUES (?,?,?,?,?,?,?)",
        (account_id, type_, at, job_id, proposal_id, thread_id, dumps(data or {})),
    )
    return {"event_id": cur.lastrowid, "account_id": account_id, "type": type_, "at_minute": at,
            "job_id": job_id, "proposal_id": proposal_id, "thread_id": thread_id, "data": dumps(data or {})}


def insert_message(conn: sqlite3.Connection, thread_id: str, sender: str, text: str, minute: int) -> str:
    message_id = next_id(conn, "msg")
    seq = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE thread_id = ?", (thread_id,)).fetchone()[0]
    conn.execute(
        "INSERT INTO messages(message_id, thread_id, sender, text, sent_minute, seq) VALUES (?,?,?,?,?,?)",
        (message_id, thread_id, sender, text, minute, seq),
    )
    if sender == "client":
        conn.execute(
            "UPDATE threads SET last_message_minute = ?, unread = unread + 1 WHERE thread_id = ?",
            (minute, thread_id),
        )
    else:
        conn.execute("UPDATE threads SET last_message_minute = ? WHERE thread_id = ?", (minute, thread_id))
    return message_id


def _ensure_thread(conn: sqlite3.Connection, proposal: sqlite3.Row, minute: int) -> str:
    if proposal["thread_id"]:
        return proposal["thread_id"]
    job = conn.execute("SELECT client_id FROM jobs WHERE job_id = ?", (proposal["job_id"],)).fetchone()
    thread_id = next_id(conn, "th")
    conn.execute(
        "INSERT INTO threads(thread_id, account_id, proposal_id, job_id, client_id, last_message_minute, unread)"
        " VALUES (?,?,?,?,?,?,0)",
        (thread_id, proposal["account_id"], proposal["proposal_id"], proposal["job_id"], job["client_id"], minute),
    )
    conn.execute("UPDATE proposals SET thread_id = ? WHERE proposal_id = ?", (thread_id, proposal["proposal_id"]))
    return thread_id


def _bump_status(conn: sqlite3.Connection, proposal: sqlite3.Row, status: str, minute: int) -> None:
    current = proposal["status"]
    if status == "declined":
        if current not in ("submitted", "viewed"):
            return
    elif current == "declined" or STATUS_RANK.get(current, 0) >= STATUS_RANK[status]:
        return
    conn.execute(
        "UPDATE proposals SET status = ?, updated_minute = ? WHERE proposal_id = ?",
        (status, minute, proposal["proposal_id"]),
    )


def _apply_scheduled(conn: sqlite3.Connection, item: sqlite3.Row) -> dict[str, Any]:
    data = loads(item["data"], {})
    at = item["at_minute"]
    thread_id = item["thread_id"]
    proposal = None
    if item["proposal_id"]:
        proposal = conn.execute("SELECT * FROM proposals WHERE proposal_id = ?", (item["proposal_id"],)).fetchone()
    type_ = item["type"]
    event_data: dict[str, Any] = {k: v for k, v in data.items() if k != "text"}

    if type_ in ("client_replied", "interview_requested") and data.get("text"):
        if thread_id is None and proposal is not None:
            thread_id = _ensure_thread(conn, proposal, at)
        message_id = insert_message(conn, thread_id, "client", data["text"], at)
        event_data["message_id"] = message_id
        event_data["preview"] = data["text"][:160]
    if proposal is not None:
        status = {
            "proposal_viewed": "viewed",
            "client_replied": "replied",
            "interview_requested": "interview",
            "hired": "hired",
            "declined": "declined",
        }.get(type_)
        if status:
            fresh = conn.execute("SELECT * FROM proposals WHERE proposal_id = ?", (proposal["proposal_id"],)).fetchone()
            _bump_status(conn, fresh, status, at)
    conn.execute("UPDATE scheduled SET applied = 1 WHERE id = ?", (item["id"],))
    return _insert_event(
        conn, account_id=item["account_id"], type_=type_, at=at, job_id=item["job_id"],
        proposal_id=item["proposal_id"], thread_id=thread_id, data=event_data,
    )


def process_due(conn: sqlite3.Connection, now: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Release due jobs and reveal due scheduled events, interleaved in time order.

    Returns (released_jobs, revealed_events) as raw rows (minutes, not ISO)."""
    due_jobs = conn.execute(
        "SELECT job_id, title, category, release_minute FROM jobs WHERE released = 0 AND release_minute <= ?",
        (now,),
    ).fetchall()
    due_events = conn.execute(
        "SELECT * FROM scheduled WHERE applied = 0 AND at_minute <= ? ORDER BY at_minute, id", (now,)
    ).fetchall()
    items: list[tuple[int, int, str, Any]] = []
    items += [(j["release_minute"], 0, j["job_id"], j) for j in due_jobs]
    items += [(e["at_minute"], 1, str(e["id"]).zfill(12), e) for e in due_events]
    items.sort(key=lambda t: (t[0], t[1], t[2]))

    released: list[dict[str, Any]] = []
    revealed: list[dict[str, Any]] = []
    for at, kind, _, row in items:
        if kind == 0:
            conn.execute("UPDATE jobs SET released = 1 WHERE job_id = ?", (row["job_id"],))
            ev = _insert_event(conn, account_id=None, type_="job_posted", at=at, job_id=row["job_id"],
                               data={"title": row["title"], "category": row["category"]})
            released.append(ev)
        else:
            revealed.append(_apply_scheduled(conn, row))
    return released, revealed


def _weekly_reset(conn: sqlite3.Connection, now: int) -> None:
    week = math.floor(now / MINUTES_PER_WEEK)
    last = int(meta_get(conn, "connects_week", "0") or 0)
    if week > last:
        conn.execute("UPDATE accounts SET connects_balance = MAX(connects_balance, weekly_allowance)")
        meta_set(conn, "connects_week", week)


def advance(conn: sqlite3.Connection, start: datetime, minutes: int) -> dict[str, Any]:
    now = now_minute(conn) + max(0, int(minutes))
    meta_set(conn, "clock_minute", now)
    released, revealed = process_due(conn, now)
    _weekly_reset(conn, now)
    return {
        "now": iso_at(start, now),
        "now_minute": now,
        "released_jobs": [r["job_id"] for r in released],
        "revealed_events": [event_public(e, start) for e in revealed],
    }


async def run_ticker(advance_fn, speed: float, interval: float = 1.0) -> None:
    """Advance the clock at `speed` sim minutes per real minute until cancelled."""
    carry = 0.0
    loop = asyncio.get_running_loop()
    last = loop.time()
    while True:
        await asyncio.sleep(interval)
        current = loop.time()
        carry += (current - last) / 60.0 * speed
        last = current
        whole = int(carry)
        if whole >= 1:
            carry -= whole
            try:
                await asyncio.to_thread(advance_fn, whole)
            except Exception:  # keep ticking; the next tick retries
                log.exception("clock tick failed")
