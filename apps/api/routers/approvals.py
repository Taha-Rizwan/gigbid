from fastapi import APIRouter, Depends

from apps.api import service
from apps.api.auth.deps import current_user
from apps.api.schemas import ApprovalIn, ApprovalResult, UserOut

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.post("/{thread_id}", response_model=ApprovalResult)
async def decide(
    thread_id: str, body: ApprovalIn, user: UserOut = Depends(current_user)
) -> ApprovalResult:
    """Resume an interrupted bid or conversation graph with the human decision."""
    return await service.decide(user, thread_id, body)
