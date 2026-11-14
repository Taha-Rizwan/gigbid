"""Shared infrastructure: database, security, MCP HTTP plumbing."""

import asyncio
import sys

if sys.platform == "win32":  # psycopg async needs the selector loop on Windows (dev only)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def serve(app, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run uvicorn under our event-loop policy (uvicorn would otherwise pick Proactor on Windows)."""
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, loop="none", log_level="info"))
    asyncio.run(server.serve())
