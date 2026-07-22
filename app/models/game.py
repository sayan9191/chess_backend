"""Game and move ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _enum_column(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        create_constraint=False,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class OpponentType(str, enum.Enum):
    MACHINE = "machine"
    HUMAN = "human"


class GameStatus(str, enum.Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class GameResult(str, enum.Enum):
    WHITE_WINS = "white_wins"
    BLACK_WINS = "black_wins"
    DRAW = "draw"
    ONGOING = "ongoing"


class PlayerSide(str, enum.Enum):
    WHITE = "white"
    BLACK = "black"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opponent_type: Mapped[OpponentType] = mapped_column(
        _enum_column(OpponentType, "opponent_type"),
        nullable=False,
        default=OpponentType.MACHINE,
    )
    status: Mapped[GameStatus] = mapped_column(
        _enum_column(GameStatus, "game_status"),
        nullable=False,
        default=GameStatus.WAITING,
    )
    result: Mapped[GameResult] = mapped_column(
        _enum_column(GameResult, "game_result"),
        nullable=False,
        default=GameResult.ONGOING,
    )
    user_color: Mapped[PlayerSide] = mapped_column(
        _enum_column(PlayerSide, "player_side"),
        nullable=False,
        default=PlayerSide.WHITE,
    )
    current_fen: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )
    pgn: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    move_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    user_time_remaining_ms: Mapped[int] = mapped_column(Integer, default=600_000, nullable=False)
    opponent_time_remaining_ms: Mapped[int] = mapped_column(
        Integer, default=600_000, nullable=False
    )
    clock_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="games", lazy="selectin")
    moves: Mapped[list["GameMove"]] = relationship(
        "GameMove", back_populates="game", lazy="selectin", order_by="GameMove.move_number"
    )


class GameMove(Base):
    __tablename__ = "game_moves"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    move_number: Mapped[int] = mapped_column(Integer, nullable=False)
    move_san: Mapped[str] = mapped_column(String(16), nullable=False)
    move_uci: Mapped[str] = mapped_column(String(8), nullable=False)
    fen_after: Mapped[str] = mapped_column(Text, nullable=False)
    played_by: Mapped[PlayerSide] = mapped_column(
        _enum_column(PlayerSide, "player_side"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    game: Mapped["Game"] = relationship("Game", back_populates="moves", lazy="selectin")
