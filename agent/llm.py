"""Model factory, structured calls and per-node token / cost accounting.

Nodes never construct models themselves: they call `structured()` or `text()` with their node
name, and the model comes from agent/config.yaml.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from agent.settings import config, load_prompt, model_spec

log = logging.getLogger("gigbid.llm")
T = TypeVar("T", bound=BaseModel)


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    by_node: dict[str, dict[str, float]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(float)))

    def add(self, node: str, model: str, inp: int, out: int, seconds: float) -> None:
        price_in, price_out = config()["models"]["prices"].get(model, [0.0, 0.0])
        cost = inp / 1e6 * price_in + out / 1e6 * price_out
        self.calls += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.cost_usd += cost
        self.latency_s += seconds
        n = self.by_node[node]
        n["calls"] += 1
        n["tokens"] += inp + out
        n["cost_usd"] += cost

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens": self.tokens,
            "cost_usd": round(self.cost_usd, 6),
            "by_node": {k: dict(v) for k, v in self.by_node.items()},
        }


# One Usage per run; set by whoever starts a graph run (API, worker, eval runner).
current_usage: contextvars.ContextVar[Usage | None] = contextvars.ContextVar("usage", default=None)
# Model profile override per run (UI setting / eval comparisons).
current_profile: contextvars.ContextVar[str | None] = contextvars.ContextVar("profile", default=None)


class BudgetExceeded(RuntimeError):
    pass


_models: dict[tuple, BaseChatModel] = {}


class AnthropicModel:
    """Claude via the official SDK. No sampling params (rejected on current models); effort in output_config."""

    def __init__(self, spec: dict):
        from anthropic import AsyncAnthropic

        self.spec = spec
        self.client = AsyncAnthropic(max_retries=4, timeout=120)

    @staticmethod
    def _split(messages: list[BaseMessage]) -> tuple[str, list[dict]]:
        system = "\n\n".join(m.content for m in messages if isinstance(m, SystemMessage))
        turns = [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                 for m in messages if not isinstance(m, SystemMessage)]
        return system, turns

    def _kwargs(self, messages: list[BaseMessage]) -> dict:
        system, turns = self._split(messages)
        kw = {"model": self.spec["model"], "max_tokens": self.spec.get("max_tokens", 16000), "messages": turns,
              "output_config": {"effort": self.spec.get("effort", "low")}}
        if system:
            kw["system"] = system
        return kw

    async def parse(self, schema, messages: list[BaseMessage]):
        resp = await self.client.messages.parse(output_format=schema, **self._kwargs(messages))
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused: {getattr(resp, 'stop_details', None)}")
        return resp, resp.parsed_output

    async def create(self, messages: list[BaseMessage]):
        resp = await self.client.messages.create(**self._kwargs(messages))
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused: {getattr(resp, 'stop_details', None)}")
        return resp, "".join(b.text for b in resp.content if b.type == "text")


def _usage_obj(resp) -> object:
    class _U:
        usage_metadata = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}

    return _U()


def get_model(node: str, profile: str | None = None) -> tuple[BaseChatModel, str]:
    spec = model_spec(node, profile or current_profile.get())
    key = tuple(sorted(spec.items()))
    if key not in _models:
        provider = spec["provider"]
        common = {"temperature": spec.get("temperature", 0.0), "max_retries": 4, "timeout": 90}
        if spec.get("max_tokens"):
            common["max_tokens"] = spec["max_tokens"]
        if provider == "anthropic":  # paid profile + LLM judge; official Anthropic SDK
            _models[key] = AnthropicModel(spec)
        elif provider == "ollama":  # local open-weight models (docker compose `ollama` service)
            import os

            from langchain_openai import ChatOpenAI

            _models[key] = ChatOpenAI(model=spec["model"], api_key="ollama",
                                      base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), **common)
        elif provider == "cerebras":  # OpenAI-compatible; open-weight models
            import os

            from langchain_openai import ChatOpenAI

            if not os.environ.get("CEREBRAS_API_KEY"):
                raise RuntimeError("CEREBRAS_API_KEY not set")
            extra = {"reasoning_effort": spec["reasoning_effort"]} if spec.get("reasoning_effort") else {}
            _models[key] = ChatOpenAI(model=spec["model"], base_url="https://api.cerebras.ai/v1",
                                      api_key=os.environ["CEREBRAS_API_KEY"], **common, **extra)
        elif provider == "groq":
            from langchain_groq import ChatGroq

            extra = {}
            if spec.get("reasoning_effort"):
                extra["reasoning_effort"] = spec["reasoning_effort"]
            _models[key] = ChatGroq(model=spec["model"], **common, **extra)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI

            _models[key] = ChatOpenAI(model=spec["model"], **common)
        else:
            raise ValueError(f"unknown provider {provider}")
    return _models[key], spec["model"]


def _record(node: str, model: str, msg: Any, seconds: float) -> None:
    usage = current_usage.get()
    if usage is None:
        return
    meta = getattr(msg, "usage_metadata", None) or {}
    usage.add(node, model, meta.get("input_tokens", 0), meta.get("output_tokens", 0), seconds)
    cap = config()["budgets"]["max_tokens_per_job"]
    if usage.tokens > cap:
        raise BudgetExceeded(f"token budget exceeded: {usage.tokens} > {cap}")


def prompt_messages(prompt: str, user: str, **fmt: Any) -> list[BaseMessage]:
    _, system = load_prompt(prompt)
    return [SystemMessage(system.format(**fmt) if fmt else system), HumanMessage(user)]


def prompt_messages_raw(system: str, user: str) -> list[BaseMessage]:
    return [SystemMessage(system), HumanMessage(user)]


async def _invoke_with_fallback(node: str, call) -> Any:
    """Try the node's model; on failure, cheap nodes fall back to fallback_small."""
    model, name = get_model(node)
    try:
        return await call(model, name)
    except BudgetExceeded:
        raise
    except Exception as exc:  # noqa: BLE001
        tier = config()["models"]["nodes"].get(node, node)
        fb_tier = {"small": "fallback_small", "strong": "fallback_strong"}.get(tier)
        profile = config()["models"]["profiles"][current_profile.get() or config()["models"]["profile"]]
        if not fb_tier or fb_tier not in profile:
            raise
        log.warning("node %s model %s failed (%s: %s); trying fallback", node, name, type(exc).__name__, str(exc)[:200])
        try:
            fb, fb_name = get_model(fb_tier)
        except Exception:  # noqa: BLE001 - no fallback configured: surface the original error
            raise exc from None
        return await call(fb, fb_name)


