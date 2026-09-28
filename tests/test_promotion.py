"""Tests for pawn promotion, including underpromotion (finding R1)."""

import pytest

from chess_ai import search
from chess_ai.engine import Move


def promotions_by_square(gs):
    """{(start, end): sorted promotion pieces} for all legal promotion moves."""
    found = {}
    for move in gs.get_legal_moves():
        if move.is_promotion:
            key = ((move.start_row, move.start_col), (move.end_row, move.end_col))
            found.setdefault(key, []).append(move.promotion_piece)
    return {key: sorted(pieces) for key, pieces in found.items()}


@pytest.mark.parametrize(
    ("fen", "push", "capture"),
    [
        # White a7 pawn: push to a8, capture the knight on b8.
        pytest.param(
            "1n2k3/P7/8/8/8/8/8/4K3 w - -",
            ((1, 0), (0, 0)),
            ((1, 0), (0, 1)),
            id="white",
        ),
        # Black h2 pawn: push to h1, capture the knight on g1.
        pytest.param(
            "4k3/8/8/8/8/8/7p/4K1N1 b - -",
            ((6, 7), (7, 7)),
            ((6, 7), (7, 6)),
            id="black",
        ),
    ],
)
def test_all_four_promotion_pieces_are_generated(fen, push, capture, load_fen):
    promotions = promotions_by_square(load_fen(fen))
    assert promotions == {push: ["B", "N", "Q", "R"], capture: ["B", "N", "Q", "R"]}


@pytest.mark.parametrize("piece", ["Q", "R", "B", "N"])
def test_make_and_undo_promotion(piece, load_fen, legal_move, state_snapshot):
    gs = load_fen("1n2k3/P7/8/8/8/8/8/4K3 w - -")
    before = state_snapshot(gs)

    gs.make_move(legal_move(gs, "a7b8" + piece.lower()))
    assert gs.board[0][1] == "w" + piece  # the knight on b8 was captured
    assert gs.board[1][0] == "--"

    gs.undo_move()
    assert state_snapshot(gs) == before
    assert gs.board[0][1] == "bN" and gs.board[1][0] == "wp"


@pytest.mark.parametrize(
    ("coordinates", "coordinate_notation", "short"),
    [
        ("a7a8q", "a7a8q", "a8=Q"),
        ("a7a8n", "a7a8n", "a8=N"),
        ("a7b8r", "a7b8r", "axb8=R"),
        ("a7b8b", "a7b8b", "axb8=B"),
    ],
)
def test_promotion_notation(
    coordinates, coordinate_notation, short, load_fen, legal_move
):
    move = legal_move(load_fen("1n2k3/P7/8/8/8/8/8/4K3 w - -"), coordinates)
    assert move.coordinate_notation() == coordinate_notation
    assert str(move) == short


def test_move_from_two_clicks_matches_only_the_queen_promotion(load_fen):
    """The GUI builds a Move from the two clicked squares; without a piece
    picker it must match exactly one legal move: the queen promotion."""
    gs = load_fen("1n2k3/P7/8/8/8/8/8/4K3 w - -")
    clicked = Move((1, 0), (0, 0), gs.board)

    matches = [move for move in gs.get_legal_moves() if move == clicked]

    assert len(matches) == 1
    assert matches[0].promotion_piece == "Q"


def test_non_promotion_moves_have_no_promotion_piece(load_fen, legal_move):
    move = legal_move(load_fen("4k3/8/8/8/8/8/P7/4K3 w - -"), "a2a4")
    assert move.is_promotion is False
    assert move.promotion_piece is None


def test_search_underpromotes_to_a_knight_when_it_forks(load_fen):
    """e8=N+ forks the king on g7 and the queen on c7 and wins the queen;
    e8=Q only trades into a queen-vs-queen position."""
    gs = load_fen("8/2q1P1k1/8/8/8/8/8/4K3 w - -")
    chosen = search.find_best_move(gs, list(gs.get_legal_moves()))
    assert chosen.coordinate_notation() == "e7e8n"
