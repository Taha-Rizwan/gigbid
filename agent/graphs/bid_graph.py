r"""Bid graph: one thread per job.

intake -> Send(job_analyst | risk_assessor | fit_matcher) in parallel -> decide
  skip/watch -> END
  bid -> pricing -> writer -> claim_verifier -> critic --(fail, < 2 revisions)--> writer
                                                     \-> compliance --blocked--> needs_attention
                                                                    \-> prepare_submission (dry run)
  -> approval (interrupt) --approve--> submit -> END
                          --edit-----> recheck (compliance on the edited text) -> submit | approval
                          --reject---> rejected -> END
"""

from __future__ import annotations

import hashlib
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy, Send, interrupt

from agent.context import RunContext
from agent.guardrails import strip_citations
from agent.handoffs import (
    ApprovalRequest,
    ApprovalResponse,
    BidDecision,
    Decision,
    Job,
    ProposalDraft,
)
from agent.memory.promotion_rules import observe_edit, observe_rejection
from agent.nodes.analyst import job_analyst
from agent.nodes.common import node
from agent.nodes.compliance import check as compliance_check
from agent.nodes.compliance import compliance_guard
from agent.nodes.critic import critic
from agent.nodes.fit_matcher import fit_matcher
from agent.nodes.pricing import pricing_strategist
from agent.nodes.risk_assessor import risk_assessor
from agent.nodes.verifier import claim_verifier
from agent.nodes.writer import proposal_writer
from agent.settings import config
from agent.state import BidState


def transient(exc: Exception) -> bool:
    """Retry rate limits, timeouts and 5xx from model providers or the marketplace; never logic errors."""
    from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable

    if isinstance(exc, MarketplaceUnavailable):
        return False  # surfaced to the API, which queues the work (degraded mode)
    if isinstance(exc, MarketplaceError):
        return exc.status == 429
    name = type(exc).__name__
    return name in {"RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError",
                    "TimeoutError", "ReadTimeout", "ServiceUnavailableError"} or "429" in str(exc)[:200]


RETRY = RetryPolicy(max_attempts=6, initial_interval=5.0, backoff_factor=2.0, max_interval=60.0, retry_on=transient)


@node("intake")
async def intake(state: BidState, runtime: Runtime[RunContext]) -> dict:
    tools = runtime.context.toolbox.for_agent("intake")
    raw = await tools.call("get_job", job_id=state["job_id"])
    job = Job(**{k: v for k, v in raw.items() if k in Job.model_fields and v is not None},
              source=raw.get("marketplace", "gigsim"))
    return {"job": job, "status": "analysing", "revisions": 0}


def fan_out(state: BidState) -> list[Send]:
    return [Send("job_analyst", state), Send("risk_assessor", state), Send("fit_matcher", state)]


@node("decide")
async def decide(state: BidState, runtime: Runtime[RunContext]) -> dict:
    t = config()["thresholds"]
    risk, fit, job = state["risk_report"], state["fit_report"], state["job"]
    profile = state.get("profile") or {}
    reasons: list[str] = []
    decision = Decision.bid
    if risk.score > t["maximum_risk_score"]:
        decision = Decision.skip
        reasons.append(f"risk {risk.score:.2f} above limit {t['maximum_risk_score']} ({', '.join(risk.flags) or 'risk'})")
    if fit.score < t["watch_fit_score"]:
        decision = Decision.skip
        reasons.append(f"fit {fit.score:.2f} below {t['watch_fit_score']}: missing {', '.join(fit.missing_skills[:4]) or 'evidence'}")
    elif fit.score < t["minimum_fit_score"] and decision == Decision.bid:
        decision = Decision.watch
        reasons.append(f"fit {fit.score:.2f} below bid threshold {t['minimum_fit_score']}")
    top = job.hourly_high if job.is_hourly else job.budget
    floor = profile.get("hourly_floor", 0) if job.is_hourly else profile.get("fixed_floor", 0)
    if top and floor and top < floor * 0.8 and decision == Decision.bid:
        decision = Decision.watch
        reasons.append(f"client's top rate {top} is well under your floor {floor}")
    if decision == Decision.bid:
        reasons.append(f"fit {fit.score:.2f}, risk {risk.score:.2f}: {'; '.join(fit.reasons[:2])}")
    d = BidDecision(decision=decision, reasons=reasons, fit_score=fit.score, risk_score=risk.score)
    status = {"bid": "drafting", "watch": "watch", "skip": "skipped"}[decision.value]
    return {"decision": d, "status": status}


