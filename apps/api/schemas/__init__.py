"""Request and response models for the GigBid API.

These are the contract the web client is generated from (apps/web/src/lib/api).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from agent.handoffs import (
    ApprovalRequest,
    Claim,
    ComplianceVerdict,
    Critique,
    EvidenceItem,
    FitReport,
    JobSpec,
    PriceQuote,
    RiskReport,
)

# ---------- auth ----------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    user_id: str
    email: str
    name: str
    onboarded: bool


# ---------- profile & settings ----------

Persona = Literal["ai_ml", "fullstack", "data_analyst", "own"]
MarketplaceMode = Literal["gigsim", "upwork_live"]
Autonomy = Literal["manual", "auto_skip_low_fit"]


class SavedSearch(BaseModel):
    search_id: str | None = None
    query: str
    category: str | None = None
    min_budget: float | None = None
    interval_minutes: int = Field(default=30, ge=15, le=1440)
    enabled: bool = True


class ProfileIn(BaseModel):
    persona: Persona = "ai_ml"
    display_title: str | None = None
    hourly_floor: float = Field(default=35, ge=0)
    fixed_floor: float = Field(default=150, ge=0)
    weekly_connects_budget: int = Field(default=80, ge=0, le=1000)
    excluded_keywords: list[str] = Field(default_factory=list)
    autonomy: Autonomy = "manual"
    marketplace_mode: MarketplaceMode = "gigsim"
    model_profile: Literal["open", "open_alt", "paid"] = "open"


class ProfileOut(ProfileIn):
    user_id: str
    connects_balance: int | None = None
    connects_spent_this_week: int = 0
    upwork_connected: bool = False


# ---------- portfolio ----------


class PortfolioItemOut(BaseModel):
    evidence_id: str
    type: str
    title: str
    project: str | None = None
    skills: list[str] = Field(default_factory=list)
    outcome: str | None = None
    synthetic: bool = True
    added_at: datetime | None = None


class UploadResult(BaseModel):
    added: int
    chunks: int
    items: list[PortfolioItemOut]


# ---------- jobs ----------

JobStatus = Literal[
    "new", "analysing", "skipped", "watch", "drafting", "awaiting_approval",
    "submitted", "rejected", "needs_attention", "failed",
]


class InboxItem(BaseModel):
    job_id: str
    title: str
    snippet: str
    category: str | None = None
    posted_at: datetime | None = None
    status: JobStatus
    fit_score: float | None = None
    risk_score: float | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    risk_flags: list[str] = Field(default_factory=list)
    recommendation: Literal["bid", "watch", "skip"] | None = None
    price: float | None = None
    rate_type: Literal["hourly", "fixed"] | None = None
    connects_cost: int | None = None
    thread_id: str | None = None


class InboxOut(BaseModel):
    items: list[InboxItem]
    total: int
    marketplace_status: Literal["ok", "degraded", "down"] = "ok"


class JobDetail(BaseModel):
    job_id: str
    title: str
    description: str
    category: str | None = None
    budget: float | None = None
    hourly_low: float | None = None
    hourly_high: float | None = None
    is_hourly: bool | None = None
    country: str | None = None
    posted_at: datetime | None = None
    connects_cost: int | None = None
    client: dict[str, Any] | None = None
    status: JobStatus
    thread_id: str | None = None
    job_spec: JobSpec | None = None
    risk_report: RiskReport | None = None
    fit_report: FitReport | None = None
    price_quote: PriceQuote | None = None
    decision: Literal["bid", "watch", "skip"] | None = None
    decision_reasons: list[str] = Field(default_factory=list)
    trace_url: str | None = None


class SkipIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RunStarted(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["queued", "running"]


# ---------- proposals / studio ----------


class ParagraphOut(BaseModel):
    index: int
    text: str
    claims: list[Claim] = Field(default_factory=list)


class StudioOut(BaseModel):
    thread_id: str
    job_id: str
    job_title: str
    status: JobStatus
    version: int
    paragraphs: list[ParagraphOut]
    screening_questions: list[str] = Field(default_factory=list)
    screening_answers: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    critiques: list[Critique] = Field(default_factory=list)
    compliance: ComplianceVerdict | None = None
    price: PriceQuote | None = None
    risk: RiskReport | None = None
    dry_run: dict[str, Any] | None = None
    unsupported_before: int = 0
    unsupported_after: int = 0
    pending_approval: ApprovalRequest | None = None
    trace_url: str | None = None
    run_id: str | None = None


class ApprovalIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: str | None = None
    edited_answers: list[str] | None = None
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalResult(BaseModel):
    thread_id: str
    status: JobStatus | Literal["sent", "message_rejected", "rechecking"]
    run_id: str | None = None
    detail: str = ""


class RegenerateIn(BaseModel):
    paragraph_index: int = Field(ge=0)
    instruction: str | None = None


# ---------- pipeline ----------

Stage = Literal["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]


class PipelineCard(BaseModel):
    job_id: str
    title: str
    stage: Stage
    bid_amount: float | None = None
    connects_spent: int | None = None
    updated_at: datetime | None = None
    proposal_id: str | None = None
    conversation_thread_id: str | None = None


class PipelineOut(BaseModel):
    columns: dict[Stage, list[PipelineCard]]


# ---------- messages ----------


class MessageOut(BaseModel):
    message_id: str
    sender: Literal["client", "freelancer"]
    text: str
    sent_at: datetime | None = None


class ConversationSummary(BaseModel):
    conversation_id: str
    job_id: str | None = None
    job_title: str | None = None
    client_name: str | None = None
    last_message_at: datetime | None = None
    unread: bool = False
    pending_reply: bool = False
    intent: str | None = None
    flags: list[str] = Field(default_factory=list)


class ConversationOut(BaseModel):
    conversation_id: str
    job_title: str | None = None
    client_name: str | None = None
    messages: list[MessageOut]
    suggested_reply: str | None = None
    proposed_slots: list[str] = Field(default_factory=list)
    intent: str | None = None
    flags: list[str] = Field(default_factory=list)
    graph_thread_id: str | None = None
    awaiting_approval: bool = False
    pending_approval: ApprovalRequest | None = None
    compliance: ComplianceVerdict | None = None


# ---------- runs ----------


class RunEvent(BaseModel):
    seq: int
    at: datetime
    node: str
    kind: Literal["start", "end", "update", "interrupt", "error", "custom", "done"]
    summary: str = ""
    data: dict[str, Any] | None = None


class RunOut(BaseModel):
    run_id: str
    thread_id: str
    graph: Literal["bid", "conversation"]
    job_id: str | None = None
    status: Literal["queued", "running", "interrupted", "done", "failed", "needs_attention"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float | None = None
    trace_url: str | None = None
    conversation_id: str | None = None
    events: list[RunEvent] = Field(default_factory=list)


# ---------- analytics ----------


class CategoryRate(BaseModel):
    category: str
    proposals: int
    replies: int
    hires: int
    reply_rate: float
    hire_rate: float


class AnalyticsOut(BaseModel):
    proposals_sent: int
    reply_rate: float
    hire_rate: float
    connects_spent: int
    by_category: list[CategoryRate]
    connects_vs_outcomes: list[dict[str, Any]]
    cost_per_proposal_usd: float | None = None
    p50_latency_s: float | None = None
    p95_latency_s: float | None = None
    top_rejection_reasons: list[dict[str, Any]]
    jobs_analysed: int = 0
    scams_flagged: int = 0


# ---------- memory ----------


class MemoryItem(BaseModel):
    namespace: Literal["style", "outcome"]
    key: str
    value: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MemoryOut(BaseModel):
    items: list[MemoryItem]


# ---------- health ----------


class ServiceStatus(BaseModel):
    name: str
    status: Literal["ok", "degraded", "down"]
    detail: str = ""


class HealthOut(BaseModel):
    status: Literal["ok", "degraded", "down"]
    services: list[ServiceStatus]
    queued_while_degraded: int = 0
