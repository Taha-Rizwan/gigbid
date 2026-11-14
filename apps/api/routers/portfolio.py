from fastapi import APIRouter, Depends, File, UploadFile

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import PortfolioItemOut, UploadResult, UserOut

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/items", response_model=list[PortfolioItemOut])
async def list_items(user: UserOut = Depends(current_user)) -> list[PortfolioItemOut]:
    return await service.list_portfolio(user)


@router.post("/upload", response_model=UploadResult)
async def upload(
    files: list[UploadFile] = File(...), user: UserOut = Depends(current_user)
) -> UploadResult:
    return await service.upload_portfolio(user, files)
