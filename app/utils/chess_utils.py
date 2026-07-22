"""Chess board utilities using python-chess."""

from __future__ import annotations

import chess
import chess.pgn
from io import StringIO

from app.models.game import GameResult, PlayerSide

STARTING_FEN = chess.STARTING_FEN


def create_board(fen: str | None = None) -> chess.Board:
    return chess.Board(fen or STARTING_FEN)


def parse_uci_move(uci: str, promotion: str | None = None) -> chess.Move:
    move = chess.Move.from_uci(uci)
    if promotion:
        piece_map = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}
        move.promotion = piece_map[promotion]
    return move


def is_legal_move(board: chess.Board, uci: str, promotion: str | None = None) -> bool:
    try:
        move = parse_uci_move(uci, promotion)
        return move in board.legal_moves
    except ValueError:
        return False


def apply_move(board: chess.Board, uci: str, promotion: str | None = None) -> tuple[chess.Move, str]:
    move = parse_uci_move(uci, promotion)
    if move not in board.legal_moves:
        raise ValueError(f"Illegal move: {uci}")
    move_san = board.san(move)
    board.push(move)
    return move, move_san


def get_legal_moves_uci(board: chess.Board) -> list[str]:
    return [move.uci() for move in board.legal_moves]


def board_to_side(board: chess.Board) -> PlayerSide:
    return PlayerSide.WHITE if board.turn == chess.WHITE else PlayerSide.BLACK


def determine_result(board: chess.Board) -> GameResult | None:
    if board.is_checkmate():
        return GameResult.BLACK_WINS if board.turn == chess.WHITE else GameResult.WHITE_WINS
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return GameResult.DRAW
    return None


def export_pgn(board: chess.Board) -> str:
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
    return board.accept(exporter)


def build_pgn_from_moves(moves_san: list[str]) -> str:
    board = create_board()
    game = chess.pgn.Game()
    node = game
    for san in moves_san:
        move = board.parse_san(san)
        board.push(move)
        node = node.add_variation(move)
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
    return game.accept(exporter)
