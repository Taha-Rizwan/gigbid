"""Pricing Strategist: a bid from market statistics, client spend and the user's floor, and whether
the Connects cost is worth it. Deterministic by design (explainable and cheap); every number in the
rationale comes from a tool result or config."""

from __future__ import annotations

from langgraph.runtime import Runtime

from agent.context import RunContext
from agent.handoffs import PriceQuote
from agent.memory.promotion_rules import outcome_hint
from agent.nodes.common import node
from agent.settings import config

USD_PER_CONNECT = 0.15


def _band(stats: dict, key: str) -> tuple[float | None, float | None, float | None]:
    b = (stats or {}).get(key) or {}
    return b.get("p25"), b.get("p50"), b.get("p75")


def quote(job, spec, fit_score: float, client: dict, stats: dict, profile: dict, policy: dict,
          balance: int | None, spent_this_week: int, hint: dict | None) -> PriceQuote:
    hourly = bool(job.is_hourly if job.is_hourly is not None else (spec.is_hourly if spec else False))
    floor_h = float(profile.get("hourly_floor", 35))
    floor_f = float(profile.get("fixed_floor", 150))
    why: list[str] = []
    if hourly:
        p25, p50, p75 = _band(stats, "realised_hourly")
        if p50 is None:
            p25, p50, p75 = _band(stats, "hourly")
        target = (p75 if fit_score >= 0.8 else p50) or floor_h
        why.append(f"market realised hourly p25/p50/p75 = {p25}/{p50}/{p75}; fit {fit_score:.2f} -> aim at "
                   f"{'p75' if fit_score >= 0.8 else 'p50'}")
        if job.hourly_high:
            target = min(target, job.hourly_high)
            why.append(f"capped at the client's range top ({job.hourly_high})")
        if job.hourly_low and target < job.hourly_low:
            target = job.hourly_low
        amount = max(target, floor_h)
        if amount == floor_h and target < floor_h:
            why.append(f"raised to your hourly floor ({floor_h})")
        value = amount * 20
    else:
        p25, p50, p75 = _band(stats, "fixed")
        budget = job.budget or (spec.budget_max if spec else None)
        if budget:
            amount = budget * (1.0 if fit_score >= 0.8 else 0.95)
            why.append(f"client budget {budget}; bid {'at' if fit_score >= 0.8 else '5% under'} budget for fit {fit_score:.2f}")
        else:
            amount = p50 or floor_f
            why.append(f"no budget given; market fixed-price median {p50}")
        if amount < floor_f:
            why.append(f"raised to your fixed floor ({floor_f})")
            amount = floor_f
        value = amount
    spend = (client or {}).get("total_spent")
    if spend:
        why.append(f"client has spent ${spend:,.0f} on the platform")
    cost = int(job.connects_cost or 0)
    cfg_policy = config()["policy"]
    extra = cfg_policy.get("connects_extra_if_proposals_over") or (policy or {}).get("extra_connects_if_proposals_over")
    if extra and job.proposals_count and job.proposals_count > extra.get("threshold", 10**9) and not job.connects_cost:
        cost += int(extra.get("extra", 0))
    budget_left = int(profile.get("weekly_connects_budget", 80)) - spent_this_week
    p_reply = (hint or {}).get("reply_rate") or 0.12 + 0.25 * fit_score
    expected = p_reply * 0.35 * value * 0.1  # chance of hire x a 10% "worth" of the contract value
    worth = cost <= cfg_policy["max_connects_per_job"] and cost <= budget_left and expected >= cost * USD_PER_CONNECT
    if balance is not None and cost > balance:
        worth = False
        why.append(f"not enough Connects ({balance} < {cost})")
    why.append(f"Connects {cost} (~${cost * USD_PER_CONNECT:.2f}); weekly budget left {budget_left}; "
               f"est. reply rate {p_reply:.0%}{' from your outcome memory' if hint else ''} -> "
               f"{'worth it' if worth else 'not worth it'}")
    return PriceQuote(amount=round(amount, 2 if hourly else 0), rate_type="hourly" if hourly else "fixed",
                      market_p25=p25, market_p50=p50, market_p75=p75, connects_cost=cost, connects_worth_it=worth,
                      rationale="; ".join(why))


@node("pricing_strategist")
async def pricing_strategist(state: dict, runtime: Runtime[RunContext]) -> dict:
    tools = runtime.context.toolbox.for_agent("pricing")
    job = state["job"]
    stats = await tools.call("get_market_stats", category=job.category)
    policy = await tools.call("get_policy")
    try:
        bal = (await tools.call("get_connects_balance")).get("balance")
    except Exception:  # noqa: BLE001
        bal = None
    hint = await outcome_hint(runtime.store, state["user_id"], job.category)
    profile = state.get("profile") or {}
    q = quote(job, state.get("job_spec"), state["fit_report"].score, state.get("client") or {}, stats, profile,
              policy, bal, int(profile.get("connects_spent_this_week", 0)), hint)
    return {"price_quote": q, "profile": profile | {"policy": policy}}
