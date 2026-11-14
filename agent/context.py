"""Per-run runtime context handed to every node (not persisted in checkpoints)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from agent.llm import Usage
from agent.mcp_client import ToolBox


@dataclass
class RunContext:
    toolbox: ToolBox
    usage: Usage = field(default_factory=Usage)
    trace_id: str | None = None
    emit: Callable[[str, str, str, dict | None], Awaitable[None]] | None = None  # (node, kind, summary, data)
    datamark: bool = False          # guardrail experiment switch
    prompt_guard: bool = True

    async def event(self, node: str, kind: str, summary: str = "", data: dict[str, Any] | None = None) -> None:
        if self.emit:
            await self.emit(node, kind, summary, data)
