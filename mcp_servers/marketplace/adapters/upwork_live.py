"""Live adapter: the official Upwork MCP server (https://mcp.upwork.com/mcp, OAuth 2.1 + PKCE)
reached through MultiServerMCPClient over Streamable HTTP, mapped onto the marketplace port.

Platform rules enforced here, not just in prompts:
- reads only (search, job details, messages), on the conservative schedule in config;
- proposals and messages are created only as **drafts**; the user confirms them on Upwork;
- no browser automation, no cookies, no scraping.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
from typing import Any

import httpx

from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable
from agent.settings import config

UPWORK_MCP = "https://mcp.upwork.com/mcp"
RESOURCE_METADATA = "https://mcp.upwork.com/.well-known/oauth-protected-resource/mcp"

# Upwork's tool names are discovered at connect time; these keyword rules map them onto the port.
# Exact names can be pinned in agent/config.yaml under marketplace.upwork_tool_map once observed.
TOOL_RULES: dict[str, list[list[str]]] = {
    "search_jobs": [["search", "job"], ["find", "job"]],
    "get_job": [["get", "job"], ["job", "detail"]],
    "get_client_history": [["client"], ["buyer"]],
    "get_connects_balance": [["connect"]],
    "list_proposals": [["list", "proposal"], ["get", "proposal"]],
    "list_threads": [["room"], ["thread"], ["conversation"]],
    "list_messages": [["message"]],
    "create_proposal_draft": [["draft", "proposal"], ["create", "proposal"]],
    "send_message": [["draft", "message"], ["send", "message"]],
}


# ----------------------------- OAuth 2.1 (PKCE + client id metadata document) ------------------

async def discover() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as c:
        prm = (await c.get(RESOURCE_METADATA)).json()
        issuer = prm["authorization_servers"][0].rstrip("/")
        asm = (await c.get(f"{issuer}/.well-known/oauth-authorization-server")).json()
    return {"resource": prm["resource"], **asm}


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def client_id_for(public_base_url: str, configured: str | None) -> str:
    """Upwork supports client ID metadata documents: our client_id is the URL of a JSON document
    we host (apps/api serves it). A pre-registered client id can be configured instead."""
    return configured or f"{public_base_url.rstrip('/')}/api/oauth/upwork/client-metadata.json"


def client_metadata(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    return {
        "client_id": f"{base}/api/oauth/upwork/client-metadata.json",
        "client_name": "GigBid",
        "client_uri": base,
        "redirect_uris": [f"{base}/api/oauth/upwork/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


async def authorize_url(public_base_url: str, client_id: str | None, state: str, challenge: str) -> str:
    meta = await discover()
    q = {
        "response_type": "code",
        "client_id": client_id_for(public_base_url, client_id),
        "redirect_uri": f"{public_base_url.rstrip('/')}/api/oauth/upwork/callback",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": meta["resource"],
    }
    return f"{meta['authorization_endpoint']}?{urllib.parse.urlencode(q)}"


async def exchange_code(public_base_url: str, client_id: str | None, client_secret: str | None,
                        code: str, verifier: str) -> dict[str, Any]:
    meta = await discover()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"{public_base_url.rstrip('/')}/api/oauth/upwork/callback",
        "client_id": client_id_for(public_base_url, client_id),
        "code_verifier": verifier,
        "resource": meta["resource"],
    }
    if client_secret:
        data["client_secret"] = client_secret
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(meta["token_endpoint"], data=data)
    if r.status_code >= 400:
        raise MarketplaceError("oauth_failed", r.text[:300], r.status_code)
    tok = r.json()
    tok["obtained_at"] = time.time()
    return tok


async def refresh(public_base_url: str, client_id: str | None, tokens: dict[str, Any]) -> dict[str, Any]:
    meta = await discover()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(meta["token_endpoint"], data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
            "client_id": client_id_for(public_base_url, client_id), "resource": meta["resource"],
        })
    if r.status_code >= 400:
        raise MarketplaceError("oauth_refresh_failed", r.text[:300], r.status_code)
    new = r.json()
    new.setdefault("refresh_token", tokens.get("refresh_token"))
    new["obtained_at"] = time.time()
    return new


# ----------------------------------------- adapter ---------------------------------------------

class UpworkLiveAdapter:
    name = "upwork_live"

    def __init__(self, access_token: str, url: str = UPWORK_MCP):
        self.url, self.access_token = url, access_token
        self._tools: dict[str, Any] | None = None
        self._map: dict[str, str] = {}

    async def _load(self) -> dict[str, Any]:
        if self._tools is not None:
            return self._tools
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient({"upwork": {
            "transport": "streamable_http", "url": self.url,
            "headers": {"Authorization": f"Bearer {self.access_token}"},
        }})
        try:
            tools = await client.get_tools()
        except Exception as exc:  # noqa: BLE001
            raise MarketplaceUnavailable(f"upwork mcp: {type(exc).__name__}: {exc}") from exc
        self._tools = {t.name: t for t in tools}
        pinned = config()["marketplace"].get("upwork_tool_map") or {}
        for port_name, rules in TOOL_RULES.items():
            if port_name in pinned and pinned[port_name] in self._tools:
                self._map[port_name] = pinned[port_name]
                continue
            for rule in rules:
                hit = next((n for n in self._tools if all(w in n.lower() for w in rule)), None)
                if hit:
                    self._map[port_name] = hit
                    break
        return self._tools

    async def _call(self, port_name: str, args: dict[str, Any]) -> Any:
        tools = await self._load()
        name = self._map.get(port_name)
        if not name:
            raise MarketplaceError("not_supported", f"Upwork MCP has no tool for {port_name}", 501,
                                   data={"available_tools": sorted(tools)})
        tool = tools[name]
        accepted = set((tool.args_schema or {}).get("properties", {}) if isinstance(tool.args_schema, dict)
                       else getattr(tool.args_schema, "model_fields", {}))
        call_args = {k: v for k, v in args.items() if v is not None and (not accepted or k in accepted)}
        out = await tool.ainvoke(call_args)
        if isinstance(out, str):
            try:
                return json.loads(out)
            except ValueError:
                return {"text": out}
        return out

    def tool_map(self) -> dict[str, str]:
        return dict(self._map)

    # ---- read ----
    async def search_jobs(self, query="", category=None, limit=20, offset=0, posted_after=None):
        out = await self._call("search_jobs", {"query": query, "q": query, "limit": limit, "category": category})
        jobs = out.get("jobs", out) if isinstance(out, dict) else out
        return {"jobs": [_norm_job(j) for j in (jobs or [])], "total": len(jobs or [])}

    async def get_job(self, job_id):
        return _norm_job(await self._call("get_job", {"job_id": job_id, "id": job_id}))

    async def get_client_history(self, client_id):
        try:
            return await self._call("get_client_history", {"client_id": client_id})
        except MarketplaceError:
            return {"client_id": client_id, "note": "client history not exposed by the live marketplace"}

    async def get_connects_balance(self):
        try:
            return await self._call("get_connects_balance", {})
        except MarketplaceError:
            return {"balance": None, "note": "Connects balance is shown on Upwork when you confirm the draft"}

    async def get_market_stats(self, category=None):
        # Upwork exposes no market statistics; fall back to the offline Kaggle-derived stats.
        from pathlib import Path

        p = Path(__file__).resolve().parents[3] / "data" / "processed" / "market_stats.json"
        stats = json.loads(p.read_text()) if p.exists() else {}
        return stats.get(category or "_all", stats.get("_all", {}))

    async def get_policy(self):
        return {"version": "upwork", "rules": ["Upwork Terms of Service and automation guidelines apply"],
                "required_disclosure": None}

    async def list_proposals(self, status=None):
        out = await self._call("list_proposals", {"status": status})
        return out.get("proposals", out) if isinstance(out, dict) else out

    async def list_threads(self):
        out = await self._call("list_threads", {})
        return out.get("rooms", out.get("threads", out)) if isinstance(out, dict) else out

    async def list_messages(self, thread_id):
        out = await self._call("list_messages", {"room_id": thread_id, "thread_id": thread_id})
        return out.get("messages", out) if isinstance(out, dict) else out

    async def get_events(self, after=0, limit=100):
        return {"events": [], "next_cursor": after}  # live mode polls proposals/threads instead

    async def health(self):
        try:
            await self._load()
            return {"status": "ok", "marketplace": self.name, "tools": len(self._tools or {})}
        except MarketplaceError as exc:
            return {"status": "down", "marketplace": self.name, "detail": exc.detail}

    # ---- write: drafts only; the user confirms on Upwork ----
    async def create_proposal_draft(self, payload, idempotency_key):
        out = await self._call("create_proposal_draft", {
            "job_id": payload["job_id"], "cover_letter": payload["cover_letter"],
            "bid_amount": payload.get("bid_amount"), "answers": payload.get("screening_answers"),
        })
        draft_id = (out or {}).get("draft_id") or (out or {}).get("id") or idempotency_key
        return {"draft_id": draft_id, "status": "draft", "connects_cost": None, "live": True}

    async def submit_proposal(self, draft_id, idempotency_key, dry_run=False):
        # Live mode never submits: the draft already exists on Upwork for the user to confirm.
        return {"proposal_id": draft_id, "status": "draft_awaiting_confirmation_on_upwork",
                "connects_spent": 0, "dry_run": dry_run,
                "note": "Open Upwork to review and confirm this proposal. GigBid never submits on your behalf."}

    async def send_message(self, thread_id, text, idempotency_key, dry_run=False):
        if dry_run:
            return {"would_send": {"thread_id": thread_id, "text": text}, "live": True}
        await self._call("send_message", {"room_id": thread_id, "thread_id": thread_id, "text": text, "message": text})
        return {"status": "draft_awaiting_confirmation_on_upwork", "thread_id": thread_id}


def _norm_job(j: Any) -> dict[str, Any]:
    if not isinstance(j, dict):
        return {"job_id": str(j), "title": str(j), "description": ""}
    return {
        "job_id": str(j.get("job_id") or j.get("id") or j.get("ciphertext") or ""),
        "title": j.get("title", ""),
        "description": j.get("description", j.get("snippet", "")),
        "skills": [s if isinstance(s, str) else s.get("name", "") for s in j.get("skills", [])],
        "budget": (j.get("budget") or {}).get("amount") if isinstance(j.get("budget"), dict) else j.get("budget"),
        "hourly_low": j.get("hourly_low") or j.get("hourlyBudgetMin"),
        "hourly_high": j.get("hourly_high") or j.get("hourlyBudgetMax"),
        "is_hourly": j.get("is_hourly") if "is_hourly" in j else j.get("type", "").lower().startswith("hour"),
        "client_id": j.get("client_id") or (j.get("client") or {}).get("id"),
        "posted_at": j.get("posted_at") or j.get("createdDateTime"),
        "source": "upwork_live",
        "raw": {k: v for k, v in j.items() if k not in {"description"}},
    }
