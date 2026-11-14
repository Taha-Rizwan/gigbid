"""Job Analyst: structured JobSpec from the post. No MCP access needed."""

from __future__ import annotations

from langgraph.runtime import Runtime

from agent import llm
from agent.context import RunContext
from agent.handoffs import JobSpec
from agent.nodes.common import job_text, node


@node("job_analyst")
async def job_analyst(state: dict, runtime: Runtime[RunContext]) -> dict:
    job = state["job"]
    spec = await llm.structured("analyst", JobSpec, llm.prompt_messages("analyst", job_text(job, runtime.context.datamark)))
    spec.job_id, spec.title, spec.category = job.job_id, job.title, job.category
    if not spec.screening_questions:
        spec.screening_questions = job.screening_questions
    if job.budget and spec.budget_max is None:
        spec.budget_max = job.budget
    if spec.is_hourly is None:
        spec.is_hourly = job.is_hourly
    return {"job_spec": spec}
