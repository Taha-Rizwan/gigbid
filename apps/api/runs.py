"""Graph execution for the API and the worker: start / resume a thread, persist run events for the
SSE stream, and mirror the final state into the jobs / proposals tables the UI reads."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import AsyncExitStack

from agent.context import RunContext
from agent.graphs import bid_graph, conversation_graph
from agent.llm import Usage
from agent.marketplace_port import MarketplaceUnavailable
from agent.mcp_client import ToolBox
from agent.memory.store import open_persistence
from agent.runner import _serialisable, resume, run_graph, start_bid
from common import db

log = logging.getLogger("gigbid.runs")


class Engine:
    """Holds the checkpointer, store and compiled graphs for one process."""

    def __init__(self):
        self.stack = AsyncExitStack()
        self.saver = self.store = None
        self.bid = self.conv = None

    async def open(self, durable: bool | None = None) -> None:
        self.saver, self.store = await open_persistence(self.stack, durable)
        self.bid = bid_graph.build(self.saver, self.store)
        self.conv = conversation_graph.build(self.saver, self.store)

    async def close(self) -> None:
        await self.stack.aclose()

    def graph_for(self, thread_id: str):
        return self.conv if thread_id.startswith("conv-") else self.bid


engine = Engine()


def langsmith_url(trace_id: str | None) -> str | None:
    import os

    if not (trace_id and os.environ.get("LANGSMITH_API_KEY")):
        return None
    return f"https://smith.langchain.com/o/-/projects/p/{os.environ.get('LANGSMITH_PROJECT', 'gigbid')}?searchModel=%7B%22filter%22%3A%22has(metadata%2C%20%27%7B%5C%22trace_id%5C%22%3A%5C%22{trace_id}%5C%22%7D%27)%22%7D"


async def new_run(user_id: str, thread_id: str, graph: str, job_id: str | None, trace_id: str) -> str:
    run_id = uuid.uuid4().hex[:16]
    await db.execute(
        "insert into runs (run_id, user_id, thread_id, graph, job_id, status, trace_url) values (%s,%s,%s,%s,%s,'queued',%s)",
        run_id, user_id, thread_id, graph, job_id, langsmith_url(trace_id),
    )
    return run_id


def _emitter(run_id: str):
    seq = {"n": 0}

    async def emit(node: str, kind: str, summary: str, data: dict | None) -> None:
        seq["n"] += 1
        await db.execute(
            "insert into run_events (run_id, seq, node, kind, summary, data) values (%s,%s,%s,%s,%s,%s) on conflict do nothing",
            run_id, seq["n"] + 1000 * 0, node, kind, summary[:500], json.dumps(_serialisable(data), default=str) if data else None,
        )

    async def init() -> None:
        row = await db.fetchrow("select coalesce(max(seq),0) as m from run_events where run_id=%s", run_id)
        seq["n"] = row["m"] if row else 0

    return emit, init


async def _toolbox(user_id: str, trace_id: str) -> ToolBox:
    import os

    if os.environ.get("GIGBID_INPROCESS_MCP") == "1":
        stack = AsyncExitStack()
        box = await ToolBox.in_memory(stack)
        box._stack = stack  # type: ignore[attr-defined]
        return box
    return await ToolBox.http(user_id, trace_id)


async def execute(run_id: str, user_id: str, thread_id: str, *, start: dict | None = None,
                  answer: dict | None = None, update: dict | None = None, profile_name: str | None = None) -> dict:
    """Run one step of a thread (start, resume with an approval answer, or continue after a state update)."""
    trace_id = uuid.uuid4().hex
    emit, init = _emitter(run_id)
    await init()
    await db.execute("update runs set status='running' where run_id=%s", run_id)
    box = await _toolbox(user_id, trace_id)
    if not box.available("marketplace"):
        await db.execute("update runs set status='queued' where run_id=%s", run_id)
        raise MarketplaceUnavailable("marketplace MCP server is not reachable")
    ctx = RunContext(toolbox=box, usage=Usage(), trace_id=trace_id, emit=emit)
    graph = engine.graph_for(thread_id)
    t0 = time.perf_counter()
    try:
        if start is not None and thread_id.startswith("bid-"):
            out = await start_bid(graph, user_id, start["persona_id"], start["job_id"], start["profile"], ctx,
                                  thread_id, profile_name)
        elif start is not None:
            out = await run_graph(graph, start, thread_id, ctx, profile_name)
        elif answer is not None:
            out = await resume(graph, thread_id, answer, ctx, profile_name)
        else:
            cfg = bid_graph.graph_config(thread_id)
            if update:
                await graph.aupdate_state(cfg, update["values"], as_node=update["as_node"])
            out = await run_graph(graph, None, thread_id, ctx, profile_name)
    except MarketplaceUnavailable as exc:
        await emit("marketplace", "error", f"marketplace unavailable: {exc.detail}; queued for retry", None)
        await db.execute("update runs set status='queued' where run_id=%s", run_id)
        raise
    except Exception as exc:
        await emit("run", "error", f"{type(exc).__name__}: {str(exc)[:300]}", None)
        await db.execute("update runs set status='failed', finished_at=now() where run_id=%s", run_id)
        await mirror(user_id, thread_id, {"status": "failed"}, None)
        raise
    finally:
        if hasattr(box, "_stack"):
            await box._stack.aclose()
    status = {"interrupted": "interrupted", "done": "done", "needs_attention": "needs_attention"}[out["status"]]
    await emit("run", "done", f"run {status}", {"tokens": out["usage"]["tokens"], "cost_usd": out["usage"]["cost_usd"],
                                                "latency_s": round(time.perf_counter() - t0, 2), "by_node": out["usage"]["by_node"]})
    await db.execute(
        """update runs set status=%s, finished_at=now(), tokens=tokens+%s, cost_usd=cost_usd+%s,
           latency_s=coalesce(latency_s,0)+%s, usage=%s where run_id=%s""",
        status, out["usage"]["tokens"], out["usage"]["cost_usd"], out["latency_s"], json.dumps(out["usage"]), run_id,
    )
    await mirror(user_id, thread_id, out["state"], out)
    return out


async def mirror(user_id: str, thread_id: str, state: dict, out: dict | None) -> None:
    """Copy the parts of graph state the UI lists (inbox / pipeline) into plain tables."""
    if thread_id.startswith("conv-"):
        conv_id = thread_id.split("conv-", 1)[1].split("|", 1)[-1]
        await db.execute(
            "update conversations set state=%s, updated_at=now() where user_id=%s and conversation_id=%s",
            json.dumps(_serialisable({k: state.get(k) for k in ("intent", "flags", "reply", "status", "slots")}), default=str),
            user_id, conv_id,
        )
        return
    job_id = state.get("job_id") or thread_id.split("-", 2)[-1]
    status = state.get("status") or "new"
    if out and out["status"] == "needs_attention":
        status = "needs_attention"
    dec, fit, risk, price = state.get("decision"), state.get("fit_report"), state.get("risk_report"), state.get("price_quote")
    analysis = _serialisable({k: state.get(k) for k in ("job_spec", "risk_report", "fit_report", "price_quote", "decision")})
    await db.execute(
        """update jobs set status=%s, thread_id=%s, analysis=%s, fit_score=%s, risk_score=%s, recommendation=%s,
           price=%s, connects_cost=coalesce(%s, connects_cost), updated_at=now() where user_id=%s and job_id=%s""",
        status, thread_id, json.dumps(analysis, default=str), fit.score if fit else None, risk.score if risk else None,
        dec.decision.value if dec else None, price.amount if price else None,
        price.connects_cost if price else None, user_id, job_id,
    )
    if state.get("draft") is not None:
        sub = state.get("submission") or {}
        stage = "submitted" if status == "submitted" else "drafted"
        job = state.get("job")
        await db.execute(
            """insert into proposals (user_id, thread_id, job_id, draft_id, proposal_id, stage, bid_amount, connects_spent, category)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (user_id, thread_id) do update set draft_id=coalesce(excluded.draft_id, proposals.draft_id),
               proposal_id=coalesce(excluded.proposal_id, proposals.proposal_id),
               stage=case when proposals.stage in ('drafted','submitted') then excluded.stage else proposals.stage end,
               bid_amount=excluded.bid_amount, connects_spent=coalesce(excluded.connects_spent, proposals.connects_spent),
               updated_at=now()""",
            user_id, thread_id, job_id, sub.get("draft_id"), sub.get("proposal_id"), stage,
            price.amount if price else None, sub.get("connects_spent"), job.category if job else None,
        )
