"""Chat models for the ReAct / supervisor baselines (langgraph.prebuilt needs a LangChain chat model
with bind_tools). Groq tiers reuse agent.llm.get_model; the Anthropic tiers get a small LangChain
adapter over the official SDK (langchain-anthropic is not a project dependency)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool


class EvalChatAnthropic(BaseChatModel):
    model: str
    max_tokens: int = 4000
    tools: list[dict] | None = None

    @property
    def _llm_type(self) -> str:
        return "eval-anthropic"

    def bind_tools(self, tools, **kwargs: Any):  # noqa: ARG002
        specs = []
        for t in tools:
            fn = convert_to_openai_tool(t)["function"]
            specs.append({"name": fn["name"], "description": fn.get("description", ""),
                          "input_schema": fn.get("parameters") or {"type": "object", "properties": {}}})
        return self.model_copy(update={"tools": specs})

    @staticmethod
    def _convert(messages: list[BaseMessage]) -> tuple[str, list[dict]]:
        system = "\n\n".join(m.content for m in messages if isinstance(m, SystemMessage))
        out: list[dict] = []

        def push(role: str, block: dict) -> None:
            if out and out[-1]["role"] == role:
                out[-1]["content"].append(block)
            else:
                out.append({"role": role, "content": [block]})

        for m in messages:
            if isinstance(m, SystemMessage):
                continue
            if isinstance(m, HumanMessage):
                push("user", {"type": "text", "text": m.content if isinstance(m.content, str) else json.dumps(m.content)})
            elif isinstance(m, AIMessage):
                text = m.content if isinstance(m.content, str) else "".join(
                    b.get("text", "") for b in m.content if isinstance(b, dict))
                if text:
                    push("assistant", {"type": "text", "text": text})
                for tc in m.tool_calls or []:
                    push("assistant", {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["args"]})
                if not text and not m.tool_calls:
                    push("assistant", {"type": "text", "text": "(no output)"})
            elif isinstance(m, ToolMessage):
                content = m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)
                push("user", {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": content[:12000]})
        return system, out

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        raise NotImplementedError("async only")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ARG002
        from anthropic import AsyncAnthropic

        system, turns = self._convert(messages)
        kw: dict[str, Any] = {"model": self.model, "max_tokens": self.max_tokens, "messages": turns}
        if system:
            kw["system"] = system
        if self.tools:
            kw["tools"] = self.tools
        resp = await AsyncAnthropic(max_retries=4, timeout=120).messages.create(**kw)
        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [{"id": b.id, "name": b.name, "args": b.input, "type": "tool_call"}
                 for b in resp.content if b.type == "tool_use"]
        msg = AIMessage(content=text, tool_calls=calls, usage_metadata={
            "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
            "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens}, response_metadata={"model": self.model})
        return ChatResult(generations=[ChatGeneration(message=msg)])


def chat_model(tier: str, profile: str) -> tuple[BaseChatModel, str]:
    from agent.llm import get_model
    from agent.settings import model_spec

    spec = model_spec(tier, profile)
    if spec["provider"] == "anthropic":
        return EvalChatAnthropic(model=spec["model"], max_tokens=min(int(spec.get("max_tokens", 4000)), 4000)), spec["model"]
    return get_model(tier, profile)


def messages_usage(messages: list[BaseMessage], model: str) -> dict:
    from agent.settings import config

    inp = sum((getattr(m, "usage_metadata", None) or {}).get("input_tokens", 0) for m in messages if isinstance(m, AIMessage))
    out = sum((getattr(m, "usage_metadata", None) or {}).get("output_tokens", 0) for m in messages if isinstance(m, AIMessage))
    pin, pout = config()["models"]["prices"].get(model, [0.0, 0.0])
    return {"calls": sum(1 for m in messages if isinstance(m, AIMessage)), "input_tokens": inp, "output_tokens": out,
            "tokens": inp + out, "cost_usd": inp / 1e6 * pin + out / 1e6 * pout}
