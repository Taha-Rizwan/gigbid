from fastapi import APIRouter, Depends

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import ProfileIn, ProfileOut, SavedSearch, UserOut

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: UserOut = Depends(current_user)) -> ProfileOut:
    return await service.get_profile(user)


@router.put("/profile", response_model=ProfileOut)
async def put_profile(body: ProfileIn, user: UserOut = Depends(current_user)) -> ProfileOut:
    return await service.put_profile(user, body)


@router.get("/searches", response_model=list[SavedSearch])
async def list_searches(user: UserOut = Depends(current_user)) -> list[SavedSearch]:
    return await service.list_searches(user)


@router.post("/searches", response_model=SavedSearch)
async def create_search(body: SavedSearch, user: UserOut = Depends(current_user)) -> SavedSearch:
    return await service.create_search(user, body)


@router.delete("/searches/{search_id}", status_code=204)
async def delete_search(search_id: str, user: UserOut = Depends(current_user)) -> None:
    await service.delete_search(user, search_id)
