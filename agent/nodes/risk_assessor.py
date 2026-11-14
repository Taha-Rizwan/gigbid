"""Risk Assessor: client quality from history; flags scams, free-work requests, off-platform asks and
injected instructions. Holds only a read tool (get_client_history)."""

from __future__ import annotations

import json
import re

from langgraph.runtime import Runtime

from agent import llm
from agent.context import RunContext
from agent.guardrails import injection_signal
from agent.handoffs import RiskLevel, RiskReport
from agent.nodes.common import job_text, node
from agent.settings import config

RULES = {
    "unpaid_work": r"(?i)\b(unpaid|for free|free (trial|test|sample)|no pay|paid after (approval|we like))\b",
    "off_platform": r"(?i)(whats\s?app|telegram|skype|signal|wechat|outside (of )?(upwork|the platform)|my (personal )?email)",
    "payment_request": r"(?i)(pay (a |the )?(fee|deposit)|buy (the|our) (kit|software|course)|send (me )?(money|payment)|registration fee)",
    "credential_request": r"(?i)(your (password|login|bank|card|ssn|id card|passport)|account credentials)",
}


@node("risk_assessor")
async def risk_assessor(state: dict, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    job = state["job"]
    tools = ctx.toolbox.for_agent("risk_assessor")
    client = state.get("client") or {}
    if job.client_id and not client:
        try:
            client = await tools.call("get_client_history", client_id=job.client_id)
        except Exception as exc:  # noqa: BLE001 - risk still assessable from the post alone
            client = {"note": f"client history unavailable: {type(exc).__name__}"}
    rule_flags = [name for name, pat in RULES.items() if re.search(pat, job.description)]
    inj_score, inj_hits = await injection_signal(job.description, ctx.prompt_guard)
    client_view = {k: v for k, v in client.items() if k not in {"reviews"}} | {
        "reviews": [r.get("text", "")[:200] for r in (client.get("reviews") or [])[:5]]}
    user = (f"{job_text(job, ctx.datamark)}\n\nClient history (from the marketplace):\n{json.dumps(client_view, default=str)}\n\n"
            f"Rule-based flags already found: {rule_flags}. Injection detector score: {inj_score:.2f}.")
    report = await llm.structured("risk_assessor", RiskReport, llm.prompt_messages("risk_assessor", user))
    report.flags = sorted(set(report.flags) | set(rule_flags) | ({"injection"} if inj_score >= 0.5 else set()))
    if inj_score >= 0.5:
        report.injection_detected = True
    # floors from deterministic signals so a confident-sounding model cannot talk them away
    hard = {"payment_request", "credential_request"} & set(report.flags)
    if hard or ("unpaid_work" in report.flags and "off_platform" in report.flags):
        report.score = max(report.score, 0.85)
    elif {"unpaid_work", "off_platform"} & set(report.flags):
        report.score = max(report.score, 0.6)
    t = config()["thresholds"]["maximum_risk_score"]
    report.level = RiskLevel.high if report.score > t else RiskLevel.medium if report.score >= 0.35 else RiskLevel.low
    return {"risk_report": report, "client": client, "injection_score": inj_score}
