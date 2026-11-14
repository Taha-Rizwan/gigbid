from fastapi import APIRouter, Depends

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import PipelineOut, RegenerateIn, RunStarted, StudioOut, UserOut

router = APIRouter(prefix="/api", tags=["proposals"])


@router.get("/proposals/{thread_id}", response_model=StudioOut)
async def studio(thread_id: str, user: UserOut = Depends(current_user)) -> StudioOut:
    return await service.studio(user, thread_id)


@router.post("/proposals/{thread_id}/regenerate", response_model=RunStarted)
async def regenerate(
    thread_id: str, body: RegenerateIn, user: UserOut = Depends(current_user)
) -> RunStarted:
    return await service.regenerate_paragraph(user, thread_id, body)


@router.get("/pipeline", response_model=PipelineOut)
async def pipeline(user: UserOut = Depends(current_user)) -> PipelineOut:
    return await service.pipeline(user)
