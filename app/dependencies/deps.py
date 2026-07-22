"""FastAPI dependency injection providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import JWTError, decode_access_token
from app.repositories.game_repository import GameRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.chess_engine_service import ChessEngineService
from app.services.game_service import GameService
from app.services.user_service import UserService
from app.utils.exceptions import UnauthorizedError


async def get_session(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    yield session


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    return UserRepository(session)


def get_game_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GameRepository:
    return GameRepository(session)


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repo)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(user_repo)


def get_engine_service() -> ChessEngineService:
    return ChessEngineService()


def get_game_service(
    game_repo: Annotated[GameRepository, Depends(get_game_repository)],
    engine: Annotated[ChessEngineService, Depends(get_engine_service)],
) -> GameService:
    return GameService(game_repo, engine)


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
        return UUID(payload["sub"])
    except (JWTError, ValueError, KeyError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
