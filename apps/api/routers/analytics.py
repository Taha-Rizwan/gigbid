from fastapi import APIRouter, Depends

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import AnalyticsOut, HealthOut, MemoryOut, UserOut

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(user: UserOut = Depends(current_user)) -> AnalyticsOut:
    return await service.analytics(user)


@router.get("/memory", response_model=MemoryOut)
async def memory(user: UserOut = Depends(current_user)) -> MemoryOut:
    return await service.list_memory(user)


@router.delete("/memory/{namespace}/{key}", status_code=204)
async def delete_memory(namespace: str, key: str, user: UserOut = Depends(current_user)) -> None:
    await service.delete_memory(user, namespace, key)


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return await service.health()
