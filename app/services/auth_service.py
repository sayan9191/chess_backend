"""Authentication service for phone-based dummy login."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse, UserRegisterRequest, UserResponse
from app.utils.exceptions import ConflictError, NotFoundError, UnauthorizedError


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo
        self._settings = get_settings()

    async def register(self, payload: UserRegisterRequest) -> TokenResponse:
        existing = await self._user_repo.get_by_phone(payload.phone)
        if existing:
            raise ConflictError(
                f"User with phone {payload.phone} already exists",
                code="PHONE_ALREADY_REGISTERED",
            )

        user = await self._user_repo.create(phone=payload.phone, name=payload.name)
        return self._build_token_response(user)

    async def login(self, phone: str) -> TokenResponse:
        user = await self._user_repo.get_by_phone(phone)
        if not user:
            raise NotFoundError(
                "No account found with this phone number",
                code="USER_NOT_FOUND",
            )
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated", code="ACCOUNT_INACTIVE")

        return self._build_token_response(user)

    def _build_token_response(self, user) -> TokenResponse:
        token = create_access_token(
            subject=user.id,
            extra_claims={"phone": user.phone, "name": user.name},
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=self._settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )
