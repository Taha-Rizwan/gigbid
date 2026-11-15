"""Single-container mode: advance the mounted GigSim clock and sync marketplace events on a timer
(the job the Arq worker's cron does in the full deployment)."""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

log = logging.getLogger("gigbid.ticker")


async def run(every_s: int = 300, sim_minutes: int = 60) -> None:
    base = os.environ.get("GIGSIM_BASE_URL", "http://127.0.0.1:8000/gigsim")
    token = os.environ.get("GIGSIM_ADMIN_TOKEN", "gigsim-admin")
    while True:
        await asyncio.sleep(every_s)
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                await c.post(f"{base}/admin/clock/advance", headers={"X-Admin-Token": token}, json={"minutes": sim_minutes})
            from worker import tasks

            await tasks.scheduled_sync({})
        except Exception as exc:  # noqa: BLE001
            log.warning("simulator tick failed: %s", exc)
