# ADR 0004: Arq on Redis for background work

- Status: accepted
- Plan reference: D24 in `PLAN.md`

## Context

Scouting and agent runs take tens of seconds and must not run inside web requests (E1). Saved
searches need schedules. LangGraph and the MCP clients are async. A worker restart must never
double-analyse a job or double-submit a proposal.

## Decision

Arq (`worker/main.py` `WorkerSettings`, tasks in `worker/tasks.py`).

- Tasks: `run_start`, `run_resume`, `run_update`, `scout_user`, `analyse_job`, `sync_events`,
  `retry_queued`.
- Cron: `scheduled_scout` every 15 min (each user's interval is enforced inside the task),
  `scheduled_sync` every 5 min, `retry_queued` every minute.
- `max_jobs = 4`, `job_timeout = 900` s.
- Idempotency: `analyse_job` returns early if the bid thread already has a checkpoint. Bid threads
  are keyed by job. Marketplace writes carry idempotency keys (`docs/ARCHITECTURE.md` §7).
- Local fallback: `apps/api/jobs_queue.py` runs the same task functions as asyncio tasks in the
  API when `WORKER_MODE=inline` or `REDIS_URL` is unset. `scripts/dev.py` uses this.

## Alternatives rejected

- **Celery.** Sync-first, awkward with async LangGraph code, and heavier.
- **Dramatiq.** No native async and no built-in cron.
- **FastAPI background tasks only.** Work dies with the request process and cannot be scheduled.
  Kept only as the inline dev mode.

## Consequences

- One small dependency, async end to end, cron included.
- Arq runs pessimistically: a job stays in Redis until it finishes, so a crashed job runs again.
  Correctness on a re-run comes from the checkpoint and the idempotency keys, not from the queue.
- In the HF Space the worker uses Upstash Redis. Its free-tier request quota is consumed by the
  cron polling as well as by real work.
