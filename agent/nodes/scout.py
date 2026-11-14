"""Scout: runs saved searches on schedule, de-duplicates, queues new jobs. Called by the worker,
not inside the bid graph (one bid-graph thread per job starts from what the Scout queues)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from agent.mcp_client import AgentTools


def fingerprint(job: dict[str, Any]) -> str:
    """Reposts get new ids; match them on normalised title + description start."""
    text = re.sub(r"\W+", " ", f"{job.get('title', '')} {(job.get('snippet') or job.get('description') or '')[:200]}").lower()
    return hashlib.sha1(text.strip().encode()).hexdigest()[:16]


async def scout(tools: AgentTools, searches: list[dict[str, Any]], seen_ids: set[str], seen_prints: set[str],
                excluded_keywords: list[str] | None = None, limit: int = 20) -> tuple[list[dict], dict[str, int]]:
    new: list[dict] = []
    stats = {"fetched": 0, "duplicates": 0, "excluded": 0}
    for s in searches or [{"query": ""}]:
        out = await tools.call("search_jobs", query=s.get("query", ""), category=s.get("category"), limit=limit)
        for j in out.get("jobs", []):
            stats["fetched"] += 1
            fp = fingerprint(j)
            if j["job_id"] in seen_ids or fp in seen_prints:
                stats["duplicates"] += 1
                continue
            text = f"{j.get('title', '')} {j.get('snippet', '')}".lower()
            if any(k.lower() in text for k in (excluded_keywords or []) if k):
                stats["excluded"] += 1
                continue
            if s.get("min_budget") and (j.get("budget") or j.get("hourly_high") or 0) < s["min_budget"]:
                stats["excluded"] += 1
                continue
            seen_ids.add(j["job_id"])
            seen_prints.add(fp)
            new.append(j | {"fingerprint": fp})
    return new, stats
