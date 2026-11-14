"""Arq worker: scheduled scouting, long agent runs, event sync and degraded-mode retries.

Run: arq worker.main.WorkerSettings
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from arq import cron
from arq.connections import RedisSettings

import common  # noqa: F401
from worker import tasks


def redis_settings() -> RedisSettings:
    u = urlparse(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return RedisSettings(host=u.hostname or "localhost", port=u.port or 6379, password=u.password,
                         username=u.username if u.username not in (None, "default") else None,
                         ssl=u.scheme == "rediss", database=int((u.path or "/0").strip("/") or 0),
                         conn_timeout=10, conn_retries=5)


async def startup(ctx: dict) -> None:
    from common import db
    from common.security import install_log_masking

    install_log_masking()
    await db.migrate()
    await tasks._ensure_engine()


async def shutdown(ctx: dict) -> None:
    from apps.api.runs import engine
    from common import db

    await engine.close()
    await db.close()


class WorkerSettings:
    functions = [tasks.run_start, tasks.run_resume, tasks.run_update, tasks.scout_user, tasks.analyse_job,
                 tasks.sync_events, tasks.retry_queued]
    cron_jobs = [
        cron(tasks.scheduled_scout, minute=set(range(0, 60, 15)), run_at_startup=False),
        cron(tasks.scheduled_sync, minute=set(range(0, 60, 5))),
        cron(tasks.retry_queued, minute=set(range(60))),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings()
    max_jobs = 4
    job_timeout = 900
    keep_result = 3600
    allow_abort_jobs = True
