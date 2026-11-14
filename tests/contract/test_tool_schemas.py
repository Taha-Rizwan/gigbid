"""Contract test: fails CI when an MCP tool signature changes unintentionally.

Update snapshots deliberately with:  UPDATE_SNAPSHOTS=1 pytest tests/contract
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.marketplace.server import mcp as marketplace
from mcp_servers.portfolio.server import mcp as portfolio
from mcp_servers.workspace.server import mcp as workspace

SNAP = Path(__file__).parent / "snapshots"


async def _surface(server) -> dict:
    async with connect(server._mcp_server) as c:
        tools = (await c.list_tools()).tools
        out = {"tools": {}}
        for t in sorted(tools, key=lambda t: t.name):
            out["tools"][t.name] = {
                "description": (t.description or "").strip(),
                "input_schema": t.inputSchema,
                "output_schema": t.outputSchema,
                "annotations": t.annotations.model_dump(exclude_none=True) if t.annotations else None,
            }
        out["resource_templates"] = sorted(r.uriTemplate for r in (await c.list_resource_templates()).resourceTemplates)
        out["prompts"] = sorted(p.name for p in (await c.list_prompts()).prompts)
        return out


@pytest.mark.parametrize("name,server", [("marketplace", marketplace), ("portfolio", portfolio), ("workspace", workspace)])
async def test_tool_surface_matches_snapshot(name, server):
    surface = await _surface(server)
    path = SNAP / f"{name}.json"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not path.exists():
        SNAP.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(surface, indent=1, sort_keys=True), encoding="utf-8")
        if os.environ.get("UPDATE_SNAPSHOTS") != "1":
            pytest.skip("snapshot created")
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert surface == expected, f"MCP tool surface of '{name}' changed; if intended, run UPDATE_SNAPSHOTS=1"


async def test_write_tools_are_annotated_correctly():
    surface = await _surface(marketplace)
    tools = surface["tools"]
    for name in ("create_proposal_draft", "submit_proposal", "send_message"):
        ann = tools[name]["annotations"]
        assert ann["readOnlyHint"] is False and ann["idempotentHint"] is True
        assert "idempotency_key" in tools[name]["input_schema"]["required"]
        assert "dry_run" in tools[name]["input_schema"]["properties"]
    assert tools["submit_proposal"]["annotations"]["destructiveHint"] is True
    for name, t in tools.items():
        if name.startswith(("get_", "list_", "search_")):
            assert t["annotations"]["readOnlyHint"] is True, name
