"""Game REST endpoints and WebSocket handler."""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.dependencies.deps import get_current_user_id, get_game_service
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.schemas.game import GameCreateRequest, GameResponse, GameStatePayload, MoveRequest
from app.services.game_service import GameService
from app.services.websocket_service import WebSocketGameHandler

router = APIRouter(prefix="/games", tags=["Games"])


@router.post(
    "",
    response_model=APIResponse[GameResponse],
    summary="Create a new chess game",
)
async def create_game(
    payload: GameCreateRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    game_service: Annotated[GameService, Depends(get_game_service)],
) -> APIResponse[GameResponse]:
    game = await game_service.create_game(user_id, payload)
    return APIResponse(
        success=True,
        message="Game created successfully",
        data=game,
    )


@router.get(
    "",
    response_model=PaginatedResponse[GameResponse],
    summary="List user's games",
)
async def list_games(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    game_service: Annotated[GameService, Depends(get_game_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[GameResponse]:
    games, total = await game_service.list_games(user_id, page=page, page_size=page_size)
    total_pages = math.ceil(total / page_size) if total else 0
    return PaginatedResponse(
        success=True,
        message="Games retrieved successfully",
        data=games,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{game_id}",
    response_model=APIResponse[GameResponse],
    summary="Get game details",
)
async def get_game(
    game_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    game_service: Annotated[GameService, Depends(get_game_service)],
) -> APIResponse[GameResponse]:
    game = await game_service.get_game(game_id, user_id)
    return APIResponse(
        success=True,
        message="Game retrieved successfully",
        data=game,
    )


@router.get(
    "/{game_id}/state",
    response_model=APIResponse[GameStatePayload],
    summary="Get current game board state",
)
async def get_game_state(
    game_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    game_service: Annotated[GameService, Depends(get_game_service)],
) -> APIResponse[GameStatePayload]:
    state = await game_service.get_game_state(game_id, user_id)
    return APIResponse(
        success=True,
        message="Game state retrieved successfully",
        data=state,
    )


@router.post(
    "/{game_id}/move",
    response_model=APIResponse[GameResponse],
    summary="Make a move (REST fallback)",
)
async def make_move(
    game_id: UUID,
    payload: MoveRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    game_service: Annotated[GameService, Depends(get_game_service)],
) -> APIResponse[GameResponse]:
    game, _, _ = await game_service.apply_human_move_and_engine_reply(
        game_id, user_id, payload.uci, payload.promotion
    )
    return APIResponse(
        success=True,
        message="Move applied successfully",
        data=game,
    )


@router.post(
    "/{game_id}/resign",
    response_model=APIResponse[GameResponse],
    summary="Resign the game",
)
async def resign_game(
    game_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    game_service: Annotated[GameService, Depends(get_game_service)],
) -> APIResponse[GameResponse]:
    game = await game_service.resign_game(game_id, user_id)
    return APIResponse(
        success=True,
        message="Game resigned",
        data=game,
    )


@router.websocket("/{game_id}/ws")
async def game_websocket(websocket: WebSocket, game_id: UUID, token: str = Query(...)) -> None:
    """
    WebSocket endpoint for real-time chess gameplay.

    Connect: ws://host/games/{game_id}/ws?token=<JWT>

    Client messages:
      {"type": "move", "payload": {"uci": "e2e4"}, "request_id": "uuid"}
      {"type": "resign", "payload": {}}
      {"type": "ping", "payload": {}}

    Server messages:
      {"type": "connected", "payload": {...}}
      {"type": "move_ack", "payload": {...}}
      {"type": "engine_move", "payload": {...}}
      {"type": "game_over", "payload": {...}}
      {"type": "error", "payload": {"code": "...", "message": "..."}}
    """
    async with AsyncSessionLocal() as session:
        handler = WebSocketGameHandler(websocket, game_id, session)
        await handler.run(token)
        await session.commit()
