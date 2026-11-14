from fastapi import APIRouter, Depends, Request

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import RunOut, UserOut

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
async def list_runs(limit: int = 30, user: UserOut = Depends(current_user)) -> list[RunOut]:
    return await service.list_runs(user, limit)


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: str, user: UserOut = Depends(current_user)) -> RunOut:
    return await service.get_run(user, run_id)


@router.get("/{run_id}/stream")
async def stream_run(run_id: str, request: Request, user: UserOut = Depends(current_user)):
    """Server-Sent Events. Each `data:` line is one RunEvent JSON; resumes from Last-Event-ID."""
    return await service.stream_run(user, run_id, request)
