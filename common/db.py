"""Postgres access shared by the API, worker and MCP servers. Every query that touches user data
filters on user_id (the tenant)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from agent.settings import ROOT

load_dotenv(ROOT / ".env")

SCHEMA = """
create table if not exists users (
  user_id text primary key, email text unique not null, name text not null,
  password_hash text not null, created_at timestamptz default now());
create table if not exists profiles (
  user_id text primary key references users(user_id) on delete cascade,
  data jsonb not null default '{}', gigsim_token text, updated_at timestamptz default now());
create table if not exists searches (
  search_id text primary key, user_id text not null references users(user_id) on delete cascade,
  data jsonb not null, last_run_at timestamptz);
create table if not exists oauth_tokens (
  user_id text not null references users(user_id) on delete cascade, provider text not null,
  enc_token bytea not null, updated_at timestamptz default now(), primary key (user_id, provider));
create table if not exists oauth_states (
  state text primary key, user_id text not null, verifier text not null, created_at timestamptz default now());
create table if not exists jobs (
  user_id text not null, job_id text not null, job jsonb not null, status text not null default 'new',
  analysis jsonb not null default '{}', thread_id text, fit_score real, risk_score real,
  recommendation text, price real, connects_cost int, posted_at timestamptz,
  created_at timestamptz default now(), updated_at timestamptz default now(),
  primary key (user_id, job_id));
create index if not exists jobs_user_status on jobs (user_id, status);
create table if not exists runs (
  run_id text primary key, user_id text not null, thread_id text not null, graph text not null,
  job_id text, status text not null, started_at timestamptz default now(), finished_at timestamptz,
  tokens int default 0, cost_usd real default 0, latency_s real, trace_url text, usage jsonb);
create index if not exists runs_user on runs (user_id, started_at desc);
create table if not exists run_events (
  run_id text not null, seq int not null, at timestamptz default now(), node text, kind text,
  summary text, data jsonb, primary key (run_id, seq));
create table if not exists proposals (
  user_id text not null, thread_id text not null, job_id text not null, draft_id text, proposal_id text,
  stage text not null default 'drafted', bid_amount real, connects_spent int, category text,
  conversation_id text, data jsonb default '{}', updated_at timestamptz default now(),
  primary key (user_id, thread_id));
create table if not exists conversations (
  user_id text not null, conversation_id text not null, job_id text, proposal_id text,
  graph_thread_id text, state jsonb default '{}', last_seen_message text, updated_at timestamptz default now(),
  primary key (user_id, conversation_id));
create table if not exists feedback (
  id bigserial primary key, user_id text not null, thread_id text not null, action text not null,
  reason text, diff jsonb, at timestamptz default now());
create table if not exists audit_log (
  id bigserial primary key, at timestamptz default now(), user_id text, server text, tool text,
  args jsonb, result jsonb, ok boolean, trace_id text);
create table if not exists idempotency (
  user_id text not null, tool text not null, key text not null, request_hash text not null,
  response jsonb not null, at timestamptz default now(), primary key (user_id, tool, key));
create table if not exists work_queue (
  id bigserial primary key, user_id text not null, kind text not null, payload jsonb not null,
  status text not null default 'queued', attempts int default 0, last_error text,
  next_at timestamptz default now(), created_at timestamptz default now());
create table if not exists events_cursor (
  user_id text primary key, cursor bigint not null default 0, updated_at timestamptz default now());
create table if not exists workspace_items (
  id text primary key, user_id text not null, kind text not null, data jsonb not null,
  created_at timestamptz default now());
"""

_pool: AsyncConnectionPool | None = None


def dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


async def pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            dsn(), min_size=1, max_size=8, open=False,
            kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None},
        )
        await _pool.open()
    return _pool


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def conn():
    p = await pool()
    async with p.connection() as c:
        yield c


async def fetch(sql: str, *args) -> list[dict]:
    async with conn() as c:
        cur = await c.execute(sql, args)
        return await cur.fetchall() if cur.description else []


async def fetchrow(sql: str, *args) -> dict | None:
    rows = await fetch(sql, *args)
    return rows[0] if rows else None


async def execute(sql: str, *args) -> None:
    async with conn() as c:
        await c.execute(sql, args)


async def migrate() -> None:
    async with conn() as c:
        await c.execute(SCHEMA)
