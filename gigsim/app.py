"""GigSim FastAPI app: `uvicorn gigsim.app:app --port 8081`.

`create_app(config)` builds an isolated app (tests pass their own `Config`). The module-level `app`
reads its configuration from the environment; the database is opened and seeded lazily on startup
or on the first request.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from gigsim import clock
from gigsim.config import Config
from gigsim.service import ApiError, Result, Simulator

log = logging.getLogger("gigsim")


# --- request models -----------------------------------------------------------------------------


class DraftIn(BaseModel):
    job_id: str = Field(min_length=1)
    cover_letter: str = Field(min_length=1, max_length=20000)
    screening_answers: list[str] = Field(default_factory=list)
    bid_amount: float = Field(gt=0)
    rate_type: Literal["hourly", "fixed"]


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class ResetIn(BaseModel):
    seed: int | None = None


class AdvanceIn(BaseModel):
    minutes: int = Field(ge=0, le=60 * 24 * 365)


class PolicyIn(BaseModel):
    version: str


class ScoreIn(DraftIn):
    account_id: str = Field(min_length=1)


# --- helpers ------------------------------------------------------------------------------------


def _respond(result: Result) -> JSONResponse:
    headers = {"Idempotent-Replay": "true"} if result.replayed else None
    return JSONResponse(result.body, status_code=result.status, headers=headers)


def _error_code(status: int) -> str:
    return {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
            405: "method_not_allowed", 409: "conflict", 422: "validation_error",
            429: "rate_limited"}.get(status, f"http_{status}")


def _validation_detail(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    return "; ".join(parts) or "invalid request"


# --- factory ------------------------------------------------------------------------------------


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()
    sim = Simulator(config)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await asyncio.to_thread(sim.ensure_ready)
        task = None
        if config.clock_speed > 0:
            task = asyncio.create_task(clock.run_ticker(sim.advance_clock, config.clock_speed))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="GigSim", version="1.0", description="Marketplace simulator", lifespan=lifespan)
    app.state.sim = sim

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status, headers=exc.headers or None)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse({"error": _error_code(exc.status_code), "detail": str(exc.detail)},
                            status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "validation_error", "detail": _validation_detail(exc)}, status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse({"error": "internal_error", "detail": type(exc).__name__}, status_code=500)

    # --- guards -----------------------------------------------------------------------------

    def v1_account(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        account = sim.authenticate(authorization)
        sim.limiter.check(account["account_id"])
        sim.chaos()
        return account

    def admin_guard(x_admin_token: str | None = Header(default=None)) -> None:
        sim.check_admin(x_admin_token)

    # --- /v1 --------------------------------------------------------------------------------

    v1 = APIRouter(prefix="/v1")

    @v1.get("/jobs")
    def search_jobs(
        account: dict = Depends(v1_account),
        q: str | None = None,
        category: str | None = None,
        skills: str | None = None,
        posted_after: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return sim.search_jobs(q=q, category=category, skills=skills, posted_after=posted_after,
                               limit=limit, offset=offset)

    @v1.get("/jobs/{job_id}")
    def get_job(job_id: str, account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.get_job(job_id)

    @v1.get("/clients/{client_id}")
    def get_client(client_id: str, account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.get_client(client_id)

    @v1.get("/connects")
    def get_connects(account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.get_connects(account)

    @v1.get("/market/stats")
    def market_stats(category: str | None = None, account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.market_stats(category)

    @v1.get("/policy")
    def get_policy(account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.get_policy()

    @v1.post("/proposals/drafts")
    def create_draft(
        body: DraftIn,
        account: dict = Depends(v1_account),
        idempotency_key: str | None = Header(default=None),
    ) -> JSONResponse:
        return _respond(sim.create_draft(account, idempotency_key, body.model_dump()))

    @v1.post("/proposals/drafts/{draft_id}/submit")
    def submit_draft(
        draft_id: str,
        dry_run: bool = False,
        account: dict = Depends(v1_account),
        idempotency_key: str | None = Header(default=None),
    ) -> JSONResponse:
        return _respond(sim.submit_draft(account, draft_id, idempotency_key, dry_run))

    @v1.get("/proposals")
    def list_proposals(status: str | None = None, account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.list_proposals(account, status)

    @v1.get("/threads")
    def list_threads(account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.list_threads(account)

    @v1.get("/threads/{thread_id}/messages")
    def get_messages(thread_id: str, account: dict = Depends(v1_account)) -> dict[str, Any]:
        return sim.get_messages(account, thread_id)

    @v1.post("/threads/{thread_id}/messages")
    def post_message(
        thread_id: str,
        body: MessageIn,
        account: dict = Depends(v1_account),
        idempotency_key: str | None = Header(default=None),
    ) -> JSONResponse:
        return _respond(sim.post_message(account, thread_id, idempotency_key, body.text))

    @v1.get("/events")
    def list_events(
        after: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        account: dict = Depends(v1_account),
    ) -> dict[str, Any]:
        return sim.list_events(account, after, limit)

    # --- /admin -----------------------------------------------------------------------------

    admin = APIRouter(prefix="/admin", dependencies=[Depends(admin_guard)])

    @admin.post("/reset")
    def reset(body: ResetIn | None = None) -> dict[str, Any]:
        return sim.reset(body.seed if body else None)

    @admin.post("/clock/advance")
    def advance(body: AdvanceIn) -> dict[str, Any]:
        return sim.advance_clock(body.minutes)

    @admin.post("/policy")
    def set_policy(body: PolicyIn) -> dict[str, Any]:
        return sim.set_policy(body.version)

    @admin.get("/jobs/{job_id}/truth")
    def job_truth(job_id: str) -> dict[str, Any]:
        return sim.job_truth(job_id)

    @admin.post("/score")
    def score(body: ScoreIn) -> dict[str, Any]:
        return sim.admin_score(body.model_dump())

    @admin.get("/proposals/{proposal_id}/outcome")
    def proposal_outcome(proposal_id: str) -> dict[str, Any]:
        return sim.proposal_outcome(proposal_id)

    @app.get("/health")
    def health() -> dict[str, Any]:
        sim.ensure_ready()
        return {"ok": True, "llm": "groq" if sim.llm.enabled else "heuristic"}

    app.include_router(v1)
    app.include_router(admin)
    return app


app = create_app()
