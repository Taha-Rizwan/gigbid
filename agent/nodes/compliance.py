"""Compliance Guard: enforces the policy pack. Deterministic patterns from config first (they
cannot be talked out of), then an LLM pass for subtler violations. No MCP access."""

from __future__ import annotations

import re

from langgraph.runtime import Runtime

from agent import llm
from agent.context import RunContext
from agent.handoffs import ClaimLabel, ComplianceVerdict
from agent.nodes.common import node
from agent.settings import ROOT, config


def policy_text() -> str:
    p = ROOT / "data" / "policy_pack" / "marketplace_policy.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def pattern_check(text: str) -> tuple[list[str], list[str]]:
    violations, redactions = [], []
    for rule in config()["policy"]["forbidden_patterns"]:
        for m in re.finditer(rule["regex"], text):
            violations.append(rule["name"])
            redactions.append(m.group(0))
    return sorted(set(violations)), redactions


def redact(text: str, redactions: list[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = [s for s in sentences if not any(r in s for r in redactions)]
    return " ".join(kept).strip()


async def check(text: str, claims=None, profile: dict | None = None) -> ComplianceVerdict:
    violations, redactions = pattern_check(text)
    disclosure = config()["policy"].get("required_disclosure") or ((profile or {}).get("policy") or {}).get("required_disclosure")
    unsupported = [c.text for c in (claims or []) if c.label == ClaimLabel.unsupported]
    verdict = await llm.structured(
        "compliance", ComplianceVerdict,
        llm.prompt_messages("compliance", f"TEXT:\n{text}\n\nClaims flagged unsupported: {unsupported}",
                            policy=policy_text()),
    )
    violations = sorted(set(violations) | set(verdict.violations))
    redactions = list(dict.fromkeys(redactions + [r for r in verdict.redactions if r and r in text]))
    cleaned = redact(text, redactions) if redactions else text
    if disclosure and disclosure not in cleaned:
        cleaned = f"{cleaned.rstrip()}\n\n{disclosure}"
    blocked_reason = ""
    if unsupported:
        blocked_reason = f"{len(unsupported)} unsupported claim(s) remain"
    leftover, _ = pattern_check(cleaned)
    if leftover:
        blocked_reason = f"could not remove: {', '.join(leftover)}"
    allowed = not blocked_reason
    return ComplianceVerdict(allowed=allowed, violations=violations, redactions=redactions,
                             cleaned_text=cleaned, reason=blocked_reason or verdict.reason or
                             ("redacted " + ", ".join(violations) if violations else "ok"))


@node("compliance_guard")
async def compliance_guard(state: dict, runtime: Runtime[RunContext]) -> dict:
    draft = state["draft"]
    v = await check(draft.cover_letter + "\n\n" + "\n\n".join(draft.screening_answers), draft.claims,
                    state.get("profile"))
    # apply redactions to the letter itself (answers are re-checked the same way)
    letter = redact(draft.cover_letter, v.redactions) if v.redactions else draft.cover_letter
    disclosure = config()["policy"].get("required_disclosure") or ((state.get("profile") or {}).get("policy") or {}).get("required_disclosure")
    if disclosure and disclosure not in letter:
        letter = f"{letter.rstrip()}\n\n{disclosure}"
    answers = [redact(a, v.redactions) if v.redactions else a for a in draft.screening_answers]
    status = "drafting" if v.allowed else "needs_attention"
    return {"compliance": v, "draft": draft.model_copy(update={"cover_letter": letter, "screening_answers": answers}),
            "status": status}
