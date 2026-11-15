import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api import service
from apps.api.routers import (
    analytics,
    approvals,
    auth,
    jobs,
    messages,
    oauth,
    portfolio,
    profile,
    proposals,
    runs,
)
from apps.api.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await service.startup()
    ticker = None
    if os.environ.get("GIGSIM_MOUNT") == "1":  # single-container mode: keep the mounted simulator moving
        import asyncio

        from apps.api.sim_ticker import run as run_ticker

        ticker = asyncio.create_task(run_ticker())
    yield
    if ticker:
        ticker.cancel()
    await service.shutdown()


app = FastAPI(title="GigBid API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """One trace id per request, propagated to the graph, MCP servers and the audit log."""
    trace_id = request.headers.get("x-trace-id") or service.new_trace_id()
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["x-trace-id"] = trace_id
    return response


@app.exception_handler(service.MarketplaceUnavailable)
async def marketplace_down(_: Request, exc: service.MarketplaceUnavailable):
    return JSONResponse(
        status_code=503,
        content={"error": "marketplace_unavailable", "detail": str(exc), "queued": exc.queued},
    )


for r in (auth, profile, portfolio, jobs, proposals, approvals, messages, runs, analytics, oauth):
    app.include_router(r.router)


if os.environ.get("GIGSIM_MOUNT") == "1":
    # Single-container deployments (512 MB): GigSim runs inside the API process at /gigsim.
    from gigsim.app import create_app as _gigsim_app

    app.mount("/gigsim", _gigsim_app())