async def structured[T: BaseModel](node: str, schema: type[T], messages: list[BaseMessage]) -> T:
    async def call(model: BaseChatModel, name: str) -> T:
        t0 = time.perf_counter()
        if isinstance(model, AnthropicModel):
            resp, parsed = await model.parse(schema, messages)
            _record(node, name, _usage_obj(resp), time.perf_counter() - t0)
            if parsed is None:
                raise ValueError(f"{node}: could not parse {schema.__name__}")
            return parsed
        try:
            runnable = model.with_structured_output(schema, include_raw=True)
            out = await runnable.ainvoke(messages)
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001  - some models reject tool-call schemas
            if "tool call validation" not in str(exc) and "tool_use_failed" not in str(exc):
                raise
            out = await _json_mode(model, schema, messages)
        _record(node, name, out["raw"], time.perf_counter() - t0)
        if out.get("parsed") is None:
            raise ValueError(f"{node}: could not parse {schema.__name__}: {out.get('parsing_error')}")
        return out["parsed"]

    return await _invoke_with_fallback(node, call)


async def _json_mode[T: BaseModel](model: BaseChatModel, schema: type[T], messages: list[BaseMessage]) -> dict:
    import json

    hint = SystemMessage(
        "Reply with one JSON object only, matching this JSON schema:\n"
        + json.dumps(schema.model_json_schema())
    )
    raw = await model.bind(response_format={"type": "json_object"}).ainvoke([*messages, hint])
    content = raw.content if isinstance(raw.content, str) else str(raw.content)
    try:
        return {"raw": raw, "parsed": schema.model_validate_json(content), "parsing_error": None}
    except Exception as exc:  # noqa: BLE001
        return {"raw": raw, "parsed": None, "parsing_error": exc}


async def text(node: str, messages: list[BaseMessage]) -> str:
    async def call(model: BaseChatModel, name: str) -> str:
        t0 = time.perf_counter()
        if isinstance(model, AnthropicModel):
            resp, out = await model.create(messages)
            _record(node, name, _usage_obj(resp), time.perf_counter() - t0)
            return out
        msg = await model.ainvoke(messages)
        _record(node, name, msg, time.perf_counter() - t0)
        return msg.content if isinstance(msg.content, str) else str(msg.content)

    return await _invoke_with_fallback(node, call)


async def gather_limited(coros, limit: int = 4):
    sem = asyncio.Semaphore(limit)

    async def run(c):
        async with sem:
            return await c

    return await asyncio.gather(*(run(c) for c in coros))
