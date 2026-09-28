"""Shared pytest fixtures."""

import pytest

from chess_ai.engine import GameState


def snapshot(gs):
    """A comparable, immutable snapshot of everything make_move()/undo_move()
    touch. Two snapshots being equal means the state is truly identical, not
    just "the board looks the same"."""
    cr = gs.castling_rights
    return (
        tuple(tuple(row) for row in gs.board),
        gs.white_to_move,
        (cr.wks, cr.bks, cr.wqs, cr.bqs),
        gs.en_passant_square,
        gs.white_king_location,
        gs.black_king_location,
        len(gs.move_log),
    )


def square(name):
    """(row, col) for a square name such as "e4". Computed here rather than
    via Move.RANKS_TO_ROWS, which maps rank 8 incorrectly (finding R2)."""
    return 8 - int(name[1]), ord(name[0]) - ord("a")


def find_legal_move(gs, coordinates):
    """The legal move matching a coordinate string such as "e2e4"."""
    start, end = square(coordinates[:2]), square(coordinates[2:4])
    for move in gs.get_legal_moves():
        if (move.start_row, move.start_col, move.end_row, move.end_col) == start + end:
            return move
    # pytest.fail, not AssertionError: a broken lookup must never be mistaken
    # for the expected failure of an xfail(raises=AssertionError) test.
    pytest.fail(f"{coordinates} is not a legal move here")


@pytest.fixture
def load_fen():
    """Factory fixture: ``gs = load_fen("<fen>")`` returns a fresh GameState."""
    return GameState.from_fen


@pytest.fixture
def legal_move():
    """``legal_move(gs, "e2e4")`` returns that legal Move, or fails the test."""
    return find_legal_move


@pytest.fixture
def state_snapshot():
    """``state_snapshot(gs)`` returns a comparable snapshot of the full state."""
    return snapshot
