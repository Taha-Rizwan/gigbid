"""Claim verification node: runs between the Writer and the Critic (B3)."""

from __future__ import annotations

from langgraph.runtime import Runtime

from agent.context import RunContext
from agent.nodes.common import node
from rag.verify import verify_draft


@node("claim_verifier")
async def claim_verifier(state: dict, runtime: Runtime[RunContext]) -> dict:
    draft = state["draft"]
    evidence = state.get("evidence") or []
    pool = [e for e in evidence if e.evidence_id in set(draft.evidence_ids)] or evidence
    res = await verify_draft(draft.cover_letter, draft.screening_answers, pool)
    new = draft.model_copy(update={
        "cover_letter": res["cover_letter"], "screening_answers": res["screening_answers"], "claims": res["claims"],
    })
    history = dict(state.get("verification") or {})
    history.setdefault("first_before", res["before"])
    history.update({"before": res["before"], "after": res["after"], "rewritten": res["rewritten"],
                    "claims": len(res["claims"])})
    await runtime.context.event("claim_verifier", "custom",
                                f"unsupported claims {res['before']} -> {res['after']}", history)
    return {"draft": new, "verification": history}
