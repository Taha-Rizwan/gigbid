"""Run a graph thread: start, stream progress, resume after approval. Shared by the API worker,
the eval runners and the CLI (python -m agent.runner <job_id> --persona ai_ml)."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from contextlib import AsyncExitStack
from typing import Any

from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from agent.context import RunContext
from agent.graphs import bid_graph
from agent.llm import BudgetExceeded, Usage, current_profile, current_usage
from agent.marketplace_port import MarketplaceUnavailable
from agent.mcp_client import ToolBox


def _serialisable(v: Any) -> Any:
    if hasattr(v, "model_dump"):
        return v.model_dump(mode="json")
    if isinstance(v, list):
        return [_serialisable(x) for x in v]
    if isinstance(v, dict):
        return {k: _serialisable(x) for k, x in v.items()}
    return v


async def run_graph(graph, inputs: dict | Command, thread_id: str, ctx: RunContext,
                    profile_name: str | None = None) -> dict[str, Any]:
    """Runs until END or an interrupt. Returns {status, state, interrupt, usage, latency_s}."""
    current_usage.set(ctx.usage)
    if profile_name:
        current_profile.set(profile_name)
    cfg = bid_graph.graph_config(thread_id)
    t0 = time.perf_counter()
    interrupt_payload = None
    status = "done"
    try:
        async for chunk in graph.astream(inputs, cfg, context=ctx, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value
                status = "interrupted"
    except (BudgetExceeded, GraphRecursionError) as exc:
        status = "needs_attention"
        await ctx.event("budget", "error", f"{type(exc).__name__}: {exc}")
    except MarketplaceUnavailable:
        raise
    snap = await graph.aget_state(cfg)
    values = snap.values or {}
    if status == "done" and values.get("status") == "needs_attention":
        status = "needs_attention"
    return {"status": status, "state": values, "interrupt": interrupt_payload, "usage": ctx.usage.as_dict(),
            "latency_s": round(time.perf_counter() - t0, 2), "next": list(snap.next)}


async def start_bid(graph, user_id: str, persona_id: str, job_id: str, profile: dict, ctx: RunContext,
                    thread_id: str | None = None, profile_name: str | None = None) -> dict:
    thread_id = thread_id or f"bid-{user_id}-{job_id}"
    return await run_graph(graph, {"user_id": user_id, "persona_id": persona_id, "job_id": job_id,
                                   "profile": profile}, thread_id, ctx, profile_name) | {"thread_id": thread_id}


async def resume(graph, thread_id: str, answer: dict, ctx: RunContext, profile_name: str | None = None) -> dict:
    return await run_graph(graph, Command(resume=answer), thread_id, ctx, profile_name) | {"thread_id": thread_id}


async def _cli() -> None:
    import common  # noqa: F401  (event loop policy on Windows)
    from agent.memory.store import open_persistence

    ap = argparse.ArgumentParser(description="Run the bid graph on one GigSim job")
    ap.add_argument("job_id")
    ap.add_argument("--persona", default="ai_ml")
    ap.add_argument("--user", default="cli-user")
    ap.add_argument("--approve", action="store_true", help="auto-approve at the interrupt (dev only)")
    ap.add_argument("--durable", action="store_true", help="use the Postgres checkpointer")
    args = ap.parse_args()

    async with AsyncExitStack() as stack:
        saver, store = await open_persistence(stack, durable=args.durable)
        graph = bid_graph.build(saver, store)
        box = await ToolBox.in_memory(stack)

        async def emit(node: str, kind: str, summary: str, data: dict | None) -> None:
            print(f"  [{kind:9}] {node:20} {summary}")

        ctx = RunContext(toolbox=box, usage=Usage(), trace_id=uuid.uuid4().hex, emit=emit)
        profile = {"hourly_floor": 40, "fixed_floor": 300, "weekly_connects_budget": 200}
        out = await start_bid(graph, args.user, args.persona, args.job_id, profile, ctx,
                              thread_id=f"cli-{uuid.uuid4().hex[:8]}")
        st = out["state"]
        print("\nSTATUS:", out["status"], "| decision:", st.get("decision") and st["decision"].decision,
              "| latency", out["latency_s"], "s | usage", json.dumps({k: out["usage"][k] for k in ("tokens", "cost_usd")}))
        if st.get("draft"):
            print("\n--- DRAFT ---\n" + st["draft"].cover_letter)
            print("\nverification:", st.get("verification"))
            print("critiques:", [(c.passed, c.issues) for c in st.get("critiques", [])])
        if out["status"] == "interrupted" and args.approve:
            res = await resume(graph, out["thread_id"], {"action": "approve"}, ctx)
            print("\nAFTER APPROVAL:", res["status"], _serialisable(res["state"].get("submission")))


if __name__ == "__main__":
    asyncio.run(_cli())
