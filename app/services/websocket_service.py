"""WebSocket connection manager and game session handler."""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.core.logger import get_logger
from app.core.security import JWTError, decode_access_token
from app.models.game import GameStatus, OpponentType, PlayerSide
from app.repositories.game_repository import GameRepository
from app.repositories.user_repository import UserRepository
from app.schemas.game import GameMoveResponse
from app.schemas.websocket import (
    WSConnectedPayload,
    WSEngineMovePayload,
    WSGameOverPayload,
    WSMessage,
    WSMessageType,
    WSMoveAckPayload,
    WSMovePayload,
    WSErrorPayload,
)
from app.services.chess_engine_service import ChessEngineService
from app.services.game_service import GameService
from app.services.websocket_session_manager import session_manager
from app.utils.chess_utils import board_to_side, create_board
from app.utils.exceptions import AppException

logger = get_logger(__name__)


class WebSocketGameHandler:
    """Handles bidirectional WebSocket messaging for a single game session."""

    def __init__(
        self,
        websocket: WebSocket,
        game_id: UUID,
        session: AsyncSession,
    ) -> None:
        self._ws = websocket
        self._game_id = game_id
        self._session = session
        self._user_id: UUID | None = None
        self._registered = False

        user_repo = UserRepository(session)
        game_repo = GameRepository(session)
        engine = ChessEngineService()
        self._game_service = GameService(game_repo, engine)
        self._game_repo = game_repo
        self._user_repo = user_repo

    async def authenticate(self, token: str) -> bool:
        try:
            payload = decode_access_token(token)
            self._user_id = UUID(payload["sub"])
            user = await self._user_repo.get_by_id(self._user_id)
            if not user or not user.is_active:
                await self._send_error("UNAUTHORIZED", "Invalid or inactive user")
                return False
            return True
        except (JWTError, ValueError, KeyError) as exc:
            logger.warning("WebSocket auth failed: %s", exc)
            await self._send_error("UNAUTHORIZED", "Invalid authentication token")
            return False

    async def run(self, token: str) -> None:
        await self._ws.accept()

        if not await self.authenticate(token):
            await self._ws.close(code=4001)
            return

        game = await self._game_repo.get_by_id(self._game_id)
        if not game or game.user_id != self._user_id:
            await self._send_error("FORBIDDEN", "Game not found or access denied")
            await self._ws.close(code=4003)
            return

        previous_session = await session_manager.register(
            self._game_id, self._user_id, self._ws
        )
        self._registered = True

        if previous_session is not None:
            await session_manager.close_websocket(
                previous_session.websocket,
                code=4002,
                reason="Replaced by a new session",
            )

        if not self._is_current_session():
            logger.info(
                "Connection superseded during setup for game %s; exiting",
                self._game_id,
            )
            return

        game_resp = await self._game_service.activate_game(self._game_id, self._user_id)
        if game_resp.status in {GameStatus.COMPLETED, GameStatus.ABANDONED}:
            await self._send(
                WSMessageType.CONNECTED,
                WSConnectedPayload(
                    game_id=game_resp.id,
                    user_color=game_resp.user_color,
                    fen=game_resp.current_fen,
                    status=game_resp.status,
                    result=game_resp.result,
                    is_live_session=True,
                    replaced_previous_session=previous_session is not None,
                    time_limit_seconds=game_resp.time_limit_seconds,
                    user_time_remaining_ms=game_resp.user_time_remaining_ms,
                    opponent_time_remaining_ms=game_resp.opponent_time_remaining_ms,
                    started_at=game_resp.started_at,
                    last_activity_at=game_resp.last_activity_at,
                ).model_dump(mode="json"),
            )
            if game_resp.status == GameStatus.COMPLETED:
                await self._send_game_over(game_resp)
            await self._ws.close(code=4004, reason="Game is no longer active")
            return

        await self._send(
            WSMessageType.CONNECTED,
            WSConnectedPayload(
                game_id=game_resp.id,
                user_color=game_resp.user_color,
                fen=game_resp.current_fen,
                status=game_resp.status,
                result=game_resp.result,
                is_live_session=True,
                replaced_previous_session=previous_session is not None,
                time_limit_seconds=game_resp.time_limit_seconds,
                user_time_remaining_ms=game_resp.user_time_remaining_ms,
                opponent_time_remaining_ms=game_resp.opponent_time_remaining_ms,
                clock_running_for=game_resp.clock_running_for,
                started_at=game_resp.started_at,
                last_activity_at=game_resp.last_activity_at,
            ).model_dump(mode="json"),
        )

        engine_task = asyncio.create_task(self._run_post_connect_tasks())

        try:
            while True:
                if not self._is_current_session():
                    logger.info(
                        "Stopping superseded websocket handler for game %s",
                        self._game_id,
                    )
                    break

                raw = await self._ws.receive_text()
                await self._handle_message(raw)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for game %s", self._game_id)
        except Exception as exc:
            if self._is_current_session():
                logger.exception("WebSocket error for game %s: %s", self._game_id, exc)
                await self._send_error("INTERNAL_ERROR", "An unexpected error occurred")
        finally:
            engine_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await engine_task
            if self._registered:
                await session_manager.unregister(self._game_id, self._ws)
                self._registered = False

    async def _run_post_connect_tasks(self) -> None:
        """Run engine opening moves without blocking the message loop."""
        if not self._is_current_session():
            return
        try:
            await self._maybe_trigger_engine_on_connect()
        except Exception as exc:
            if self._is_current_session():
                logger.exception(
                    "Post-connect task failed for game %s: %s",
                    self._game_id,
                    exc,
                )

    def _is_current_session(self) -> bool:
        return session_manager.is_current(self._game_id, self._ws)

    async def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
            message = WSMessage.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            await self._send_error("INVALID_MESSAGE", f"Malformed message: {exc}")
            return

        handlers = {
            WSMessageType.PING: self._handle_ping,
            WSMessageType.MOVE: self._handle_move,
            WSMessageType.RESIGN: self._handle_resign,
            WSMessageType.CONNECT: self._handle_connect_refresh,
        }

        handler = handlers.get(message.type)
        if not handler:
            await self._send_error(
                "UNKNOWN_TYPE",
                f"Unknown message type: {message.type}",
                request_id=message.request_id,
            )
            return

        await handler(message)

    async def _handle_ping(self, message: WSMessage) -> None:
        await self._send(
            WSMessageType.PONG,
            {
                "timestamp": message.payload.get("timestamp"),
                "server_time": datetime.now(timezone.utc).isoformat(),
            },
            request_id=message.request_id,
        )

    async def _handle_connect_refresh(self, message: WSMessage) -> None:
        state = await self._game_service.get_game_state(self._game_id, self._user_id)
        await self._send(
            WSMessageType.GAME_STATE,
            state.model_dump(mode="json"),
            request_id=message.request_id,
        )

    async def _handle_move(self, message: WSMessage) -> None:
        try:
            move_payload = WSMovePayload.model_validate(message.payload)
            game_resp, meta = await self._game_service.make_human_move(
                self._game_id,
                self._user_id,
                move_payload.uci,
                move_payload.promotion,
            )
            move = meta["move"]

            await self._send(
                WSMessageType.MOVE_ACK,
                WSMoveAckPayload(
                    move=GameMoveResponse.model_validate(move),
                    fen=meta["fen"],
                    is_check=meta["is_check"],
                    is_checkmate=meta["is_checkmate"],
                    is_stalemate=meta["is_stalemate"],
                    turn=meta["turn"],
                    user_time_remaining_ms=meta.get("user_time_remaining_ms"),
                    opponent_time_remaining_ms=meta.get("opponent_time_remaining_ms"),
                    clock_running_for=meta.get("clock_running_for"),
                ).model_dump(mode="json"),
                request_id=message.request_id,
            )

            if game_resp.status == GameStatus.COMPLETED:
                await self._send_game_over(game_resp)
                return

            game = await self._game_repo.get_by_id(self._game_id)
            if game and game.opponent_type == OpponentType.MACHINE:
                await self._trigger_engine_move(message.request_id)

        except AppException as exc:
            await self._send_error(exc.code, exc.message, request_id=message.request_id)

    async def _maybe_trigger_engine_on_connect(self) -> None:
        """If the computer should move first (user plays black), make that move."""
        game = await self._game_repo.get_by_id(self._game_id)
        if not game or game.status != GameStatus.IN_PROGRESS:
            return
        if game.opponent_type != OpponentType.MACHINE:
            return

        board = create_board(game.current_fen)
        engine_side = (
            PlayerSide.BLACK if game.user_color == PlayerSide.WHITE else PlayerSide.WHITE
        )
        if board_to_side(board) == engine_side:
            await self._trigger_engine_move(request_id=None)

    async def _trigger_engine_move(self, request_id: str | None) -> None:
        try:
            game_resp, meta = await self._game_service.make_engine_move(
                self._game_id, self._user_id
            )
            move = meta["move"]

            await self._send(
                WSMessageType.ENGINE_MOVE,
                WSEngineMovePayload(
                    move=GameMoveResponse.model_validate(move),
                    fen=meta["fen"],
                    is_check=meta["is_check"],
                    is_checkmate=meta["is_checkmate"],
                    is_stalemate=meta["is_stalemate"],
                    turn=meta.get("turn"),
                    user_time_remaining_ms=meta.get("user_time_remaining_ms"),
                    opponent_time_remaining_ms=meta.get("opponent_time_remaining_ms"),
                    clock_running_for=meta.get("clock_running_for"),
                ).model_dump(mode="json"),
                request_id=request_id,
            )

            if game_resp.status == GameStatus.COMPLETED:
                await self._send_game_over(game_resp)

        except AppException as exc:
            await self._send_error(exc.code, exc.message, request_id=request_id)
        except RuntimeError as exc:
            await self._send_error("ENGINE_UNAVAILABLE", str(exc), request_id=request_id)

    async def _handle_resign(self, message: WSMessage) -> None:
        try:
            game_resp = await self._game_service.resign_game(self._game_id, self._user_id)
            await self._send_game_over(
                game_resp, reason="resignation", request_id=message.request_id
            )
        except AppException as exc:
            await self._send_error(exc.code, exc.message, request_id=message.request_id)

    async def _send_game_over(
        self, game_resp, reason: str = "checkmate", request_id: str | None = None
    ) -> None:
        if game_resp.result.value == "draw":
            reason = "draw"
        elif reason == "checkmate":
            reason = "checkmate" if reason != "resignation" else "resignation"

        await self._send(
            WSMessageType.GAME_OVER,
            WSGameOverPayload(
                result=game_resp.result,
                reason=reason,
                fen=game_resp.current_fen,
                pgn=game_resp.pgn,
            ).model_dump(mode="json"),
            request_id=request_id,
        )

    async def _send(
        self,
        msg_type: WSMessageType,
        payload: dict,
        request_id: str | None = None,
    ) -> None:
        if (
            not self._is_current_session()
            or self._ws.client_state != WebSocketState.CONNECTED
        ):
            return

        message = WSMessage(type=msg_type, payload=payload, request_id=request_id)
        try:
            await self._ws.send_text(message.model_dump_json())
        except RuntimeError as exc:
            if "close message has been sent" in str(exc).lower():
                return
            raise

    async def _send_error(
        self,
        code: str,
        message: str,
        request_id: str | None = None,
    ) -> None:
        await self._send(
            WSMessageType.ERROR,
            WSErrorPayload(code=code, message=message).model_dump(),
            request_id=request_id,
        )