def after_decide(state: BidState) -> str:
    return "pricing_strategist" if state["decision"].decision == Decision.bid else END


def after_critic(state: BidState) -> str:
    last = state["critiques"][-1]
    if not last.passed and state.get("revisions", 0) < config()["budgets"]["max_revisions"]:
        return "proposal_writer"
    return "compliance_guard"


def after_compliance(state: BidState) -> str:
    return "prepare_submission" if state["compliance"].allowed else END


def final_text(draft: ProposalDraft) -> tuple[str, list[str]]:
    return strip_citations(draft.cover_letter), [strip_citations(a) for a in draft.screening_answers]


def idem_key(state: BidState, step: str) -> str:
    d = state["draft"]
    basis = f"{state['user_id']}|{state['job_id']}|{d.version}|{hashlib.sha256(d.cover_letter.encode()).hexdigest()}"
    return f"{step}-{hashlib.sha256(basis.encode()).hexdigest()[:40]}"


@node("prepare_submission")
async def prepare_submission(state: BidState, runtime: Runtime[RunContext]) -> dict:
    """dry_run preview of exactly what will be sent and what it costs, for the approval screen."""
    tools = runtime.context.toolbox.for_agent("submitter")
    letter, answers = final_text(state["draft"])
    price = state["price_quote"]
    preview = await tools.call(
        "create_proposal_draft",
        draft={"job_id": state["job_id"], "cover_letter": letter, "screening_answers": answers,
               "bid_amount": price.amount, "rate_type": price.rate_type},
        idempotency_key=idem_key(state, "draft"), dry_run=True,
    )
    return {"dry_run": {"cover_letter": letter, "screening_answers": answers, "bid_amount": price.amount,
                        "rate_type": price.rate_type, "connects_cost": (preview.get("result") or {}).get("connects_cost",
                                                                                                         price.connects_cost),
                        "marketplace": preview.get("marketplace")},
            "status": "awaiting_approval"}


async def approval(state: BidState, runtime: Runtime[RunContext]) -> dict:
    """Human approval (LangGraph interrupt). Nothing is sent and no Connects are spent before this."""
    req = ApprovalRequest(
        kind="proposal", thread_id=state["job_id"], draft=state["draft"], evidence=state.get("evidence") or [],
        risk=state.get("risk_report"), price=state.get("price_quote"), critiques=state.get("critiques") or [],
        compliance=state.get("compliance"), dry_run=state.get("dry_run"),
    )
    await runtime.context.event("approval", "interrupt", "waiting for your approval", {"dry_run": state.get("dry_run")})
    answer = ApprovalResponse(**interrupt(req.model_dump(mode="json")))
    return {"approval": answer}


def after_approval(state: BidState) -> str:
    return {"approve": "submit", "edit": "recheck", "reject": "rejected"}[state["approval"].action]


@node("recheck")
async def recheck(state: BidState, runtime: Runtime[RunContext]) -> dict:
    """User edits are diffed (style memory), applied, and re-checked by Compliance."""
    a, draft = state["approval"], state["draft"]
    before = strip_citations(draft.cover_letter)
    edited = draft.model_copy(update={
        "cover_letter": a.edited_text or draft.cover_letter,
        "screening_answers": a.edited_answers or draft.screening_answers,
        "version": draft.version + 1,
    })
    if runtime.store is not None and a.edited_text:
        learned = await observe_edit(runtime.store, state["user_id"], before, a.edited_text)
        await runtime.context.event("style_memory", "custom", f"edit observed; promoted {learned.get('promoted')}", learned)
    v = await compliance_check(edited.cover_letter + "\n\n" + "\n\n".join(edited.screening_answers), None,
                               state.get("profile"))
    letter = v.cleaned_text if v.cleaned_text and v.violations else edited.cover_letter
    edited = edited.model_copy(update={"cover_letter": letter})
    return {"draft": edited, "compliance": v}


