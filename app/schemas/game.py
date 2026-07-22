"""Game-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.models.game import GameResult, GameStatus, OpponentType, PlayerSide


class GameCreateRequest(BaseModel):
    opponent_type: OpponentType = OpponentType.MACHINE
    user_color: PlayerSide = PlayerSide.WHITE
    time_limit_seconds: int = Field(
        default_factory=lambda: get_settings().default_time_limit_seconds,
        ge=60,
        le=7200,
    )


class GameMoveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    move_number: int
    move_san: str
    move_uci: str
    fen_after: str
    played_by: PlayerSide
    created_at: datetime


class GameClockPayload(BaseModel):
    time_limit_seconds: int
    user_time_remaining_ms: int
    opponent_time_remaining_ms: int
    clock_running_for: PlayerSide | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_activity_at: datetime | None = None
    is_session_active: bool = False


class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    opponent_type: OpponentType
    status: GameStatus
    result: GameResult
    user_color: PlayerSide
    current_fen: str
    pgn: str | None
    move_count: int
    time_limit_seconds: int
    user_time_remaining_ms: int
    opponent_time_remaining_ms: int
    clock_running_for: PlayerSide | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_activity_at: datetime | None = None
    is_session_active: bool = False
    created_at: datetime
    updated_at: datetime
    moves: list[GameMoveResponse] = Field(default_factory=list)


class MoveRequest(BaseModel):
    uci: str = Field(..., min_length=4, max_length=7, examples=["e2e4"])
    promotion: str | None = Field(default=None, pattern="^[qrbn]$")


class GameStatePayload(BaseModel):
    game_id: UUID
    fen: str
    status: GameStatus
    result: GameResult
    move_count: int
    turn: PlayerSide
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    legal_moves: list[str]
    is_session_active: bool = False
    time_limit_seconds: int
    user_time_remaining_ms: int
    opponent_time_remaining_ms: int
    clock_running_for: PlayerSide | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_activity_at: datetime | None = None
