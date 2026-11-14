"""Claim verification (B3): split a draft into claims, ground each against evidence, and remove
or rewrite unsupported ones before the Critic sees the draft."""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agent import llm
from agent.handoffs import Claim, ClaimLabel, EvidenceItem

CITE = re.compile(r"\[([a-z_]+:[a-z]+:[^\]\s]+)\]")


class _Claims(BaseModel):
    claims: list[Claim] = Field(default_factory=list)


class _Verdict(BaseModel):
    index: int
    label: ClaimLabel
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = ""


class _Verdicts(BaseModel):
    verdicts: list[_Verdict] = Field(default_factory=list)


class _Rewrite(BaseModel):
    cover_letter: str
    screening_answers: list[str] = Field(default_factory=list)


def _catalogue(evidence: list[EvidenceItem]) -> str:
    return "\n".join(f"[{e.evidence_id}] {e.title}: {e.snippet}" for e in evidence)


async def split_claims(text: str) -> list[Claim]:
    out = await llm.structured("verifier", _Claims, llm.prompt_messages("claim_splitter", text))
    for c in out.claims:
        c.evidence_ids = list(dict.fromkeys(c.evidence_ids + CITE.findall(c.text)))
    return out.claims


async def label_claims(claims: list[Claim], evidence: list[EvidenceItem]) -> list[Claim]:
    if not claims:
        return []
    valid = {e.evidence_id for e in evidence}
    listing = "\n".join(f"{i}. {c.text} (cited: {', '.join(c.evidence_ids) or 'none'})" for i, c in enumerate(claims))
    out = await llm.structured(
        "verifier",
        _Verdicts,
        llm.prompt_messages("claim_verifier", f"EVIDENCE:\n{_catalogue(evidence)}\n\nCLAIMS:\n{listing}"),
    )
    by_idx = {v.index: v for v in out.verdicts}
    labelled = []
    for i, c in enumerate(claims):
        v = by_idx.get(i)
        if v is None:
            labelled.append(c.model_copy(update={"label": ClaimLabel.unsupported, "note": "not verified"}))
            continue
        ids = [e for e in v.evidence_ids if e in valid]
        label = v.label
        if label != ClaimLabel.unsupported and not ids:
            label = ClaimLabel.unsupported  # a "supported" verdict must point at real evidence
        labelled.append(c.model_copy(update={"label": label, "evidence_ids": ids, "note": v.note}))
    return labelled


def unsupported_count(claims: list[Claim]) -> int:
    return sum(c.label == ClaimLabel.unsupported for c in claims)


async def verify_draft(cover_letter: str, answers: list[str], evidence: list[EvidenceItem]) -> dict:
    """Returns {cover_letter, screening_answers, claims, before, after, rewritten}."""
    full = cover_letter + ("\n\n" + "\n".join(answers) if answers else "")
    claims = await label_claims(await split_claims(full), evidence)
    before = unsupported_count(claims)
    partly = sum(c.label == ClaimLabel.partly_supported for c in claims)
    if before == 0 and partly == 0:
        return {"cover_letter": cover_letter, "screening_answers": answers, "claims": claims,
                "before": 0, "after": 0, "rewritten": False}
    problems = "\n".join(
        f"- {c.label.value.upper()}: {c.text} ({c.note})" for c in claims if c.label != ClaimLabel.supported
    )
    rewrite = await llm.structured(
        "verifier",
        _Rewrite,
        llm.prompt_messages(
            "claim_rewriter",
            f"EVIDENCE:\n{_catalogue(evidence)}\n\nPROBLEM CLAIMS:\n{problems}\n\n"
            f"COVER LETTER:\n{cover_letter}\n\nSCREENING ANSWERS:\n" + "\n---\n".join(answers),
        ),
    )
    full2 = rewrite.cover_letter + ("\n\n" + "\n".join(rewrite.screening_answers) if rewrite.screening_answers else "")
    claims2 = await label_claims(await split_claims(full2), evidence)
    return {
        "cover_letter": rewrite.cover_letter,
        "screening_answers": rewrite.screening_answers or answers,
        "claims": claims2,
        "before": before,
        "after": unsupported_count(claims2),
        "rewritten": True,
    }


def verify_claims(draft: str, evidence: list[dict]) -> list[dict]:
    """Sync helper kept from the starter-kit signature."""
    import asyncio

    items = [EvidenceItem(**e) for e in evidence]
    claims = asyncio.run(label_claims(asyncio.run(split_claims(draft)), items))
    return [c.model_dump() for c in claims]


_ = HumanMessage
