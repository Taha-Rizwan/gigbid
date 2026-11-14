"""Typed graph state.

Three things are kept apart (see docs/ARCHITECTURE.md):
- **State** (this file): what one job or conversation needs right now.
- **Execution trace**: every tool name, argument, result and observation, in LangSmith plus the
  append-only audit_log and run_events tables. Never stored in state.
- **Long-term memory**: only promoted knowledge, in the LangGraph store (agent/memory).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from agent.handoffs import (
    ApprovalResponse,
    BidDecision,
    ComplianceVerdict,
    Critique,
    EvidenceItem,
    FitReport,
    Job,
    JobSpec,
    PriceQuote,
    ProposalDraft,
    ReplyDraft,
    RiskReport,
)


def merge_evidence(left: list[EvidenceItem] | None, right: list[EvidenceItem] | None) -> list[EvidenceItem]:
    """Parallel branches may both add evidence; keep one copy per id with the best score."""
    out: dict[str, EvidenceItem] = {e.evidence_id: e for e in (left or [])}
    for e in right or []:
        if e.evidence_id not in out or e.score > out[e.evidence_id].score:
            out[e.evidence_id] = e
    return sorted(out.values(), key=lambda e: -e.score)


def last(left: Any, right: Any) -> Any:
    return right if right is not None else left


class BidState(TypedDict, total=False):
    # inputs
    user_id: str
    persona_id: str
    job_id: str
    profile: dict[str, Any]          # rates, floors, budgets, autonomy, style rules
    # intake
    job: Job
    client: dict[str, Any]
    injection_score: float
    # parallel analysis (each branch writes its own field; evidence/errors use reducers)
    job_spec: JobSpec
    risk_report: RiskReport
    fit_report: FitReport
    evidence: Annotated[list[EvidenceItem], merge_evidence]
    # decision and pricing
    decision: BidDecision
    price_quote: PriceQuote
    # drafting loop
    draft: ProposalDraft
    verification: dict[str, Any]
    critiques: Annotated[list[Critique], operator.add]
    revisions: int
    compliance: ComplianceVerdict
    # approval and send
    dry_run: dict[str, Any]
    approval: ApprovalResponse
    submission: dict[str, Any]
    status: Annotated[str, last]
    errors: Annotated[list[str], operator.add]


class ConversationState(TypedDict, total=False):
    user_id: str
    persona_id: str
    conversation_id: str
    job_id: str | None
    profile: dict[str, Any]
    messages: list[dict[str, Any]]
    intent: str
    flags: list[str]
    slots: list[dict[str, Any]]
    evidence: list[EvidenceItem]
    reply: ReplyDraft
    compliance: ComplianceVerdict
    approval: ApprovalResponse
    sent: dict[str, Any]
    status: Annotated[str, last]
    errors: Annotated[list[str], operator.add]
