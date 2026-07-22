"""WebSocket session registry for tracking active game connections."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ActiveSession:
    game_id: UUID
    user_id: UUID
    websocket: WebSocket
    connection_id: UUID = field(default_factory=uuid4)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebSocketSessionManager:
    """Tracks active WebSocket connections per game (one live session per game)."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, ActiveSession] = {}
        self._lock = asyncio.Lock()

    async def register(
        self, game_id: UUID, user_id: UUID, websocket: WebSocket
    ) -> ActiveSession | None:
        """Register a connection. Returns the previous session if one existed."""
        async with self._lock:
            previous = self._sessions.get(game_id)
            self._sessions[game_id] = ActiveSession(
                game_id=game_id,
                user_id=user_id,
                websocket=websocket,
            )
            if previous and previous.websocket is not websocket:
                logger.info(
                    "Replacing active session for game %s (user %s)",
                    game_id,
                    user_id,
                )
            else:
                logger.info("Registered session for game %s (user %s)", game_id, user_id)
            return previous if previous and previous.websocket is not websocket else None

    async def unregister(self, game_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            session = self._sessions.get(game_id)
            if session and session.websocket is websocket:
                del self._sessions[game_id]
                logger.info("Unregistered session for game %s", game_id)

    def is_current(self, game_id: UUID, websocket: WebSocket) -> bool:
        session = self._sessions.get(game_id)
        return session is not None and session.websocket is websocket

    def is_active(self, game_id: UUID) -> bool:
        return game_id in self._sessions

    def get_session(self, game_id: UUID) -> ActiveSession | None:
        return self._sessions.get(game_id)

    def active_count(self) -> int:
        return len(self._sessions)

    def list_sessions(self) -> list[dict[str, str]]:
        return [
            {
                "game_id": str(session.game_id),
                "user_id": str(session.user_id),
                "connection_id": str(session.connection_id),
                "connected_at": session.connected_at.isoformat(),
            }
            for session in self._sessions.values()
        ]

    @staticmethod
    async def close_websocket(
        websocket: WebSocket,
        *,
        code: int = 1000,
        reason: str = "",
    ) -> None:
        """Close a websocket if still connected; ignore already-closed sockets."""
        if websocket.client_state != WebSocketState.CONNECTED:
            logger.debug(
                "Skipped closing websocket (state=%s)",
                websocket.client_state.name,
            )
            return

        try:
            await websocket.close(code=code, reason=reason)
        except RuntimeError as exc:
            message = str(exc).lower()
            if "close message has been sent" in message or "already completed" in message:
                logger.debug("Previous websocket was already closing")
                return
            raise
        except Exception as exc:
            logger.debug("Failed to close previous websocket: %s", exc)


session_manager = WebSocketSessionManager()
