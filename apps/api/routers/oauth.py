from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import UserOut

router = APIRouter(prefix="/api/oauth/upwork", tags=["oauth"])


@router.get("/start")
async def start(user: UserOut = Depends(current_user)) -> RedirectResponse:
    return await service.upwork_oauth_start(user)


@router.get("/callback")
async def callback(code: str, state: str) -> RedirectResponse:
    return await service.upwork_oauth_callback(code, state)


@router.get("/client-metadata.json")
async def client_metadata() -> dict:
    """OAuth client ID metadata document: Upwork fetches this URL as our client_id."""
    return service.client_metadata()


@router.post("/disconnect", status_code=204)
async def disconnect(user: UserOut = Depends(current_user)) -> None:
    await service.upwork_disconnect(user)