def after_recheck(state: BidState) -> str:
    v = state["compliance"]
    return "submit" if v.allowed and not v.violations else "prepare_submission"


@node("submit")
async def submit(state: BidState, runtime: Runtime[RunContext]) -> dict:
    """Exactly-once: idempotency keys derive from (user, job, draft version, text), so a crash and
    replay after approval returns the stored first result instead of submitting again."""
    tools = runtime.context.toolbox.for_agent("submitter")
    letter, answers = final_text(state["draft"])
    price = state["price_quote"]
    created = await tools.call(
        "create_proposal_draft",
        draft={"job_id": state["job_id"], "cover_letter": letter, "screening_answers": answers,
               "bid_amount": price.amount, "rate_type": price.rate_type},
        idempotency_key=idem_key(state, "draft"),
    )
    draft_id = created["result"]["draft_id"]
    sent = await tools.call("submit_proposal", draft_id=draft_id, idempotency_key=idem_key(state, "submit"))
    return {"submission": {"draft_id": draft_id, **sent["result"], "replay": sent.get("idempotent_replay", False),
                           "marketplace": sent.get("marketplace")},
            "status": "submitted"}


@node("rejected")
async def rejected(state: BidState, runtime: Runtime[RunContext]) -> dict:
    reason = state["approval"].reason or ""
    if runtime.store is not None and reason:
        learned = await observe_rejection(runtime.store, state["user_id"], reason)
        await runtime.context.event("style_memory", "custom", "rejection observed", learned)
    return {"status": "rejected"}


def build(checkpointer=None, store=None):
    g = StateGraph(BidState, context_schema=RunContext)
    g.add_node("intake", intake, retry_policy=RETRY)
    g.add_node("job_analyst", job_analyst, retry_policy=RETRY)
    g.add_node("risk_assessor", risk_assessor, retry_policy=RETRY)
    g.add_node("fit_matcher", fit_matcher, retry_policy=RETRY)
    g.add_node("decide", decide, defer=True, retry_policy=RETRY)  # waits for all three parallel branches
    g.add_node("pricing_strategist", pricing_strategist, retry_policy=RETRY)
    g.add_node("proposal_writer", proposal_writer, retry_policy=RETRY)
    g.add_node("claim_verifier", claim_verifier, retry_policy=RETRY)
    g.add_node("critic", critic, retry_policy=RETRY)
    g.add_node("compliance_guard", compliance_guard, retry_policy=RETRY)
    g.add_node("prepare_submission", prepare_submission, retry_policy=RETRY)
    g.add_node("approval", approval)
    g.add_node("recheck", recheck, retry_policy=RETRY)
    g.add_node("submit", submit, retry_policy=RETRY)
    g.add_node("rejected", rejected, retry_policy=RETRY)

    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", fan_out, ["job_analyst", "risk_assessor", "fit_matcher"])
    for n in ("job_analyst", "risk_assessor", "fit_matcher"):
        g.add_edge(n, "decide")
    g.add_conditional_edges("decide", after_decide, ["pricing_strategist", END])
    g.add_edge("pricing_strategist", "proposal_writer")
    g.add_edge("proposal_writer", "claim_verifier")
    g.add_edge("claim_verifier", "critic")
    g.add_conditional_edges("critic", after_critic, ["proposal_writer", "compliance_guard"])
    g.add_conditional_edges("compliance_guard", after_compliance, ["prepare_submission", END])
    g.add_edge("prepare_submission", "approval")
    g.add_conditional_edges("approval", after_approval, ["submit", "recheck", "rejected"])
    g.add_conditional_edges("recheck", after_recheck, ["submit", "prepare_submission"])
    g.add_edge("submit", END)
    g.add_edge("rejected", END)
    return g.compile(checkpointer=checkpointer, store=store)


def graph_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": config()["budgets"]["max_graph_steps"]}


build_bid_graph = build
