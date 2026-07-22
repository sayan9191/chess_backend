"""WebSocket message schemas for real-time chess gameplay."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.game import GameResult, GameStatus, PlayerSide
from app.schemas.game import GameMoveResponse


class WSMessageType(str, Enum):
    # Client -> Server
    CONNECT = "connect"
    MOVE = "move"
    RESIGN = "resign"
    PING = "ping"

    # Server -> Client
    CONNECTED = "connected"
    MOVE_ACK = "move_ack"
    ENGINE_MOVE = "engine_move"
    GAME_STATE = "game_state"
    GAME_OVER = "game_over"
    ERROR = "error"
    PONG = "pong"


class WSMessage(BaseModel):
    type: WSMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class WSMovePayload(BaseModel):
    uci: str = Field(..., min_length=4, max_length=7)
    promotion: str | None = Field(default=None, pattern="^[qrbn]$")


class WSConnectedPayload(BaseModel):
    game_id: UUID
    user_color: PlayerSide
    fen: str
    status: GameStatus
    is_live_session: bool = True
    replaced_previous_session: bool = False
    time_limit_seconds: int = 600
    user_time_remaining_ms: int = 600_000
    opponent_time_remaining_ms: int = 600_000
    clock_running_for: PlayerSide | None = None
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    message: str = "Connected to game session"


class WSMoveAckPayload(BaseModel):
    move: GameMoveResponse
    fen: str
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    turn: PlayerSide
    user_time_remaining_ms: int | None = None
    opponent_time_remaining_ms: int | None = None
    clock_running_for: PlayerSide | None = None


class WSEngineMovePayload(BaseModel):
    move: GameMoveResponse
    fen: str
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    turn: PlayerSide | None = None
    user_time_remaining_ms: int | None = None
    opponent_time_remaining_ms: int | None = None
    clock_running_for: PlayerSide | None = None


class WSGameOverPayload(BaseModel):
    result: GameResult
    reason: str
    fen: str
    pgn: str | None


class WSErrorPayload(BaseModel):
    code: str
    message: str
