"""R&D question A: does tool granularity change how well one agent picks and fills tools?

40 hand-written tasks (evals/datasets/tool_tasks.jsonl, expected calls written against the real MCP
tool names, with per-set overrides where the fine set splits a tool) run through one ReAct agent
(langgraph.prebuilt.create_react_agent, small tier of the profile) holding one of four tool sets:
  fine    18 narrow tools (thin wrappers, defined only here, over the same MCP tools)
  coarse   2 tools (marketplace(action=...), portfolio(action=...)) over the same MCP tools
  mcp     our real read-only MCP tools with their current descriptions
  mcp_rewritten   the same tools with rewritten descriptions (when-to-use + argument examples)
All tools execute for real (eval GigSim + portfolio index); nothing writes.

Metrics per set: tool-selection accuracy (every expected tool called), argument accuracy (share of
expected calls matched with their args subset; strings match case-insensitively as substrings),
exact task success (both), extra calls, tokens and latency per task.

    python -m evals.runners.tool_granularity [--sets fine,coarse,mcp,mcp_rewritten] [--limit 40]
Output: evals/results/tool_granularity.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from evals.runners.common import (
    ANTHROPIC_CAP_USD,
    DATASETS_DIR,
    DailyLimitReached,
    Harness,
    RecordCache,
    _log_spend,
    add_common_args,
    anthropic_spend,
    call_with_backoff,
    header,
    load_jsonl,
    setup,
    use_profile,
    write_json,
)

READ_TOOLS = ["search_jobs", "get_job", "get_client_history", "get_connects_balance", "get_market_stats",
              "get_policy", "list_proposals", "search_evidence", "get_case_study", "list_skills"]
SYSTEM = ("You help a freelancer whose portfolio persona is ai_ml. Use the tools to gather what the task needs, "
          "then answer in one or two sentences. Call only the tools you need. Never create, submit or send anything.")

REWRITTEN = {
    "search_jobs": "Search OPEN marketplace jobs. Use `query` for keywords (e.g. query='airflow') or `category` for a "
                   "taxonomy category (ml_ai, data_engineering, data_analysis, web_fullstack, automation_scraping...). "
                   "Returns summaries only; use get_job for one job's full post.",
    "get_job": "Everything about ONE job by job_id (ids look like '~01...'): description, budget or hourly range, "
               "is_hourly, screening questions, Connects cost to apply, client_id. Use for any question about a "
               "specific job.",
    "get_client_history": "Everything about ONE client by client_id ('cl_...'): total spent, hires, hire rate, rating, "
                          "payment verification and reviews from freelancers. Use to judge whether a client is reliable.",
    "get_connects_balance": "The freelancer's own Connects balance and weekly allowance. No arguments.",
    "get_market_stats": "Market price quantiles for a category (e.g. category='ml_ai'): posted hourly, fixed-price "
                        "budgets and realised hourly rates. Use for 'what does X usually pay'.",
    "get_policy": "The marketplace's current proposal rules, required disclosures and Connects formula. No arguments.",
    "list_proposals": "The freelancer's own past proposals; optional status filter: submitted, viewed, replied, "
                      "interview, hired, declined.",
    "search_evidence": "Search the freelancer's OWN portfolio for proof of a skill or requirement (requirement='churn "
                       "model'). Narrow with filters={'types': ['case'|'repo'|'review'|'proposal'|'cv']} and, for past "
                       "proposals, filters={'outcomes': ['won'|'replied'|'ignored']}.",
    "get_case_study": "Full text of ONE portfolio item by evidence_id (e.g. 'ai_ml:case:churn-uplift-telco').",
    "list_skills": "Skills in the freelancer's portfolio with how many items mention each. No arguments needed.",
}


# ----------------------------------------------------------------------------- expected calls per set

def to_fine(call: dict) -> dict:
    t, a = call["tool"], dict(call["args_subset"])
    if t == "search_jobs":
        return {"tool": "search_jobs_by_keyword", "args_subset": {"query": a["query"]}} if "query" in a else \
            {"tool": "list_jobs_in_category", "args_subset": {"category": a.get("category")}}
    if t == "search_evidence":
        return {"tool": "search_case_studies", "args_subset": {"query": a["requirement"]}}
    m = {"get_job": "get_job_details", "get_client_history": "get_client_profile", "get_market_stats": "get_hourly_rate_stats",
         "get_policy": "get_policy_rules", "list_proposals": "list_my_proposals", "get_case_study": "get_evidence_item",
         "list_skills": "list_portfolio_skills"}
    return {"tool": m.get(t, t), "args_subset": a}


def to_coarse(call: dict) -> dict:
    t, a = call["tool"], dict(call["args_subset"])
    if t == "search_evidence":
        args = {"action": "search", "query": a["requirement"]} | (a.get("filters") or {})
        return {"tool": "portfolio", "args_subset": args}
    if t == "get_case_study":
        return {"tool": "portfolio", "args_subset": {"action": "get", "evidence_id": a["evidence_id"]}}
    if t == "list_skills":
        return {"tool": "portfolio", "args_subset": {"action": "skills"}}
    return {"tool": "marketplace", "args_subset": {"action": t} | a}


def expected_for(task: dict, tool_set: str) -> list[dict]:
    calls = task["expected_calls"]
    if tool_set == "fine":
        return task.get("expected_fine") or [to_fine(c) for c in calls]
    if tool_set == "coarse":
        return task.get("expected_coarse") or [to_coarse(c) for c in calls]
    return calls


def arg_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(arg_match(v, actual.get(k)) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and {str(x).lower() for x in expected} <= {str(x).lower() for x in actual}
    if isinstance(expected, str):
        return isinstance(actual, str) and expected.lower() in actual.lower()
    return expected == actual


def score_task(expected: list[dict], calls: list[dict]) -> dict:
    names = [c["tool"] for c in calls]
    remaining = list(names)
    sel = True
    for e in expected:
        if e["tool"] in remaining:
            remaining.remove(e["tool"])
        else:
            sel = False
    matched = sum(1 for e in expected if any(c["tool"] == e["tool"] and arg_match(e["args_subset"], c["args"]) for c in calls))
    exp_names = {e["tool"] for e in expected}
    return {"selection_correct": sel, "args_matched": matched, "args_expected": len(expected),
            "arg_accuracy": matched / len(expected) if expected else None,
            "exact": sel and matched == len(expected), "n_calls": len(calls),
            "extra_calls": sum(1 for n in names if n not in exp_names)}


# ----------------------------------------------------------------------------- tool sets

def build_sets(box) -> dict[str, list]:
    from langchain_core.tools import StructuredTool

    from agent.mcp_client import _parse

    async def call(name: str, **args):
        args = {k: v for k, v in args.items() if v is not None}
        try:
            out = _parse(await box.tools[name].ainvoke(args))
        except Exception as exc:  # noqa: BLE001
            out = {"error": str(exc)[:300]}
        return out

    def short(x: Any, n: int = 3500) -> str:
        return json.dumps(x, default=str)[:n]

    def tool(fn, name: str, desc: str):
        return StructuredTool.from_function(coroutine=fn, name=name, description=desc)

    async def search_jobs_by_keyword(query: str, limit: int = 10) -> str:
        return short(await call("search_jobs", query=query, limit=limit))

    async def list_jobs_in_category(category: str, limit: int = 10) -> str:
        return short(await call("search_jobs", category=category, limit=limit))

    async def get_job_details(job_id: str) -> str:
        return short(await call("get_job", job_id=job_id))

    async def get_job_budget(job_id: str) -> str:
        j = await call("get_job", job_id=job_id)
        return short({k: j.get(k) for k in ("job_id", "is_hourly", "budget", "hourly_low", "hourly_high", "connects_cost")}
                     if isinstance(j, dict) else j)

    async def get_job_screening_questions(job_id: str) -> str:
        j = await call("get_job", job_id=job_id)
        return short({"job_id": job_id, "screening_questions": j.get("screening_questions")} if isinstance(j, dict) else j)

    async def get_client_profile(client_id: str) -> str:
        c = await call("get_client_history", client_id=client_id)
        return short({k: v for k, v in c.items() if k != "reviews"} if isinstance(c, dict) else c)

    async def get_client_reviews(client_id: str) -> str:
        c = await call("get_client_history", client_id=client_id)
        return short({"client_id": client_id, "reviews": c.get("reviews")} if isinstance(c, dict) else c)

    async def get_connects_balance() -> str:
        return short(await call("get_connects_balance"))

    async def get_hourly_rate_stats(category: str) -> str:
        s = await call("get_market_stats", category=category)
        return short({k: s.get(k) for k in ("hourly", "realised_hourly")} if isinstance(s, dict) else s)

    async def get_fixed_price_stats(category: str) -> str:
        s = await call("get_market_stats", category=category)
        return short({"fixed": s.get("fixed")} if isinstance(s, dict) else s)

    async def get_policy_rules() -> str:
        return short(await call("get_policy"))

    async def list_my_proposals(status: str | None = None) -> str:
        return short(await call("list_proposals", status=status))

    def search_typed(types: list[str]):
        async def fn(query: str, outcome: str | None = None) -> str:
            f = {"types": types} | ({"outcomes": [outcome]} if outcome else {})
            return short(await call("search_evidence", requirement=query, filters=f, k=5))
        return fn

    async def get_evidence_item(evidence_id: str) -> str:
        return short(await call("get_case_study", evidence_id=evidence_id))

    async def list_portfolio_skills() -> str:
        return short(await call("list_skills"))

    fine = [
        tool(search_jobs_by_keyword, "search_jobs_by_keyword", "Search open jobs by keyword."),
        tool(list_jobs_in_category, "list_jobs_in_category", "List open jobs in a taxonomy category."),
        tool(get_job_details, "get_job_details", "Full post of one job."),
        tool(get_job_budget, "get_job_budget", "Budget / hourly range, rate type and Connects cost of one job."),
        tool(get_job_screening_questions, "get_job_screening_questions", "Screening questions of one job."),
        tool(get_client_profile, "get_client_profile", "Client stats: spend, hires, hire rate, rating, payment verified."),
        tool(get_client_reviews, "get_client_reviews", "Reviews freelancers left for a client."),
        tool(get_connects_balance, "get_connects_balance", "My Connects balance."),
        tool(get_hourly_rate_stats, "get_hourly_rate_stats", "Hourly rate quantiles (posted and realised) for a category."),
        tool(get_fixed_price_stats, "get_fixed_price_stats", "Fixed-price budget quantiles for a category."),
        tool(get_policy_rules, "get_policy_rules", "Marketplace proposal rules and required disclosures."),
        tool(list_my_proposals, "list_my_proposals", "My proposals, optionally filtered by status."),
        tool(search_typed(["case", "cv"]), "search_case_studies", "Search my case studies and CV."),
        tool(search_typed(["repo"]), "search_repositories", "Search my code repositories."),
        tool(search_typed(["review"]), "search_client_reviews", "Search reviews clients wrote about me."),
        tool(search_typed(["proposal"]), "search_past_proposals", "Search my past proposals; optional outcome won/replied/ignored."),
        tool(get_evidence_item, "get_evidence_item", "Full text of one portfolio item by evidence id."),
        tool(list_portfolio_skills, "list_portfolio_skills", "Skills in my portfolio."),
    ]

    async def marketplace(action: str, job_id: str | None = None, client_id: str | None = None, query: str | None = None,
                          category: str | None = None, status: str | None = None) -> str:
        """Marketplace reads. action: search_jobs | get_job | get_client_history | get_connects_balance |
        get_market_stats | get_policy | list_proposals."""
        args = {"search_jobs": {"query": query or "", "category": category, "limit": 10}, "get_job": {"job_id": job_id},
                "get_client_history": {"client_id": client_id}, "get_market_stats": {"category": category},
                "list_proposals": {"status": status}}.get(action, {})
        if action not in READ_TOOLS[:7]:
            return short({"error": f"unknown action {action}"})
        return short(await call(action, **args))

    async def portfolio(action: str, query: str | None = None, evidence_id: str | None = None,
                        types: list[str] | None = None, outcomes: list[str] | None = None) -> str:
        """My portfolio. action: search (query, optional types/outcomes) | get (evidence_id) | skills."""
        if action == "search":
            f = {k: v for k, v in {"types": types, "outcomes": outcomes}.items() if v}
            return short(await call("search_evidence", requirement=query or "", filters=f or None, k=5))
        if action == "get":
            return short(await call("get_case_study", evidence_id=evidence_id or ""))
        if action == "skills":
            return short(await call("list_skills"))
        return short({"error": f"unknown action {action}"})

    coarse = [tool(marketplace, "marketplace", marketplace.__doc__), tool(portfolio, "portfolio", portfolio.__doc__)]
    mcp = [box.tools[n] for n in READ_TOOLS if n in box.tools]
    mcp_rw = [t.model_copy(update={"description": REWRITTEN.get(t.name, t.description)}) for t in mcp]
    return {"fine": fine, "coarse": coarse, "mcp": mcp, "mcp_rewritten": mcp_rw}


async def run_task(model, model_name: str, tools: list, task: dict) -> dict:
    from langchain_core.messages import AIMessage
    from langgraph.prebuilt import create_react_agent

    from evals.runners.agent_models import messages_usage

    agent = create_react_agent(model, tools, prompt=SYSTEM)
    t0 = time.perf_counter()

    async def go():
        return await agent.ainvoke({"messages": [("user", task["task"])]}, {"recursion_limit": 14})

    try:
        out = await call_with_backoff(model_name, 3000, go)
        msgs = out["messages"]
        err = None
    except DailyLimitReached:
        raise
    except Exception as exc:  # noqa: BLE001 - recursion limit etc.: score the calls made so far is not possible
        msgs, err = [], f"{type(exc).__name__}: {str(exc)[:200]}"
    calls = [{"tool": tc["name"], "args": tc["args"]} for m in msgs if isinstance(m, AIMessage) for tc in m.tool_calls]
    return {"calls": calls, "usage": messages_usage(msgs, model_name), "latency_s": round(time.perf_counter() - t0, 3),
            "error": err, "final": (msgs[-1].content if msgs else "")[:500] if msgs else None}


async def main(args) -> None:
    setup(args.gigsim)
    profile = use_profile(args.profile)
    from evals.metrics import mean, percentile
    from evals.runners.agent_models import chat_model

    tasks = load_jsonl(args.tasks)[: args.limit or None]
    model, model_name = chat_model("small", profile)
    cache = RecordCache("tool_granularity")
    sets = args.sets.split(",")
    res: dict[str, dict] = {}
    stop = None
    async with Harness() as h:
        h.use_persona("ai_ml")
        toolsets = build_sets(h.box)
        for s in sets:
            sem = asyncio.Semaphore(args.concurrency)
            desc_hash = RecordCache.key([(t.name, t.description) for t in toolsets[s]])

            async def one(task, s=s, desc_hash=desc_hash):
                nonlocal stop
                key = cache.key(s, task, model_name, desc_hash, SYSTEM)
                if (rec := cache.get(key)) is not None:
                    return rec
                if stop:
                    return None
                if "claude" in model_name and anthropic_spend() >= ANTHROPIC_CAP_USD:
                    stop = "Anthropic eval budget cap reached"
                    return None
                async with sem:  # noqa: B023 - awaited within this iteration
                    try:
                        r = await run_task(model, model_name, toolsets[s], task)
                    except DailyLimitReached as exc:
                        stop = str(exc)
                        return None
                if "claude" in model_name:
                    _log_spend(model_name, f"react_{s}", r["usage"]["cost_usd"])
                r |= {"task_id": task["task_id"], "kind": task["kind"]} | score_task(expected_for(task, s), r["calls"])
                if r["error"]:
                    return r  # not cached: transient failures get retried on the next run
                return cache.put(key, r)

            recs = [x for x in await asyncio.gather(*(one(t) for t in tasks)) if x]
            ok = [r for r in recs if not r.get("error")]

            def agg(rs):
                return {"n": len(rs),
                        "tool_selection_accuracy": mean(1.0 if r["selection_correct"] else 0.0 for r in rs),
                        "argument_accuracy": mean(r["arg_accuracy"] for r in rs),
                        "exact_task_success": mean(1.0 if r["exact"] else 0.0 for r in rs),
                        "calls_per_task": mean(r["n_calls"] for r in rs), "extra_calls_per_task": mean(r["extra_calls"] for r in rs),
                        "tokens_per_task": mean(r["usage"]["tokens"] for r in rs),
                        "cost_usd_per_task": mean(r["usage"]["cost_usd"] for r in rs),
                        "latency_p50_s": percentile([r["latency_s"] for r in rs], 50),
                        "latency_p95_s": percentile([r["latency_s"] for r in rs], 95)}

            res[s] = {"n_tools": len(toolsets[s]), "tool_names": [t.name for t in toolsets[s]],
                      "status": "complete" if len(ok) == len(tasks) else "partial",
                      "n_errors": len(recs) - len(ok), "errors": [r["error"] for r in recs if r.get("error")][:5],
                      **agg(ok), "single_step": agg([r for r in ok if r["kind"] == "single"]),
                      "multi_step": agg([r for r in ok if r["kind"] == "multi"]),
                      "per_task": [{k: r[k] for k in ("task_id", "selection_correct", "arg_accuracy", "n_calls", "calls")}
                                   for r in ok]}
            print(f"[{s}] n={len(ok)} sel={res[s]['tool_selection_accuracy']} args={res[s]['argument_accuracy']}")
    payload = header("tool_granularity", args, len(tasks), {"model": model_name, "system_prompt": SYSTEM}, profile) | {
        "status": "complete" if all(v["status"] == "complete" for v in res.values()) and not stop else "partial",
        "model_profile": profile, "agent_model": model_name, "n_tasks": len(tasks), "tasks_file": "evals/datasets/tool_tasks.jsonl",
        "sets": res, "stopped_early": stop, "anthropic_spend_usd_all_evals": anthropic_spend(),
        "note": "Tasks and expected calls are hand-written by the eval author (single rater).",
    }
    write_json(f"tool_granularity{args.tag}.json", payload, args.out_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--tasks", default=str(DATASETS_DIR / "tool_tasks.jsonl"))
    ap.add_argument("--sets", default="fine,coarse,mcp,mcp_rewritten")
    from evals.runners.common import run

    run(main(ap.parse_args()))
