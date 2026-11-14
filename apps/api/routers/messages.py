from fastapi import APIRouter, Depends

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import ConversationOut, ConversationSummary, RunStarted, UserOut

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("", response_model=list[ConversationSummary])
async def conversations(user: UserOut = Depends(current_user)) -> list[ConversationSummary]:
    return await service.conversations(user)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def conversation(
    conversation_id: str, user: UserOut = Depends(current_user)
) -> ConversationOut:
    return await service.conversation(user, conversation_id)


@router.post("/{conversation_id}/draft", response_model=RunStarted)
async def draft_reply(conversation_id: str, user: UserOut = Depends(current_user)) -> RunStarted:
    return await service.draft_reply(user, conversation_id)
