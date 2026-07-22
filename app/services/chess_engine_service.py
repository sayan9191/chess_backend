"""Stockfish chess engine integration with safe lifecycle management."""

from __future__ import annotations

import asyncio
import os
import random
import shutil
from contextlib import contextmanager
from typing import Iterator

import chess

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def _stockfish_binary_exists(path: str) -> bool:
    """Return True only if the Stockfish executable is reachable."""
    if os.path.isfile(path) and os.access(path, os.X_OK):
        return True
    return shutil.which(path) is not None


def _fallback_move(fen: str) -> str:
    """Pick a random legal move when Stockfish is unavailable."""
    board = chess.Board(fen)
    move = random.choice(list(board.legal_moves))
    return move.uci()


@contextmanager
def _stockfish_session() -> Iterator[object]:
    """
    Open a Stockfish process for one computation and ensure clean shutdown.
    """
    settings = get_settings()
    if not _stockfish_binary_exists(settings.stockfish_path):
        raise FileNotFoundError(
            f"Stockfish binary not found at '{settings.stockfish_path}'. "
            "Install with: brew install stockfish"
        )

    engine = None
    try:
        from stockfish import Stockfish

        engine = Stockfish(
            path=settings.stockfish_path,
            parameters={"Skill Level": settings.stockfish_skill_level},
        )
        if not engine.is_fen_valid(chess.STARTING_FEN):
            raise RuntimeError("Stockfish failed startup validation")
        yield engine
    finally:
        if engine is not None and hasattr(engine, "_stockfish"):
            try:
                process = engine._stockfish
                if process is not None and process.poll() is None:
                    engine._put("quit")
                    process.wait(timeout=2)
            except Exception as exc:
                logger.debug("Stockfish shutdown: %s", exc)


class ChessEngineService:
    """Wraps Stockfish for async-friendly engine move generation."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._stockfish_available: bool | None = None

    def _check_availability(self) -> bool:
        available = _stockfish_binary_exists(self._settings.stockfish_path)
        self._stockfish_available = available
        return available

    def _compute_best_move(self, fen: str) -> tuple[str, bool]:
        """Returns (move_uci, used_stockfish)."""
        if not self._check_availability():
            logger.warning(
                "Stockfish not installed (path=%s), using random legal move",
                self._settings.stockfish_path,
            )
            return _fallback_move(fen), False

        try:
            with _stockfish_session() as engine:
                engine.set_fen_position(fen)
                engine.set_skill_level(self._settings.stockfish_skill_level)
                move = engine.get_best_move_time(self._settings.stockfish_move_time_ms)
                if not move:
                    raise RuntimeError("Engine returned no move")
                return move, True
        except Exception as exc:
            logger.warning("Stockfish error (%s), using fallback move", exc)
            self._stockfish_available = False
            return _fallback_move(fen), False

    async def get_best_move(self, fen: str) -> str:
        """Return the best move in UCI format for the given FEN."""
        move, used_stockfish = await asyncio.to_thread(self._compute_best_move, fen)
        if used_stockfish:
            self._stockfish_available = True
        return move

    async def is_available(self) -> bool:
        return await asyncio.to_thread(self._check_availability)
