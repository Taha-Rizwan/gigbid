"""Critic: checks grounding, personalisation and length; sends the draft back at most twice."""

from __future__ import annotations

import re

from langgraph.runtime import Runtime

from agent import llm
from agent.context import RunContext
from agent.handoffs import Critique
from agent.nodes.common import job_text, node
from agent.settings import config

GENERIC = re.compile(
    r"(?i)^\s*(dear (sir|madam|hiring manager|client)|hello sir|hi there|i am writing to|i am a highly|"
    r"i have read your job|i am excited to apply|i am the perfect|i am an? (experienced|expert))"
)
BUZZ = re.compile(r"(?i)\b(passionate|synergy|cutting[- ]edge|rockstar|ninja|go-getter|world[- ]class)\b")


def deterministic_checks(draft, questions: list[str]) -> list[str]:
    t = config()["thresholds"]
    words = len(draft.cover_letter.split())
    issues = []
    if words > t["max_proposal_words"]:
        issues.append(f"too long: {words} words (max {t['max_proposal_words']})")
    if words < t["min_proposal_words"]:
        issues.append(f"too short: {words} words (min {t['min_proposal_words']})")
    if GENERIC.search(draft.cover_letter):
        issues.append("generic opening: start with the client's problem")
    if m := BUZZ.search(draft.cover_letter):
        issues.append(f"buzzword '{m.group(0)}'")
    if questions and len([a for a in draft.screening_answers if len(a.split()) > 12]) < len(questions):
        issues.append("not every screening question has a real answer")
    if "[" not in draft.cover_letter:
        issues.append("no evidence citations in the cover letter")
    return issues


@node("critic")
async def critic(state: dict, runtime: Runtime[RunContext]) -> dict:
    draft, job = state["draft"], state["job"]
    spec = state.get("job_spec")
    questions = (spec.screening_questions if spec else None) or job.screening_questions
    issues = deterministic_checks(draft, questions)
    ver = state.get("verification") or {}
    t = config()["thresholds"]
    user = (f"{job_text(job)}\n\nWord limits: {t['min_proposal_words']}-{t['max_proposal_words']}\n"
            f"Verification: {ver.get('after', 0)} unsupported claims remain after rewriting.\n"
            f"Automatic checks found: {issues or 'nothing'}\n\nDRAFT:\n{draft.cover_letter}\n\nANSWERS:\n"
            + "\n---\n".join(draft.screening_answers))
    c = await llm.structured("critic", Critique, llm.prompt_messages("critic", user))
    c.issues = list(dict.fromkeys(issues + c.issues))
    if issues or ver.get("after", 0) > 0:
        c.passed = False
        c.grounding_ok = c.grounding_ok and ver.get("after", 0) == 0
        if not c.instructions:
            c.instructions = "Fix: " + "; ".join(c.issues)
    return {"critiques": [c]}
