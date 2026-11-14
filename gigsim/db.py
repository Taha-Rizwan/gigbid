"""SQLite storage: schema and small helpers.

Thread safety: every unit of work opens its own connection inside `Store.tx()`, which also holds a
process-wide re-entrant lock and runs in a `BEGIN IMMEDIATE` transaction. Never call `tx()` while
another `tx()` is open on the same thread (the second connection would wait on the first).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT,
    hourly_rate REAL,
    skills TEXT NOT NULL DEFAULT '[]',
    success_score REAL NOT NULL DEFAULT 0.8,
    token TEXT NOT NULL UNIQUE,
    connects_balance INTEGER NOT NULL DEFAULT 0,
    weekly_allowance INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    member_since TEXT,
    total_spent REAL,
    jobs_posted INTEGER,
    hires INTEGER,
    avg_rating REAL,
    payment_verified INTEGER NOT NULL DEFAULT 0,
    reviews TEXT NOT NULL DEFAULT '[]',
    hidden TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    skills TEXT NOT NULL DEFAULT '[]',
    is_hourly INTEGER NOT NULL DEFAULT 0,
    hourly_low REAL,
    hourly_high REAL,
    budget REAL,
    country TEXT,
    client_id TEXT NOT NULL,
    release_minute INTEGER NOT NULL DEFAULT 0,
    base_proposals INTEGER NOT NULL DEFAULT 0,
    sim_proposals INTEGER NOT NULL DEFAULT 0,
    screening_questions TEXT NOT NULL DEFAULT '[]',
    experience_level TEXT,
    is_scam INTEGER NOT NULL DEFAULT 0,
    has_injection INTEGER NOT NULL DEFAULT 0,
    duplicate_of TEXT,
    source TEXT,
    released INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_released ON jobs(released, release_minute);
CREATE TABLE IF NOT EXISTS drafts (
    draft_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    cover_letter TEXT NOT NULL,
    screening_answers TEXT NOT NULL DEFAULT '[]',
    bid_amount REAL NOT NULL,
    rate_type TEXT NOT NULL,
    connects_cost INTEGER NOT NULL,
    created_minute INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    cover_letter TEXT NOT NULL,
    screening_answers TEXT NOT NULL DEFAULT '[]',
    bid_amount REAL NOT NULL,
    rate_type TEXT NOT NULL,
    connects_spent INTEGER NOT NULL,
    status TEXT NOT NULL,
    submitted_minute INTEGER NOT NULL,
    updated_minute INTEGER NOT NULL,
    thread_id TEXT,
    outcome TEXT NOT NULL,
    score TEXT NOT NULL DEFAULT '{}',
    UNIQUE(account_id, job_id)
);
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    last_message_minute INTEGER NOT NULL,
    unread INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    text TEXT NOT NULL,
    sent_minute INTEGER NOT NULL,
    seq INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, seq);
CREATE TABLE IF NOT EXISTS scheduled (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    type TEXT NOT NULL,
    at_minute INTEGER NOT NULL,
    job_id TEXT,
    proposal_id TEXT,
    thread_id TEXT,
    data TEXT NOT NULL DEFAULT '{}',
    applied INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_scheduled_due ON scheduled(applied, at_minute);
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    type TEXT NOT NULL,
    at_minute INTEGER NOT NULL,
    job_id TEXT,
    proposal_id TEXT,
    thread_id TEXT,
    data TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS idempotency (
    account_id TEXT NOT NULL,
    idem_key TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    response TEXT NOT NULL,
    PRIMARY KEY (account_id, idem_key)
);
CREATE TABLE IF NOT EXISTS llm_cache (
    hash TEXT PRIMARY KEY,
    value TEXT
);
"""

# Tables wiped by /admin/reset. llm_cache survives resets on purpose: it only saves API calls.
RESET_TABLES = (
    "meta", "accounts", "clients", "jobs", "drafts", "proposals", "threads", "messages",
    "scheduled", "events", "idempotency",
)


def _statements(script: str) -> list[str]:
    return [s.strip() for s in script.split(";") if s.strip()]


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.lock = threading.RLock()

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as conn:
            create_schema(conn)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    yield conn
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
                conn.execute("COMMIT")
            finally:
                conn.close()


def create_schema(conn: sqlite3.Connection) -> None:
    for stmt in _statements(SCHEMA):
        conn.execute(stmt)


def drop_resettable(conn: sqlite3.Connection) -> None:
    for table in RESET_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    create_schema(conn)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads(value: str | None, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


def meta_get(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def meta_set(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def next_id(conn: sqlite3.Connection, prefix: str) -> str:
    """Sequential, human-readable ids (dr_000001, pr_000001, ...). Deterministic per reset."""
    key = f"seq:{prefix}"
    n = int(meta_get(conn, key, "0") or 0) + 1
    meta_set(conn, key, n)
    return f"{prefix}_{n:06d}"
