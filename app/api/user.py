"""User profile endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.deps import get_current_user_id, get_user_service
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=APIResponse[UserResponse],
    summary="Get current user profile",
)
async def get_me(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> APIResponse[UserResponse]:
    profile = await user_service.get_profile(user_id)
    return APIResponse(
        success=True,
        message="Profile retrieved successfully",
        data=profile,
    )
