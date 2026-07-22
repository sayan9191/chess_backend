"""User profile service."""

from __future__ import annotations

from uuid import UUID

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse
from app.utils.exceptions import NotFoundError


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def get_profile(self, user_id: UUID) -> UserResponse:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")
        return UserResponse.model_validate(user)
