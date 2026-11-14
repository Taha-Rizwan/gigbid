"""Typed hand-offs between agents.

Anything a later node decides on travels as one of these models, never as free text.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Decision(StrEnum):
    bid = "bid"
    watch = "watch"
    skip = "skip"


class ClaimLabel(StrEnum):
    supported = "supported"
    partly_supported = "partly_supported"
    unsupported = "unsupported"


class Job(BaseModel):
    """A job as the marketplace port returns it (GigSim or live Upwork)."""

    job_id: str
    title: str
    description: str
    category: str | None = None
    skills: list[str] = Field(default_factory=list)
    is_hourly: bool | None = None
    hourly_low: float | None = None
    hourly_high: float | None = None
    budget: float | None = None
    country: str | None = None
    posted_at: datetime | None = None
    client_id: str | None = None
    connects_cost: int | None = None
    proposals_count: int | None = None
    screening_questions: list[str] = Field(default_factory=list)
    experience_level: str | None = None
    source: str = "gigsim"


class JobSpec(BaseModel):
    job_id: str
    title: str
    summary: str = ""
    deliverables: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(
        default_factory=list, description="Atomic requirements, one per thing the client asks for"
    )
    budget_min: float | None = None
    budget_max: float | None = None
    is_hourly: bool | None = None
    timeline: str | None = None
    screening_questions: list[str] = Field(default_factory=list)
    hidden_needs: list[str] = Field(default_factory=list)
    category: str | None = None


class RiskReport(BaseModel):
    score: float = Field(ge=0, le=1, description="0 = safe, 1 = certainly a scam")
    level: RiskLevel = RiskLevel.low
    flags: list[str] = Field(default_factory=list)
    injection_detected: bool = False
    client_quality: float = Field(default=0.5, ge=0, le=1)
    explanation: str = ""


class EvidenceItem(BaseModel):
    evidence_id: str
    type: str
    title: str
    snippet: str
    source: str = ""
    project: str | None = None
    date: str | None = None
    outcome: str | None = None
    score: float = 0.0


class RequirementMatch(BaseModel):
    requirement: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    covered: bool = False
    rationale: str = ""


class FitReport(BaseModel):
    score: float = Field(ge=0, le=1)
    matches: list[RequirementMatch] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)

    @property
    def evidence_ids(self) -> list[str]:
        return [e.evidence_id for m in self.matches for e in m.evidence]


class BidDecision(BaseModel):
    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    fit_score: float = 0.0
    risk_score: float = 0.0


class PriceQuote(BaseModel):
    amount: float
    rate_type: Literal["hourly", "fixed"]
    currency: str = "USD"
    market_p25: float | None = None
    market_p50: float | None = None
    market_p75: float | None = None
    connects_cost: int = 0
    connects_worth_it: bool = True
    rationale: str = ""


class Claim(BaseModel):
    text: str
    label: ClaimLabel = ClaimLabel.unsupported
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ProposalDraft(BaseModel):
    job_id: str
    cover_letter: str
    screening_answers: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    version: int = 1
    status: str = "pending_review"


class Critique(BaseModel):
    passed: bool
    grounding_ok: bool = True
    personalised: bool = True
    length_ok: bool = True
    issues: list[str] = Field(default_factory=list)
    instructions: str = ""


class ComplianceVerdict(BaseModel):
    allowed: bool
    violations: list[str] = Field(default_factory=list)
    redactions: list[str] = Field(default_factory=list)
    cleaned_text: str | None = None
    reason: str = ""


class MessageIntent(StrEnum):
    question = "question"
    negotiation = "negotiation"
    interview_request = "interview_request"
    scam_signal = "scam_signal"
    other = "other"


class ReplyDraft(BaseModel):
    thread_id: str
    intent: MessageIntent
    text: str
    proposed_slots: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    """What the UI shows at an interrupt. Everything the human needs to decide."""

    kind: Literal["proposal", "message", "connects"]
    thread_id: str
    draft: ProposalDraft | None = None
    reply: ReplyDraft | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    risk: RiskReport | None = None
    price: PriceQuote | None = None
    critiques: list[Critique] = Field(default_factory=list)
    compliance: ComplianceVerdict | None = None
    dry_run: dict | None = None


class ApprovalResponse(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: str | None = None
    edited_answers: list[str] | None = None
    reason: str | None = None
