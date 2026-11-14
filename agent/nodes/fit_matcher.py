"""Fit Matcher: maps every requirement to portfolio evidence via the Portfolio MCP server and
produces a fit score with reasons. Runs in parallel with the Analyst, so it splits requirements
itself (cheap small-model call) rather than waiting for the JobSpec."""

from __future__ import annotations

import asyncio

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from agent import llm
from agent.context import RunContext
from agent.handoffs import FitReport, RequirementMatch
from agent.nodes.common import as_items, evidence_block, job_text, node
from agent.settings import config


class _Reqs(BaseModel):
    requirements: list[str] = Field(default_factory=list, description="2-8 atomic, searchable requirements")
    required_skills: list[str] = Field(default_factory=list)


class _Match(BaseModel):
    requirement: str
    evidence_ids: list[str] = Field(default_factory=list)
    covered: bool = False
    rationale: str = ""


class _Fit(BaseModel):
    matches: list[_Match]
    score: float = Field(ge=0, le=1)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


@node("fit_matcher")
async def fit_matcher(state: dict, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    job, persona = state["job"], state["persona_id"]
    tools = ctx.toolbox.for_agent("fit_matcher")
    reqs = await llm.structured("fit_matcher", _Reqs, llm.prompt_messages("analyst", job_text(job, ctx.datamark)))
    requirements = reqs.requirements[:8] or [job.title]
    k = config()["rag"]["k"]

    async def search(r: str):
        return r, as_items(await tools.call("search_evidence", requirement=r, k=k, persona_id=persona))

    per_req = dict(await asyncio.gather(*(search(r) for r in requirements)))
    pool = {e.evidence_id: e for items in per_req.values() for e in items}
    catalogue = "\n\n".join(f"REQUIREMENT: {r}\n{evidence_block(items, 350)}" for r, items in per_req.items())
    fit = await llm.structured(
        "fit_matcher", _Fit,
        llm.prompt_messages("fit_matcher", f"Job required skills: {reqs.required_skills}\n\n{catalogue}"),
    )
    matches = []
    for m in fit.matches:
        ev = [pool[i] for i in m.evidence_ids if i in pool]  # ids not retrieved are dropped: no invented evidence
        matches.append(RequirementMatch(requirement=m.requirement, evidence=ev, covered=m.covered and bool(ev),
                                        rationale=m.rationale))
    covered = sum(m.covered for m in matches) / max(1, len(matches))
    score = round(min(fit.score, covered + 0.15), 3)  # model score cannot exceed observed coverage by much
    report = FitReport(score=score, matches=matches, matched_skills=fit.matched_skills,
                       missing_skills=fit.missing_skills, reasons=fit.reasons)
    used = {e.evidence_id for m in matches for e in m.evidence}
    return {"fit_report": report, "evidence": [pool[i] for i in used] or list(pool.values())[:k]}
