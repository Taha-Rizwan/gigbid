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
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        # A pool that checks connections before use: hosted Postgres (Neon) closes idle connections,
        # and a single long-lived connection made every run fail after a quiet period.
        pool = AsyncConnectionPool(
            os.environ["DATABASE_URL"], min_size=1, max_size=6, open=False, max_idle=120,
            check=AsyncConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await pool.open()
        stack.push_async_callback(pool.close)
        saver = AsyncPostgresSaver(pool, serde=serde())
        store = AsyncPostgresStore(pool)
        await saver.setup()
        await store.setup()
        return saver, store
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore

    return InMemorySaver(serde=serde()), InMemoryStore()
