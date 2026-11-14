from fastapi import Cookie, HTTPException, status

from apps.api import service
from apps.api.schemas import UserOut


async def current_user(gigbid_session: str | None = Cookie(default=None)) -> UserOut:
    user = await service.user_from_session(gigbid_session) if gigbid_session else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    return user
