"""V8: corrective RAG as a small LangGraph loop.

retrieve -> grade each requirement's evidence -> re-query weak requirements once -> refuse to
claim requirements that still have no support. The coverage map feeds the Fit Matcher and the
bid-or-skip decision, so jobs the persona cannot prove become skips instead of bluffs.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agent import llm
from agent.handoffs import EvidenceItem
from agent.settings import config
from rag.variants.base import PipelineConfig


class Grade(BaseModel):
    relevant_ids: list[str] = Field(default_factory=list, description="evidence ids that prove the requirement")
    better_query: str = Field(default="", description="a rewritten search query if none are relevant")


class CState(TypedDict, total=False):
    requirements: list[str]
    per_req: dict[str, list[EvidenceItem]]
    covered: dict[str, list[str]]
    requeries: int
    queries: dict[str, str]


async def _grade(req: str, items: list[EvidenceItem]) -> Grade:
    if not items:
        return Grade(relevant_ids=[], better_query=req)
    catalogue = "\n".join(f"- {e.evidence_id}: {e.title} :: {e.snippet[:300]}" for e in items)
    return await llm.structured(
        "fit_matcher",
        Grade,
        llm.prompt_messages("evidence_grader", f"Requirement: {req}\n\nCandidate evidence:\n{catalogue}"),
    )


def build_graph(retriever, base_query):
    max_requeries = config()["rag"]["corrective_max_requeries"]

    async def retrieve(state: CState) -> CState:
        queries = state.get("queries") or {r: r for r in state["requirements"]}
        per_req = dict(state.get("per_req") or {})
        todo = [r for r in state["requirements"] if r not in (state.get("covered") or {})]

        async def one(r: str):
            q = replace(base_query, job_text=queries[r], requirements=[queries[r]], k=4)
            return r, await asyncio.to_thread(retriever.retrieve, q)

        for r, items in await asyncio.gather(*(one(r) for r in todo)):
            per_req[r] = items
        return {"per_req": per_req, "queries": queries}

    async def grade(state: CState) -> CState:
        covered = dict(state.get("covered") or {})
        queries = dict(state["queries"])
        todo = [r for r in state["requirements"] if r not in covered]
        grades = await asyncio.gather(*(_grade(r, state["per_req"].get(r, [])) for r in todo))
        for r, g in zip(todo, grades, strict=True):
            valid = {e.evidence_id for e in state["per_req"].get(r, [])}
            ids = [i for i in g.relevant_ids if i in valid]
            if ids:
                covered[r] = ids
            elif g.better_query:
                queries[r] = g.better_query
        return {"covered": covered, "queries": queries, "requeries": state.get("requeries", 0) + 1}

    def route(state: CState) -> str:
        missing = [r for r in state["requirements"] if r not in state.get("covered", {})]
        return "retrieve" if missing and state["requeries"] <= max_requeries else END

    g = StateGraph(CState)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route, ["retrieve", END])
    return g.compile()


async def corrective_retrieve(retriever, q) -> tuple[list[EvidenceItem], dict[str, list[str]]]:
    reqs = q.requirements or [q.job_text[:500]]
    graph = build_graph(retriever, q)
    final = await graph.ainvoke({"requirements": reqs, "requeries": 0})
    covered = final.get("covered", {})
    # keep only graded-relevant evidence (refuse to claim the rest), ordered by best score
    pool: dict[str, EvidenceItem] = {}
    for r, items in final.get("per_req", {}).items():
        for e in items:
            if e.evidence_id in covered.get(r, []):
                if e.evidence_id not in pool or e.score > pool[e.evidence_id].score:
                    pool[e.evidence_id] = e
    ranked = sorted(pool.values(), key=lambda e: -e.score)
    if len(ranked) < q.k:  # backfill with ungraded top results, marked low-confidence
        extra = await asyncio.to_thread(retriever.retrieve, replace(q, k=q.k * 2))
        for e in extra:
            if e.evidence_id not in pool and len(ranked) < q.k:
                ranked.append(e.model_copy(update={"score": min(e.score, 0.0)}))
    return ranked[: q.k], covered




PIPELINE = PipelineConfig(
    "v8_corrective", scheme="multivector", decompose=True, hybrid=True, rerank=True, corrective=True
)
