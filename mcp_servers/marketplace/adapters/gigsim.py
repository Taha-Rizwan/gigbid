"""GigSim adapter: the marketplace port over GigSim's REST API, with timeouts and bounded
retries with backoff on 429 / 5xx."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable
from agent.settings import config


class GigSimAdapter:
    name = "gigsim"

    def __init__(self, base_url: str, account_token: str, client: httpx.AsyncClient | None = None):
        mk = config()["marketplace"]
        self.base_url = base_url.rstrip("/")
        self.token = account_token
        self.max_retries = mk["max_retries"]
        self.client = client or httpx.AsyncClient(timeout=mk["timeout_seconds"])

    async def _req(self, method: str, path: str, *, params=None, json=None, idem: str | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"}
        if idem:
            headers["Idempotency-Key"] = idem
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                r = await self.client.request(method, f"{self.base_url}{path}", params=params, json=json, headers=headers)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as exc:
                last = MarketplaceUnavailable(f"gigsim unreachable: {type(exc).__name__}")
            else:
                if r.status_code < 400:
                    return r.json()
                body = _safe_json(r)
                if r.status_code == 429:
                    wait = float(r.headers.get("retry-after", body.get("retry_after", 1)))
                    last = MarketplaceError("rate_limited", body.get("detail", ""), 429, wait)
                    await asyncio.sleep(min(wait, 10))
                    continue
                if r.status_code >= 500:
                    last = MarketplaceUnavailable(body.get("detail") or f"gigsim {r.status_code}")
                else:
                    raise MarketplaceError(body.get("error", "error"), body.get("detail", ""), r.status_code, data=body)
            if attempt < self.max_retries:
                await asyncio.sleep(min(8, 0.5 * 2**attempt) + random.random() * 0.2)
        raise last or MarketplaceUnavailable()

    # ---- read ----
    async def search_jobs(self, query="", category=None, limit=20, offset=0, posted_after=None):
        params = {k: v for k, v in {"q": query, "category": category, "limit": limit, "offset": offset,
                                    "posted_after": posted_after}.items() if v not in (None, "")}
        return await self._req("GET", "/v1/jobs", params=params)

    async def get_job(self, job_id):
        return await self._req("GET", f"/v1/jobs/{job_id}")

    async def get_client_history(self, client_id):
        return await self._req("GET", f"/v1/clients/{client_id}")

    async def get_connects_balance(self):
        return await self._req("GET", "/v1/connects")

    async def get_market_stats(self, category=None):
        return await self._req("GET", "/v1/market/stats", params={"category": category} if category else None)

    async def get_policy(self):
        return await self._req("GET", "/v1/policy")

    async def list_proposals(self, status=None):
        out = await self._req("GET", "/v1/proposals", params={"status": status} if status else None)
        return out.get("proposals", out) if isinstance(out, dict) else out

    async def list_threads(self):
        out = await self._req("GET", "/v1/threads")
        return out.get("threads", out) if isinstance(out, dict) else out

    async def list_messages(self, thread_id):
        out = await self._req("GET", f"/v1/threads/{thread_id}/messages")
        return out.get("messages", out) if isinstance(out, dict) else out

    async def get_events(self, after=0, limit=100):
        return await self._req("GET", "/v1/events", params={"after": after, "limit": limit})

    async def health(self):
        try:
            await self.client.get(f"{self.base_url}/v1/policy", headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            return {"status": "ok", "marketplace": self.name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "down", "marketplace": self.name, "detail": type(exc).__name__}

    # ---- write ----
    async def create_proposal_draft(self, payload, idempotency_key):
        return await self._req("POST", "/v1/proposals/drafts", json=payload, idem=idempotency_key)

    async def submit_proposal(self, draft_id, idempotency_key, dry_run=False):
        return await self._req("POST", f"/v1/proposals/drafts/{draft_id}/submit",
                               params={"dry_run": str(dry_run).lower()}, idem=idempotency_key)

    async def send_message(self, thread_id, text, idempotency_key, dry_run=False):
        if dry_run:
            return {"would_send": {"thread_id": thread_id, "text": text}, "connects_cost": 0}
        return await self._req("POST", f"/v1/threads/{thread_id}/messages", json={"text": text}, idem=idempotency_key)


def _safe_json(r: httpx.Response) -> dict:
    try:
        j = r.json()
        return j if isinstance(j, dict) else {"detail": str(j)}
    except Exception:  # noqa: BLE001
        return {"detail": r.text[:300]}
