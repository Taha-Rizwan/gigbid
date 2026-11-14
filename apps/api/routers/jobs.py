from typing import Literal

from fastapi import APIRouter, Depends, Query

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import InboxOut, JobDetail, RunStarted, SkipIn, UserOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=InboxOut)
async def inbox(
    status: str | None = None,
    recommendation: Literal["bid", "watch", "skip"] | None = None,
    q: str | None = None,
    sort: Literal["fit", "newest", "price"] = "fit",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserOut = Depends(current_user),
) -> InboxOut:
    return await service.inbox(user, status, recommendation, q, sort, limit, offset)


@router.post("/scout", response_model=RunStarted)
async def scout_now(user: UserOut = Depends(current_user)) -> RunStarted:
    return await service.scout_now(user)


@router.get("/{job_id}", response_model=JobDetail)
async def job_detail(job_id: str, user: UserOut = Depends(current_user)) -> JobDetail:
    return await service.job_detail(user, job_id)


@router.post("/{job_id}/analyze", response_model=RunStarted)
async def analyze(job_id: str, user: UserOut = Depends(current_user)) -> RunStarted:
    return await service.analyze(user, job_id)


@router.post("/{job_id}/skip", status_code=204)
async def skip(job_id: str, body: SkipIn, user: UserOut = Depends(current_user)) -> None:
    await service.skip(user, job_id, body.reason)
