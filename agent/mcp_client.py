"""MCP client setup and per-agent tool allowlists (A6).

Agents never call GigSim, Upwork, a database or files directly: every capability is an MCP tool.
Each agent gets only the tools on its allowlist. Calls have timeouts, bounded retries with
backoff, and raise MarketplaceUnavailable when the marketplace server is down, which the API
turns into the degraded-mode banner and a queued job.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from contextlib import AsyncExitStack
from typing import Any

from langchain_core.tools import BaseTool

from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable

ALLOWLIST: dict[str, set[str]] = {
    "scout": {"search_jobs", "get_events"},
    "intake": {"get_job"},
    "risk_assessor": {"get_client_history"},
    "fit_matcher": {"search_evidence", "get_case_study"},
    "pricing": {"get_market_stats", "get_connects_balance", "get_policy"},
    "writer": {"search_evidence", "get_case_study"},
    "verifier": {"search_evidence"},
    "critic": {"search_evidence"},
    "compliance": set(),  # no MCP access, by design
    "submitter": {"create_proposal_draft", "submit_proposal", "get_connects_balance"},
    "liaison": {"list_threads", "list_messages", "free_slots", "create_interview_hold", "create_email_draft"},
    "messenger": {"send_message"},
    "tracker": {"list_proposals", "get_events", "list_threads"},
}

SERVER_OF = {
    "search_jobs": "marketplace", "get_job": "marketplace", "get_client_history": "marketplace",
    "get_connects_balance": "marketplace", "get_market_stats": "marketplace", "get_policy": "marketplace",
    "list_proposals": "marketplace", "list_threads": "marketplace", "list_messages": "marketplace",
    "get_events": "marketplace", "create_proposal_draft": "marketplace", "submit_proposal": "marketplace",
    "send_message": "marketplace",
    "search_evidence": "portfolio", "get_case_study": "portfolio", "list_skills": "portfolio",
    "free_slots": "workspace", "create_interview_hold": "workspace", "create_email_draft": "workspace",
}


def connections(user_id: str, trace_id: str | None = None) -> dict[str, dict[str, Any]]:
    token = os.environ.get("MCP_AUTH_TOKEN", "dev-mcp-token")
    headers = {"Authorization": f"Bearer {token}", "X-GigBid-User": user_id, "X-Trace-Id": trace_id or ""}
    return {
        name: {"transport": "streamable_http", "url": os.environ.get(f"MCP_{name.upper()}_URL", default),
               "headers": headers, "timeout": 30}
        for name, default in [
            ("marketplace", "http://127.0.0.1:8101/mcp"),
            ("portfolio", "http://127.0.0.1:8102/mcp"),
            ("workspace", "http://127.0.0.1:8103/mcp"),
        ]
    }


def _parse(result: Any) -> Any:
    """Tool results come back as text/JSON content; decode to Python objects."""
    if isinstance(result, tuple):  # (content, artifact)
        result = result[0]
    if isinstance(result, list):
        texts = [r.get("text") if isinstance(r, dict) else getattr(r, "text", r) for r in result]
        result = texts[0] if len(texts) == 1 else texts
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return result
    return result


class ToolBox:
    """All MCP tools for one user/run, handed out per agent by allowlist."""

    def __init__(self, tools: dict[str, BaseTool], timeout: float = 30, retries: int = 2):
        self.tools, self.timeout, self.retries = tools, timeout, retries

    @classmethod
    async def http(cls, user_id: str, trace_id: str | None = None) -> ToolBox:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        conns = connections(user_id, trace_id)
        tools: dict[str, BaseTool] = {}
        for server in conns:
            try:
                for t in await MultiServerMCPClient({server: conns[server]}).get_tools(server_name=server):
                    tools[t.name] = t
            except Exception:  # noqa: BLE001 - a dead server just means its tools are missing
                continue
        return cls(tools)

    @classmethod
    async def in_memory(cls, stack: AsyncExitStack, servers: list[Any] | None = None) -> ToolBox:
        """In-process MCP sessions (tests, evals): same protocol, no network."""
        from langchain_mcp_adapters.tools import load_mcp_tools
        from mcp.shared.memory import create_connected_server_and_client_session as connect

        if servers is None:
            from mcp_servers.marketplace.server import mcp as m
            from mcp_servers.portfolio.server import mcp as p
            from mcp_servers.workspace.server import mcp as w

            servers = [m, p, w]
        tools: dict[str, BaseTool] = {}
        for s in servers:
            session = await stack.enter_async_context(connect(s._mcp_server))
            for t in await load_mcp_tools(session):
                tools[t.name] = t
        return cls(tools)

    def for_agent(self, agent: str) -> AgentTools:
        allowed = ALLOWLIST[agent]
        return AgentTools(agent, {n: t for n, t in self.tools.items() if n in allowed}, self)

    def available(self, server: str) -> bool:
        return any(SERVER_OF.get(n) == server for n in self.tools)


class AgentTools:
    def __init__(self, agent: str, tools: dict[str, BaseTool], box: ToolBox):
        self.agent, self.tools, self.box = agent, tools, box

    def langchain_tools(self) -> list[BaseTool]:
        return list(self.tools.values())

    async def call(self, name: str, **args: Any) -> Any:
        if name not in ALLOWLIST[self.agent]:
            raise PermissionError(f"agent '{self.agent}' may not call '{name}'")
        tool = self.tools.get(name)
        if tool is None:
            if SERVER_OF.get(name) == "marketplace":
                raise MarketplaceUnavailable(f"marketplace MCP server is not reachable ({name})")
            raise RuntimeError(f"MCP tool {name} unavailable (server {SERVER_OF.get(name)} down?)")
        last: Exception | None = None
        for attempt in range(self.box.retries + 1):
            try:
                out = _parse(await asyncio.wait_for(tool.ainvoke(args), self.box.timeout))
                if isinstance(out, str):  # adapters return tool errors as text; our tools always return JSON
                    raise RuntimeError(out)
                return out
            except (TimeoutError, ConnectionError, OSError) as exc:
                last = exc
            except Exception as exc:  # noqa: BLE001 - tool errors carry our JSON error payload
                err = _tool_error(exc)
                if err and err.get("error") in ("marketplace_unavailable", "upstream_unavailable"):
                    last = MarketplaceUnavailable(err.get("detail", ""))
                elif err and err.get("error") == "rate_limited":
                    last = MarketplaceError("rate_limited", err.get("detail", ""), 429, err.get("retry_after"))
                    await asyncio.sleep(min(float(err.get("retry_after") or 1), 10))
                    continue
                elif err:
                    raise MarketplaceError(err.get("error", "error"), err.get("detail", ""), int(err.get("status") or 400), data=err) from exc
                elif "connect" in str(exc).lower() or "closed" in str(exc).lower():
                    last = exc
                else:
                    raise
            if attempt < self.box.retries:
                await asyncio.sleep(min(6, 0.5 * 2**attempt) + random.random() * 0.2)
        if SERVER_OF.get(name) == "marketplace":
            raise MarketplaceUnavailable(f"{name} failed after retries: {type(last).__name__}: {last}")
        raise RuntimeError(f"{name} failed after retries: {type(last).__name__}: {last}")


def _tool_error(exc: Exception) -> dict | None:
    text = str(exc)
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj = json.loads(text[start: text.rfind("}") + 1])
        return obj if isinstance(obj, dict) and "error" in obj else None
    except ValueError:
        return None
