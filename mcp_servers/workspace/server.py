"""Workspace MCP server: free calendar slots, tentative interview holds and email drafts.

Backed by a documented local mock (Postgres table `workspace_items` plus a working-hours calendar),
not Google APIs: GigBid only needs proposed slots and drafts, and the agent sees MCP tools either way.
Swapping in Google Calendar/Gmail means replacing the three functions marked BACKEND.

Run: python -m mcp_servers.workspace.server   (HTTP :8103/mcp, bearer auth)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from common import db
from common.mcp_http import BearerAuthMiddleware, audit, request_user

SERVER = "workspace"
mcp = FastMCP("gigbid-workspace", instructions="Calendar availability, interview holds and email drafts.",
              stateless_http=True, json_response=True)
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)

WORK_START, WORK_END = 9, 18


class Slot(BaseModel):
    start: str
    end: str
    label: str


class Hold(BaseModel):
    hold_id: str
    start: str
    end: str
    title: str
    status: str = "tentative"


class EmailDraft(BaseModel):
    draft_id: str
    to: str
    subject: str
    body: str
    status: str = "draft"


async def _busy(user: str) -> list[tuple[datetime, datetime]]:  # BACKEND
    rows = await db.fetch("select data from workspace_items where user_id=%s and kind='hold'", user)
    return [(datetime.fromisoformat(r["data"]["start"]), datetime.fromisoformat(r["data"]["end"])) for r in rows]


@mcp.tool(annotations=READ)
async def free_slots(
    days_ahead: Annotated[int, Field(ge=1, le=14)] = 5,
    duration_minutes: Annotated[int, Field(ge=15, le=180)] = 30,
    timezone: str = "Asia/Karachi",
    max_slots: Annotated[int, Field(ge=1, le=10)] = 3,
) -> list[Slot]:
    """Free interview slots in working hours over the next days, avoiding existing holds."""
    user = request_user.get()
    tz = ZoneInfo(timezone)
    busy = await _busy(user)
    now = datetime.now(tz)
    out: list[Slot] = []
    day = now.date()
    while len(out) < max_slots and (day - now.date()).days <= days_ahead:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue
        for hour in (WORK_START + 1, 13, 16):
            start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz)
            end = start + timedelta(minutes=duration_minutes)
            if end.hour > WORK_END or any(s < end and start < e for s, e in busy):
                continue
            out.append(Slot(start=start.isoformat(), end=end.isoformat(),
                            label=start.strftime("%a %d %b, %H:%M ") + timezone))
            break
    await audit(SERVER, "free_slots", {"days_ahead": days_ahead}, {"n": len(out)}, True)
    return out


@mcp.tool(annotations=WRITE)
async def create_interview_hold(
    start: Annotated[str, Field(description="ISO datetime")],
    duration_minutes: Annotated[int, Field(ge=15, le=180)] = 30,
    title: Annotated[str, Field(max_length=200)] = "Client interview (tentative)",
) -> Hold:
    """Place a tentative calendar hold for a proposed interview slot."""
    user = request_user.get()
    s = datetime.fromisoformat(start)
    hold = Hold(hold_id=uuid.uuid4().hex[:12], start=s.isoformat(),
                end=(s + timedelta(minutes=duration_minutes)).isoformat(), title=title)
    await db.execute("insert into workspace_items (id, user_id, kind, data) values (%s,%s,'hold',%s)",  # BACKEND
                     hold.hold_id, user, json.dumps(hold.model_dump()))
    await audit(SERVER, "create_interview_hold", hold.model_dump(), {"ok": True}, True)
    return hold


@mcp.tool(annotations=WRITE)
async def create_email_draft(
    to: Annotated[str, Field(max_length=200)],
    subject: Annotated[str, Field(max_length=300)],
    body: Annotated[str, Field(max_length=10000)],
) -> EmailDraft:
    """Save an email draft (never sent automatically)."""
    user = request_user.get()
    d = EmailDraft(draft_id=uuid.uuid4().hex[:12], to=to, subject=subject, body=body)
    await db.execute("insert into workspace_items (id, user_id, kind, data) values (%s,%s,'email_draft',%s)",  # BACKEND
                     d.draft_id, user, json.dumps({**d.model_dump(), "created_at": datetime.now(UTC).isoformat()}))
    await audit(SERVER, "create_email_draft", {"to": to, "subject": subject}, {"draft_id": d.draft_id}, True)
    return d


def app():
    a = mcp.streamable_http_app()
    a.add_middleware(BearerAuthMiddleware)
    return a


if __name__ == "__main__":
    from common import serve
    from common.security import install_log_masking

    install_log_masking()
    serve(app(), host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("MCP_WORKSPACE_PORT", 8103)))
