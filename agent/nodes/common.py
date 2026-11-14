from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from langgraph.runtime import Runtime

from agent.context import RunContext
from agent.guardrails import wrap
from agent.handoffs import EvidenceItem, Job


def node(name: str):
    """Emit start/end events for the live run viewer and record per-node latency."""

    def deco(fn: Callable[..., Awaitable[dict]]):
        @wraps(fn)
        async def inner(state: dict, runtime: Runtime[RunContext]) -> dict:
            ctx = runtime.context
            t0 = time.perf_counter()
            await ctx.event(name, "start", f"{name} started")
            try:
                out = await fn(state, runtime)
            except Exception as exc:
                await ctx.event(name, "error", f"{type(exc).__name__}: {str(exc)[:200]}")
                raise
            await ctx.event(name, "end", _summary(name, out), {"seconds": round(time.perf_counter() - t0, 2)})
            return out

        return inner

    return deco


def _summary(name: str, out: dict) -> str:
    parts = []
    for k, v in (out or {}).items():
        if hasattr(v, "score"):
            parts.append(f"{k} score {v.score:.2f}")
        elif hasattr(v, "decision"):
            parts.append(f"decision {v.decision}")
        elif k == "status":
            parts.append(f"status {v}")
        elif k == "price_quote":
            parts.append(f"price {v.amount:.0f} {v.rate_type}")
    return "; ".join(parts) or f"{name} done"


def job_text(job: Job, mark: bool = False) -> str:
    header = (f"Title: {job.title}\nCategory: {job.category}\nBudget: {job.budget}\n"
              f"Hourly: {job.hourly_low}-{job.hourly_high}\nSkills listed: {', '.join(job.skills)}\n"
              f"Screening questions: {json.dumps(job.screening_questions)}")
    return wrap("job_post", f"{header}\n\nDescription:\n{job.description}", mark)


def evidence_block(items: list[EvidenceItem], max_chars: int = 600) -> str:
    return "\n".join(
        f"[{e.evidence_id}] ({e.type}{', outcome ' + e.outcome if e.outcome else ''}) {e.title}: {e.snippet[:max_chars]}"
        for e in items
    )


def as_items(raw: Any) -> list[EvidenceItem]:
    items = raw.get("items", []) if isinstance(raw, dict) else raw or []
    return [EvidenceItem(**i) if isinstance(i, dict) else i for i in items]
