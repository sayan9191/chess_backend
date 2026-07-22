"""Game and move data access repository."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game import Game, GameMove, GameResult, GameStatus, OpponentType, PlayerSide


class GameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, game_id: UUID) -> Game | None:
        result = await self._session.execute(
            select(Game)
            .options(selectinload(Game.moves))
            .where(Game.id == game_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Game]:
        result = await self._session.execute(
            select(Game)
            .options(selectinload(Game.moves))
            .where(Game.user_id == user_id)
            .order_by(Game.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count()).select_from(Game).where(Game.user_id == user_id)
        )
        return result.scalar_one()

    async def create(
        self,
        user_id: UUID,
        *,
        opponent_type: OpponentType = OpponentType.MACHINE,
        user_color: PlayerSide = PlayerSide.WHITE,
        time_limit_seconds: int = 600,
    ) -> Game:
        initial_ms = time_limit_seconds * 1000
        game = Game(
            user_id=user_id,
            opponent_type=opponent_type,
            user_color=user_color,
            status=GameStatus.WAITING,
            time_limit_seconds=time_limit_seconds,
            user_time_remaining_ms=initial_ms,
            opponent_time_remaining_ms=initial_ms,
        )
        self._session.add(game)
        await self._session.flush()
        await self._session.refresh(game)
        return game

    async def add_move(
        self,
        game: Game,
        *,
        move_number: int,
        move_san: str,
        move_uci: str,
        fen_after: str,
        played_by: PlayerSide,
    ) -> GameMove:
        move = GameMove(
            game_id=game.id,
            move_number=move_number,
            move_san=move_san,
            move_uci=move_uci,
            fen_after=fen_after,
            played_by=played_by,
        )
        self._session.add(move)
        game.move_count = move_number
        game.current_fen = fen_after
        await self._session.flush()
        await self._session.refresh(move)
        return move

    async def update_game_state(
        self,
        game: Game,
        *,
        status: GameStatus | None = None,
        result: GameResult | None = None,
        pgn: str | None = None,
        current_fen: str | None = None,
        ended_at: datetime | None = None,
        clock_started_at: datetime | None = None,
        last_activity_at: datetime | None = None,
        user_time_remaining_ms: int | None = None,
        opponent_time_remaining_ms: int | None = None,
        clear_clock_started_at: bool = False,
    ) -> Game:
        if status is not None:
            game.status = status
        if result is not None:
            game.result = result
        if pgn is not None:
            game.pgn = pgn
        if current_fen is not None:
            game.current_fen = current_fen
        if ended_at is not None:
            game.ended_at = ended_at
        if last_activity_at is not None:
            game.last_activity_at = last_activity_at
        if user_time_remaining_ms is not None:
            game.user_time_remaining_ms = user_time_remaining_ms
        if opponent_time_remaining_ms is not None:
            game.opponent_time_remaining_ms = opponent_time_remaining_ms
        if clear_clock_started_at:
            game.clock_started_at = None
        elif clock_started_at is not None:
            game.clock_started_at = clock_started_at
        await self._session.flush()
        await self._session.refresh(game)
        return game

    async def flush(self, game: Game | None = None) -> None:
        await self._session.flush()
        if game is not None:
            await self._session.refresh(game)
