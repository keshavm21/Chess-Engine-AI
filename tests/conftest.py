"""Shared pytest fixtures.

The engine has no FEN parser of its own yet (planned for Phase 2 of
docs/improvement-plan), so the test suite provides one here. benchmark.py still
carries its own copy until then.
"""

import pytest

import chessEngine

PIECE_FROM_FEN = {
    "p": "bp",
    "n": "bN",
    "b": "bB",
    "r": "bR",
    "q": "bQ",
    "k": "bK",
    "P": "wp",
    "N": "wN",
    "B": "wB",
    "R": "wR",
    "Q": "wQ",
    "K": "wK",
}


def position_from_fen(fen):
    """Return a new GameState set up from a FEN string.

    Only the fields chessEngine.GameState actually tracks are set (board, side
    to move, castling rights, en-passant square, and the logs undoMove() pops).
    The halfmove clock and fullmove number are ignored, since the engine does
    not implement the fifty-move rule or move numbering.
    """
    placement, side, castling, ep = fen.split()[:4]
    gs = chessEngine.GameState()

    board = []
    for row in placement.split("/"):
        board_row = []
        for ch in row:
            if ch.isdigit():
                board_row.extend(["--"] * int(ch))
            else:
                board_row.append(PIECE_FROM_FEN[ch])
        board.append(board_row)
    gs.board = board

    gs.whiteToMove = side == "w"

    gs.currentCastlingRights = chessEngine.CastleRights(
        "K" in castling,
        "k" in castling,
        "Q" in castling,
        "q" in castling,
    )
    gs.castleRightLog = [
        chessEngine.CastleRights(
            gs.currentCastlingRights.wks,
            gs.currentCastlingRights.bks,
            gs.currentCastlingRights.wqs,
            gs.currentCastlingRights.bqs,
        )
    ]

    if ep == "-":
        gs.enpassantPossible = ()
    else:
        col = chessEngine.Move.fileToCols[ep[0]]
        row = chessEngine.Move.ranksToRows[ep[1]]
        gs.enpassantPossible = (row, col)
    gs.enpassantPossibleLog = [gs.enpassantPossible]

    gs.moveLog = []

    for r in range(8):
        for c in range(8):
            if gs.board[r][c] == "wK":
                gs.whiteKingLocation = (r, c)
            elif gs.board[r][c] == "bK":
                gs.blackKingLocation = (r, c)

    gs.checkmate = False
    gs.stalemate = False
    return gs


def snapshot(gs):
    """A comparable, immutable snapshot of everything makeMove()/undoMove()
    touch. Two snapshots being equal means the state is truly identical, not
    just "the board looks the same"."""
    cr = gs.currentCastlingRights
    return (
        tuple(tuple(row) for row in gs.board),
        gs.whiteToMove,
        (cr.wks, cr.bks, cr.wqs, cr.bqs),
        gs.enpassantPossible,
        gs.whiteKingLocation,
        gs.blackKingLocation,
        len(gs.moveLog),
    )


def square(name):
    """(row, col) for a square name such as "e4". Computed here rather than
    via Move.ranksToRows, which maps rank 8 incorrectly (finding R2)."""
    return 8 - int(name[1]), ord(name[0]) - ord("a")


def find_legal_move(gs, coordinates):
    """The legal move matching a coordinate string such as "e2e4"."""
    start, end = square(coordinates[:2]), square(coordinates[2:4])
    for move in gs.getValidMoves():
        if (move.startRow, move.startCol, move.endRow, move.endCol) == start + end:
            return move
    # pytest.fail, not AssertionError: a broken lookup must never be mistaken
    # for the expected failure of an xfail(raises=AssertionError) test.
    pytest.fail(f"{coordinates} is not a legal move here")


@pytest.fixture
def load_fen():
    """Factory fixture: ``gs = load_fen("<fen>")`` returns a fresh GameState."""
    return position_from_fen


@pytest.fixture
def legal_move():
    """``legal_move(gs, "e2e4")`` returns that legal Move, or fails the test."""
    return find_legal_move


@pytest.fixture
def state_snapshot():
    """``state_snapshot(gs)`` returns a comparable snapshot of the full state."""
    return snapshot
