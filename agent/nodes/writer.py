"""Proposal Writer: cover letter + screening answers where every claim cites portfolio evidence."""

from __future__ import annotations

import asyncio

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from agent import llm
from agent.context import RunContext
from agent.handoffs import EvidenceItem, ProposalDraft
from agent.memory.promotion_rules import outcome_hint, style_rules
from agent.nodes.common import as_items, evidence_block, job_text, node
from agent.settings import config, load_prompt
from agent.state import merge_evidence


class _Draft(BaseModel):
    cover_letter: str
    screening_answers: list[str] = Field(default_factory=list)


def strategy_rule(profile: dict) -> str:
    """X2: the opening strategy under test (config.proposal_strategies)."""
    cfg = config()
    name = profile.get("strategy") or cfg.get("default_strategy")
    text = (cfg.get("proposal_strategies") or {}).get(name)
    return f"\n- Opening strategy ({name}): {text}" if text else ""


def policy_rules(profile: dict) -> str:
    disclosure = config()["policy"].get("required_disclosure") or (profile.get("policy") or {}).get("required_disclosure")
    return f"\n- The cover letter MUST end with this exact sentence: \"{disclosure}\"" if disclosure else ""


async def write(state: dict, ctx: RunContext, store, instructions: str = "") -> ProposalDraft:
    job, spec, persona = state["job"], state.get("job_spec"), state["persona_id"]
    tools = ctx.toolbox.for_agent("writer")
    evidence: list[EvidenceItem] = list(state.get("evidence") or [])
    questions = (spec.screening_questions if spec else None) or job.screening_questions
    if questions and not instructions:  # find evidence for screening questions too
        found = await asyncio.gather(*(tools.call("search_evidence", requirement=q, k=3, persona_id=persona) for q in questions))
        evidence = merge_evidence(evidence, [e for f in found for e in as_items(f)])
    rules = await style_rules(store, state["user_id"])
    hint = await outcome_hint(store, state["user_id"], job.category)
    t = config()["thresholds"]
    _, system = load_prompt("writer")
    system = system.format(
        min_words=t["min_proposal_words"], max_words=t["max_proposal_words"],
        style_rules=("User style rules (learned from their edits):\n" + "\n".join(f"- {r}" for r in rules)) if rules else "",
        policy_rules=policy_rules(state.get("profile") or {}) + strategy_rule(state.get("profile") or {}),
    )
    price = state.get("price_quote")
    user = (
        f"{job_text(job, ctx.datamark)}\n\n"
        f"Job analysis: requirements={spec.requirements if spec else []}; hidden needs={spec.hidden_needs if spec else []}\n"
        f"Bid: {price.amount if price else '?'} ({price.rate_type if price else ''})\n"
        + (f"What worked before in this category: {hint}\n" if hint else "")
        + f"\nEVIDENCE (cite ids exactly):\n{evidence_block(evidence[:12], 500)}\n"
        + ("\nScreening questions to answer:\n" + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions)) if questions else "")
        + (f"\n\nREVISION INSTRUCTIONS from the critic:\n{instructions}\n\nPrevious draft:\n{state['draft'].cover_letter}"
           if instructions and state.get("draft") else "")
    )
    from langchain_core.messages import HumanMessage, SystemMessage

    out = await llm.structured("writer", _Draft, [SystemMessage(system), HumanMessage(user)])
    prev = state.get("draft")
    return ProposalDraft(job_id=job.job_id, cover_letter=out.cover_letter.strip(),
                         screening_answers=out.screening_answers[: len(questions)] if questions else out.screening_answers,
                         evidence_ids=[e.evidence_id for e in evidence], version=(prev.version + 1) if prev else 1)


@node("proposal_writer")
async def proposal_writer(state: dict, runtime: Runtime[RunContext]) -> dict:
    critiques = state.get("critiques") or []
    instructions = critiques[-1].instructions if critiques and not critiques[-1].passed else ""
    draft = await write(state, runtime.context, runtime.store, instructions)
    revisions = state.get("revisions", 0) + (1 if instructions else 0)
    return {"draft": draft, "revisions": revisions, "status": "drafting"}
