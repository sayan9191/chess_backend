"""Game session lifecycle and chess clock management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import chess

from app.core.config import get_settings
from app.models.game import Game, GameResult, GameStatus, PlayerSide
from app.repositories.game_repository import GameRepository
from app.services.websocket_session_manager import session_manager
from app.utils.chess_utils import board_to_side, create_board


class GameSessionService:
    def __init__(self, game_repo: GameRepository) -> None:
        self._game_repo = game_repo
        self._settings = get_settings()

    async def resolve_game(self, game: Game) -> Game:
        """Apply idle expiry and clock timeouts, persisting any status change."""
        changed = False

        if game.status == GameStatus.IN_PROGRESS:
            changed |= await self._apply_clock_timeout(game)

        if game.status == GameStatus.IN_PROGRESS:
            changed |= await self._apply_idle_abandonment(game)

        if changed:
            await self._game_repo.flush(game)
            refreshed = await self._game_repo.get_by_id(game.id)
            return refreshed or game
        return game

    async def activate_game(self, game: Game) -> Game:
        """Start or resume a game session when the player connects."""
        now = datetime.now(timezone.utc)
        game.last_activity_at = now

        if game.status == GameStatus.WAITING:
            game.status = GameStatus.IN_PROGRESS
            game.started_at = now

        if game.status == GameStatus.IN_PROGRESS and game.clock_started_at is None:
            board = create_board(game.current_fen)
            self._start_clock_for_turn(game, board)

        await self._game_repo.flush(game)
        refreshed = await self._game_repo.get_by_id(game.id)
        return refreshed or game

    async def touch_activity(self, game: Game) -> None:
        game.last_activity_at = datetime.now(timezone.utc)
        await self._game_repo.flush(game)

    async def before_move(self, game: Game, board: chess.Board) -> GameResult | None:
        """Tick the clock before a move. Returns a result if someone lost on time."""
        if game.status != GameStatus.IN_PROGRESS:
            return None

        self._tick_clock(game, board)
        return self._time_forfeit_result(game, board)

    async def after_move(self, game: Game, board: chess.Board) -> None:
        """Switch the running clock to the side now on move."""
        if game.status != GameStatus.IN_PROGRESS:
            game.clock_started_at = None
            return

        self._start_clock_for_turn(game, board)
        game.last_activity_at = datetime.now(timezone.utc)
        await self._game_repo.flush(game)

    async def finalize_game(
        self,
        game: Game,
        *,
        status: GameStatus,
        result: GameResult,
        pgn: str | None = None,
        current_fen: str | None = None,
    ) -> Game:
        now = datetime.now(timezone.utc)
        if game.status == GameStatus.IN_PROGRESS:
            board = create_board(game.current_fen)
            self._tick_clock(game, board)

        return await self._game_repo.update_game_state(
            game,
            status=status,
            result=result,
            pgn=pgn,
            current_fen=current_fen,
            ended_at=now,
            clock_started_at=None,
            last_activity_at=now,
        )

    def get_clock_snapshot(self, game: Game, board: chess.Board) -> dict:
        """Return authoritative remaining times including elapsed time on the active clock."""
        user_ms = game.user_time_remaining_ms
        opponent_ms = game.opponent_time_remaining_ms

        if (
            game.status == GameStatus.IN_PROGRESS
            and game.clock_started_at is not None
        ):
            elapsed_ms = self._elapsed_ms(game.clock_started_at)
            turn = board_to_side(board)
            if turn == game.user_color:
                user_ms = max(0, user_ms - elapsed_ms)
            else:
                opponent_ms = max(0, opponent_ms - elapsed_ms)

        return {
            "time_limit_seconds": game.time_limit_seconds,
            "user_time_remaining_ms": user_ms,
            "opponent_time_remaining_ms": opponent_ms,
            "clock_running_for": board_to_side(board)
            if game.status == GameStatus.IN_PROGRESS and game.clock_started_at
            else None,
            "started_at": game.started_at,
            "ended_at": game.ended_at,
            "last_activity_at": game.last_activity_at,
            "is_session_active": session_manager.is_active(game.id),
        }

    async def _apply_clock_timeout(self, game: Game) -> bool:
        board = create_board(game.current_fen)
        self._tick_clock(game, board)
        result = self._time_forfeit_result(game, board)
        if not result:
            return False

        await self._game_repo.update_game_state(
            game,
            status=GameStatus.COMPLETED,
            result=result,
            ended_at=datetime.now(timezone.utc),
            clock_started_at=None,
            last_activity_at=datetime.now(timezone.utc),
        )
        return True

    async def _apply_idle_abandonment(self, game: Game) -> bool:
        if session_manager.is_active(game.id):
            return False

        reference = game.last_activity_at or game.started_at or game.created_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)

        idle_limit = timedelta(minutes=self._settings.game_idle_timeout_minutes)
        if datetime.now(timezone.utc) - reference < idle_limit:
            return False

        await self._game_repo.update_game_state(
            game,
            status=GameStatus.ABANDONED,
            ended_at=datetime.now(timezone.utc),
            clock_started_at=None,
            last_activity_at=datetime.now(timezone.utc),
        )
        return True

    def _tick_clock(self, game: Game, board: chess.Board) -> None:
        if game.status != GameStatus.IN_PROGRESS or game.clock_started_at is None:
            return

        elapsed_ms = self._elapsed_ms(game.clock_started_at)
        if elapsed_ms <= 0:
            return

        turn = board_to_side(board)
        if turn == game.user_color:
            game.user_time_remaining_ms = max(0, game.user_time_remaining_ms - elapsed_ms)
        else:
            game.opponent_time_remaining_ms = max(
                0, game.opponent_time_remaining_ms - elapsed_ms
            )
        game.clock_started_at = datetime.now(timezone.utc)

    def _start_clock_for_turn(self, game: Game, board: chess.Board) -> None:
        game.clock_started_at = datetime.now(timezone.utc)

    def _time_forfeit_result(self, game: Game, board: chess.Board) -> GameResult | None:
        turn = board_to_side(board)
        if turn == game.user_color and game.user_time_remaining_ms <= 0:
            return (
                GameResult.BLACK_WINS
                if game.user_color == PlayerSide.WHITE
                else GameResult.WHITE_WINS
            )
        if turn != game.user_color and game.opponent_time_remaining_ms <= 0:
            return (
                GameResult.WHITE_WINS
                if game.user_color == PlayerSide.WHITE
                else GameResult.BLACK_WINS
            )
        return None

    @staticmethod
    def _elapsed_ms(since: datetime) -> int:
        now = datetime.now(timezone.utc)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        return max(0, int((now - since).total_seconds() * 1000))
