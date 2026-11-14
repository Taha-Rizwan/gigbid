"""Shared plumbing for GigBid's own MCP servers over Streamable HTTP:
bearer auth, per-user rate limiting, request context (user, tenant, trace id) and the
append-only audit log."""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from common.security import mask_obj

log = logging.getLogger("gigbid.mcp")

request_user: contextvars.ContextVar[str] = contextvars.ContextVar("request_user", default="anonymous")
request_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_trace", default=None)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Rejects requests without the shared bearer token; captures user and trace headers."""

    def __init__(self, app, token: str | None = None):
        super().__init__(app)
        self.token = token or os.environ.get("MCP_AUTH_TOKEN", "dev-mcp-token")

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {self.token}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        request_user.set(request.headers.get("x-gigbid-user", "anonymous"))
        request_trace.set(request.headers.get("x-trace-id"))
        return await call_next(request)


class RateLimiter:
    """Per-user token bucket, kept below the marketplace's own limit."""

    def __init__(self, per_minute: int):
        self.rate = per_minute / 60.0
        self.capacity = max(1, per_minute // 4)
        self.state: dict[str, tuple[float, float]] = defaultdict(lambda: (self.capacity, time.monotonic()))
        self.lock = asyncio.Lock()

    async def acquire(self, user: str) -> None:
        while True:
            async with self.lock:
                tokens, last = self.state[user]
                now = time.monotonic()
                tokens = min(self.capacity, tokens + (now - last) * self.rate)
                if tokens >= 1:
                    self.state[user] = (tokens - 1, now)
                    return
                self.state[user] = (tokens, now)
                wait = (1 - tokens) / self.rate
            await asyncio.sleep(wait)


async def audit(server: str, tool: str, args: dict[str, Any], result: Any, ok: bool) -> None:
    """Append-only: rows are only ever inserted. Arguments and results are PII-masked."""
    row = (
        request_user.get(), server, tool,
        json.dumps(mask_obj(args), default=str)[:20000],
        json.dumps(mask_obj(result), default=str)[:20000],
        ok, request_trace.get(),
    )
    try:
        from common import db

        await db.execute(
            "insert into audit_log (user_id, server, tool, args, result, ok, trace_id) values (%s,%s,%s,%s,%s,%s,%s)",
            *row,
        )
    except Exception as exc:  # noqa: BLE001 - audit must never break the tool call
        log.warning("audit write failed: %s", exc)
