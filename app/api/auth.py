"""Authentication endpoints: register and login with phone."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.deps import get_auth_service
from app.schemas.common import APIResponse
from app.schemas.user import TokenResponse, UserLoginRequest, UserRegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=APIResponse[TokenResponse],
    summary="Register a new user with phone and name",
)
async def register(
    payload: UserRegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIResponse[TokenResponse]:
    token_data = await auth_service.register(payload)
    return APIResponse(
        success=True,
        message="User registered successfully",
        data=token_data,
    )


@router.post(
    "/login",
    response_model=APIResponse[TokenResponse],
    summary="Login with phone number",
)
async def login(
    payload: UserLoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> APIResponse[TokenResponse]:
    token_data = await auth_service.login(payload.phone)
    return APIResponse(
        success=True,
        message="Login successful",
        data=token_data,
    )
