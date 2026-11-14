"""Explicit promotion rules: the only way anything enters long-term memory (R7).

Style memory   ("style", user_id):   learned from the user's edits and rejection reasons.
  - Each edit is diffed; a small model names at most 3 generalisable rules ("cut the first sentence").
  - A rule is a *candidate* until the same rule is observed `style_promotion_min_occurrences` times
    (config); only then is it promoted into ("style", user_id) and used by the Writer.
  - One-off edits and anything quoting a specific client never get promoted. At most
    `style_max_rules` rules are kept; the user can delete any of them in the UI.
Outcome memory ("outcome", user_id): what won or got replies per job category.
  - Only aggregates derived from marketplace outcome events are stored (counts, rates, the
    proposal styles that worked); raw tool output never goes into memory.
  - A category insight is promoted once it has `outcome_min_samples` outcomes.
"""

from __future__ import annotations

import difflib
import re
from datetime import UTC, datetime
from typing import Any

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from agent import llm
from agent.settings import config


class StyleObservation(BaseModel):
    rules: list[str] = Field(default_factory=list, max_length=3,
                             description="Short imperative, general rules the edit implies, e.g. 'Never say passionate'")


def diff_summary(before: str, after: str) -> dict[str, Any]:
    sm = difflib.SequenceMatcher(None, before.split(), after.split())
    removed, added = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            removed.append(" ".join(before.split()[i1:i2]))
        if tag in ("insert", "replace"):
            added.append(" ".join(after.split()[j1:j2]))
    first_sentence_cut = bool(before.strip()) and before.split(".")[0].strip() not in after
    return {"similarity": round(sm.ratio(), 3), "removed": removed[:20], "added": added[:20],
            "first_sentence_cut": first_sentence_cut,
            "length_delta": len(after.split()) - len(before.split())}


def slug(rule: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", rule.lower()).strip("-")[:60]


async def observe_edit(store: BaseStore, user_id: str, before: str, after: str) -> dict[str, Any]:
    diff = diff_summary(before, after)
    if diff["similarity"] > 0.98:
        return {"diff": diff, "candidates": [], "promoted": []}
    obs = await llm.structured(
        "compliance", StyleObservation,
        llm.prompt_messages_raw(
            "From this edit a freelancer made to an AI-drafted proposal, infer at most 3 short, general style "
            "rules they want applied to future proposals. Ignore job-specific content and names. "
            "If nothing generalises, return an empty list.",
            f"Removed: {diff['removed']}\nAdded: {diff['added']}\nFirst sentence cut: {diff['first_sentence_cut']}\n"
            f"Length change (words): {diff['length_delta']}",
        ),
    )
    return {"diff": diff, **await _count_and_promote(store, user_id, obs.rules, source="edit")}


async def observe_rejection(store: BaseStore, user_id: str, reason: str) -> dict[str, Any]:
    if not reason or len(reason.split()) < 3:
        return {"candidates": [], "promoted": []}
    obs = await llm.structured(
        "compliance", StyleObservation,
        llm.prompt_messages_raw(
            "A freelancer rejected an AI-drafted proposal with this reason. If it implies a general style rule for "
            "future proposals, state it (max 2). If it is about the job itself (wrong fit, bad client), return none.",
            reason,
        ),
    )
    return await _count_and_promote(store, user_id, obs.rules[:2], source="rejection")


async def _count_and_promote(store: BaseStore, user_id: str, rules: list[str], source: str) -> dict[str, Any]:
    cfg = config()["memory"]
    now = datetime.now(UTC).isoformat()
    cand_ns, style_ns = ("style_candidates", user_id), ("style", user_id)
    promoted, candidates = [], []
    for rule in rules:
        rule = rule.strip().rstrip(".")
        if not rule or len(rule) > 160 or re.search(r"\d{3,}|@|https?://", rule):
            continue
        key = slug(rule)
        item = await store.aget(cand_ns, key)
        count = (item.value["count"] if item else 0) + 1
        await store.aput(cand_ns, key, {"rule": rule, "count": count, "source": source, "last_seen": now})
        candidates.append({"rule": rule, "count": count})
        if count >= cfg["style_promotion_min_occurrences"] and not await store.aget(style_ns, key):
            existing = await store.asearch(style_ns, limit=100)
            if len(existing) >= cfg["style_max_rules"]:
                oldest = min(existing, key=lambda i: i.updated_at)
                await store.adelete(style_ns, oldest.key)
            await store.aput(style_ns, key, {"rule": rule, "evidence_count": count, "promoted_at": now,
                                             "promotion_rule": f">= {cfg['style_promotion_min_occurrences']} observations"})
            promoted.append(rule)
    return {"candidates": candidates, "promoted": promoted}


async def style_rules(store: BaseStore | None, user_id: str) -> list[str]:
    if store is None:
        return []
    return [i.value["rule"] for i in await store.asearch(("style", user_id), limit=50)]


async def record_outcome(store: BaseStore, user_id: str, category: str, outcome: str, style: str | None = None) -> dict:
    """Called from marketplace events (viewed/replied/interview/hired/declined) for submitted proposals."""
    cfg = config()["memory"]
    ns_raw, ns = ("outcome_counts", user_id), ("outcome", user_id)
    item = await store.aget(ns_raw, category or "other")
    v = item.value if item else {"proposals": 0, "replies": 0, "hires": 0, "styles": {}}
    v["proposals"] += 1
    replied = outcome in ("replied", "interview", "hired")
    v["replies"] += int(replied)
    v["hires"] += int(outcome == "hired")
    if style:
        s = v["styles"].setdefault(style, [0, 0])
        s[0] += 1
        s[1] += int(replied)
    await store.aput(ns_raw, category or "other", v)
    if v["proposals"] >= cfg["outcome_min_samples"]:
        best = max(v["styles"].items(), key=lambda kv: kv[1][1] / max(1, kv[1][0]), default=(None, None))[0]
        await store.aput(ns, category or "other", {
            "category": category, "proposals": v["proposals"], "reply_rate": round(v["replies"] / v["proposals"], 3),
            "hire_rate": round(v["hires"] / v["proposals"], 3), "best_style": best,
            "promotion_rule": f">= {cfg['outcome_min_samples']} outcomes"})
    return v


async def outcome_hint(store: BaseStore | None, user_id: str, category: str | None) -> dict | None:
    if store is None or not category:
        return None
    item = await store.aget(("outcome", user_id), category)
    return item.value if item else None
