from fastapi import APIRouter, Depends, Response

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
async def register(body: RegisterIn, response: Response) -> UserOut:
    return await service.register(body, response)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, response: Response) -> UserOut:
    return await service.login(body, response)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    service.logout(response)


@router.get("/me", response_model=UserOut)
async def me(user: UserOut = Depends(current_user)) -> UserOut:
    return user
