"""LangGraph long-term store + checkpointer factories (Postgres in deployment, in-memory in tests)."""

from __future__ import annotations

import inspect
import os
from contextlib import AsyncExitStack

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.store.base import BaseStore
from pydantic import BaseModel


def serde() -> JsonPlusSerializer:
    """Only our own hand-off types may be deserialised from checkpoints."""
    from agent import handoffs

    allowed = [("agent.handoffs", name) for name, obj in vars(handoffs).items()
               if inspect.isclass(obj) and obj.__module__ == "agent.handoffs"
               and (issubclass(obj, BaseModel) or hasattr(obj, "__members__"))]
    return JsonPlusSerializer(allowed_msgpack_modules=allowed)


async def open_persistence(stack: AsyncExitStack, durable: bool | None = None) -> tuple[BaseCheckpointSaver, BaseStore]:
    durable = bool(os.environ.get("DATABASE_URL")) if durable is None else durable
    if durable:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.store.postgres.aio import AsyncPostgresStore

        url = os.environ["DATABASE_URL"]
        saver = await stack.enter_async_context(AsyncPostgresSaver.from_conn_string(url, serde=serde()))
        store = await stack.enter_async_context(AsyncPostgresStore.from_conn_string(url))
        await saver.setup()
        await store.setup()
        return saver, store
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore

    return InMemorySaver(serde=serde()), InMemoryStore()
