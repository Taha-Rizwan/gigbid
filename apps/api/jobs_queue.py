"""Long agent runs never execute inside web requests: they go to the Arq worker on Redis.
WORKER_MODE=inline runs them as background tasks in the API process (local dev without Redis)."""

from __future__ import annotations

import asyncio
import logging
import os

log = logging.getLogger("gigbid.queue")
_pool = None
_inline_tasks: set[asyncio.Task] = set()


async def _redis():
    global _pool
    if _pool is None:
        from arq import create_pool

        from worker.main import redis_settings

        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(task: str, *args) -> None:
    if os.environ.get("WORKER_MODE", "arq") == "inline" or not os.environ.get("REDIS_URL"):
        from worker import tasks

        t = asyncio.create_task(getattr(tasks, task)({}, *args))
        _inline_tasks.add(t)
        t.add_done_callback(_inline_tasks.discard)
        return
    pool = await _redis()
    await pool.enqueue_job(task, *args)
