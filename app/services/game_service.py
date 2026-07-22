"""Game business logic: move validation, engine responses, state management."""

from __future__ import annotations

from uuid import UUID

import chess

from app.core.config import get_settings
from app.models.game import Game, GameResult, GameStatus, OpponentType, PlayerSide
from app.repositories.game_repository import GameRepository
from app.schemas.game import GameCreateRequest, GameResponse, GameStatePayload
from app.services.chess_engine_service import ChessEngineService
from app.services.game_session_service import GameSessionService
from app.utils.chess_utils import (
    apply_move,
    board_to_side,
    create_board,
    determine_result,
    export_pgn,
    get_legal_moves_uci,
    is_legal_move,
)
from app.utils.exceptions import AppException, ForbiddenError, InvalidMoveError, NotFoundError, ValidationError


class GameService:
    def __init__(
        self,
        game_repo: GameRepository,
        engine_service: ChessEngineService,
        session_service: GameSessionService | None = None,
    ) -> None:
        self._game_repo = game_repo
        self._engine = engine_service
        self._sessions = session_service or GameSessionService(game_repo)
        self._settings = get_settings()

    async def create_game(self, user_id: UUID, payload: GameCreateRequest) -> GameResponse:
        game = await self._game_repo.create(
            user_id,
            opponent_type=payload.opponent_type,
            user_color=payload.user_color,
            time_limit_seconds=payload.time_limit_seconds,
        )
        return await self._to_game_response(game)

    async def activate_game(self, game_id: UUID, user_id: UUID) -> GameResponse:
        game = await self._get_owned_game(game_id, user_id)
        game = await self._sessions.resolve_game(game)
        if game.status in {GameStatus.COMPLETED, GameStatus.ABANDONED}:
            return await self._to_game_response(game)

        game = await self._sessions.activate_game(game)
        return await self._to_game_response(game)

    async def get_game(self, game_id: UUID, user_id: UUID) -> GameResponse:
        game = await self._get_owned_game(game_id, user_id)
        game = await self._sessions.resolve_game(game)
        return await self._to_game_response(game)

    async def list_games(
        self, user_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[GameResponse], int]:
        offset = (page - 1) * page_size
        games = await self._game_repo.list_by_user(user_id, limit=page_size, offset=offset)
        resolved = [await self._sessions.resolve_game(game) for game in games]
        total = await self._game_repo.count_by_user(user_id)
        responses: list[GameResponse] = []
        for game in resolved:
            responses.append(await self._to_game_response(game))
        return responses, total

    async def get_game_state(self, game_id: UUID, user_id: UUID) -> GameStatePayload:
        game = await self._get_owned_game(game_id, user_id)
        game = await self._sessions.resolve_game(game)
        board = create_board(game.current_fen)
        return self._build_state_payload(game, board)

    async def apply_human_move_and_engine_reply(
        self,
        game_id: UUID,
        user_id: UUID,
        uci: str,
        promotion: str | None = None,
    ) -> tuple[GameResponse, dict, dict | None]:
        game_resp, human_meta = await self.make_human_move(
            game_id, user_id, uci, promotion
        )
        engine_meta: dict | None = None
        if game_resp.status == GameStatus.IN_PROGRESS:
            game = await self._game_repo.get_by_id(game_id)
            if game and game.opponent_type == OpponentType.MACHINE:
                try:
                    _, engine_meta = await self.make_engine_move(game_id, user_id)
                    game_resp = await self._to_game_response(
                        await self._game_repo.get_by_id(game_id)
                    )
                except (AppException, RuntimeError):
                    pass
        return game_resp, human_meta, engine_meta

    async def make_human_move(
        self,
        game_id: UUID,
        user_id: UUID,
        uci: str,
        promotion: str | None = None,
    ) -> tuple[GameResponse, dict]:
        game = await self._get_owned_game(game_id, user_id)
        game = await self._sessions.resolve_game(game)
        self._ensure_game_active(game)

        board = create_board(game.current_fen)
        self._ensure_correct_turn(game, board)

        timeout_result = await self._sessions.before_move(game, board)
        if timeout_result:
            await self._sessions.finalize_game(
                game, status=GameStatus.COMPLETED, result=timeout_result
            )
            refreshed = await self._game_repo.get_by_id(game.id)
            raise ValidationError("Your time has expired", code="TIME_EXPIRED")

        if not is_legal_move(board, uci, promotion):
            raise InvalidMoveError(f"Illegal move: {uci}")

        move, move_san = apply_move(board, uci, promotion)
        move_number = game.move_count + 1
        played_by = game.user_color

        db_move = await self._game_repo.add_move(
            game,
            move_number=move_number,
            move_san=move_san,
            move_uci=move.uci(),
            fen_after=board.fen(),
            played_by=played_by,
        )

        await self._sessions.after_move(game, board)
        meta = self._board_meta(board, game)
        await self._finalize_if_over(game, board)

        refreshed = await self._game_repo.get_by_id(game.id)
        return await self._to_game_response(refreshed), {**meta, "move": db_move}

    async def make_engine_move(self, game_id: UUID, user_id: UUID) -> tuple[GameResponse, dict]:
        game = await self._get_owned_game(game_id, user_id)
        game = await self._sessions.resolve_game(game)
        self._ensure_game_active(game)

        if game.opponent_type != OpponentType.MACHINE:
            raise ValidationError("Engine moves only apply to machine opponent games")

        board = create_board(game.current_fen)
        engine_side = PlayerSide.BLACK if game.user_color == PlayerSide.WHITE else PlayerSide.WHITE

        if board_to_side(board) != engine_side:
            raise InvalidMoveError("Not engine's turn")

        timeout_result = await self._sessions.before_move(game, board)
        if timeout_result:
            await self._sessions.finalize_game(
                game, status=GameStatus.COMPLETED, result=timeout_result
            )
            refreshed = await self._game_repo.get_by_id(game.id)
            return await self._to_game_response(refreshed), self._board_meta(
                create_board(refreshed.current_fen), refreshed
            )

        uci = await self._engine.get_best_move(board.fen())
        move, move_san = apply_move(board, uci)
        move_number = game.move_count + 1

        db_move = await self._game_repo.add_move(
            game,
            move_number=move_number,
            move_san=move_san,
            move_uci=move.uci(),
            fen_after=board.fen(),
            played_by=engine_side,
        )

        await self._sessions.after_move(game, board)
        meta = self._board_meta(board, game)
        await self._finalize_if_over(game, board)

        refreshed = await self._game_repo.get_by_id(game.id)
        return await self._to_game_response(refreshed), {**meta, "move": db_move}

    async def resign_game(self, game_id: UUID, user_id: UUID) -> GameResponse:
        game = await self._get_owned_game(game_id, user_id)
        game = await self._sessions.resolve_game(game)
        self._ensure_game_active(game)

        result = (
            GameResult.BLACK_WINS
            if game.user_color == PlayerSide.WHITE
            else GameResult.WHITE_WINS
        )
        await self._sessions.finalize_game(
            game, status=GameStatus.COMPLETED, result=result
        )
        refreshed = await self._game_repo.get_by_id(game.id)
        return await self._to_game_response(refreshed)

    async def _get_owned_game(self, game_id: UUID, user_id: UUID) -> Game:
        game = await self._game_repo.get_by_id(game_id)
        if not game:
            raise NotFoundError("Game not found", code="GAME_NOT_FOUND")
        if game.user_id != user_id:
            raise ForbiddenError("You do not have access to this game")
        return game

    def _ensure_game_active(self, game: Game) -> None:
        if game.status != GameStatus.IN_PROGRESS:
            raise ValidationError(
                f"Game is not active (status={game.status.value})",
                code="GAME_NOT_ACTIVE",
            )

    def _ensure_correct_turn(self, game: Game, board: chess.Board) -> None:
        current = board_to_side(board)
        if current != game.user_color:
            raise InvalidMoveError("It is not your turn")

    async def _finalize_if_over(self, game: Game, board: chess.Board) -> None:
        result = determine_result(board)
        if result:
            pgn = export_pgn(board)
            await self._sessions.finalize_game(
                game,
                status=GameStatus.COMPLETED,
                result=result,
                pgn=pgn,
                current_fen=board.fen(),
            )

    def _board_meta(self, board: chess.Board, game: Game) -> dict:
        clock = self._sessions.get_clock_snapshot(game, board)
        return {
            "fen": board.fen(),
            "is_check": board.is_check(),
            "is_checkmate": board.is_checkmate(),
            "is_stalemate": board.is_stalemate(),
            "turn": board_to_side(board),
            "legal_moves": get_legal_moves_uci(board),
            **clock,
        }

    def _build_state_payload(self, game: Game, board: chess.Board) -> GameStatePayload:
        clock = self._sessions.get_clock_snapshot(game, board)
        return GameStatePayload(
            game_id=game.id,
            fen=board.fen(),
            status=game.status,
            result=game.result,
            move_count=game.move_count,
            turn=board_to_side(board),
            is_check=board.is_check(),
            is_checkmate=board.is_checkmate(),
            is_stalemate=board.is_stalemate(),
            legal_moves=get_legal_moves_uci(board),
            **clock,
        )

    async def _to_game_response(self, game: Game | None) -> GameResponse:
        if game is None:
            raise NotFoundError("Game not found", code="GAME_NOT_FOUND")

        loaded = await self._game_repo.get_by_id(game.id)
        if loaded is None:
            raise NotFoundError("Game not found", code="GAME_NOT_FOUND")

        board = create_board(loaded.current_fen)
        clock = self._sessions.get_clock_snapshot(loaded, board)
        data = GameResponse.model_validate(loaded).model_dump()
        data.update(clock)
        return GameResponse.model_validate(data)
