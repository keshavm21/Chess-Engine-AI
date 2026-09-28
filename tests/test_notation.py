"""Tests for Move's coordinate notation (coordinate_notation) and the short
notation shown in the GUI move log (str(move))."""

import pytest

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


@pytest.mark.parametrize(
    ("fen", "coordinates", "short"),
    [
        pytest.param(STARTPOS, "e2e4", "e4", id="pawn-push"),
        pytest.param(STARTPOS, "g1f3", "Nf3", id="knight"),
        pytest.param("4k3/8/8/3p4/4P3/8/8/4K3 w - -", "e4d5", "exd5", id="capture"),
        pytest.param("4k3/8/8/8/8/8/8/4K2R w K -", "e1g1", "O-O", id="castle-short"),
        pytest.param("4k3/8/8/8/8/8/8/R3K3 w Q -", "e1c1", "O-O-O", id="castle-long"),
    ],
)
def test_notation_on_ranks_1_to_7(fen, coordinates, short, load_fen, legal_move):
    move = legal_move(load_fen(fen), coordinates)
    assert move.coordinate_notation() == coordinates
    assert str(move) == short


@pytest.mark.parametrize(
    ("fen", "coordinates", "short"),
    [
        pytest.param("8/7k/8/8/8/8/8/R3K3 w - -", "a1a8", "Ra8", id="rook-to-8"),
        pytest.param("4k3/8/6N1/8/8/8/8/4K3 w - -", "g6f8", "Nf8", id="knight-to-8"),
        pytest.param("4k3/8/8/8/8/8/8/4K3 b - -", "e8e7", "Ke7", id="king-from-8"),
    ],
)
def test_notation_on_rank_8(fen, coordinates, short, load_fen, legal_move):
    """Regression test for finding R2: rank 8 used to be written as "0"."""
    move = legal_move(load_fen(fen), coordinates)
    assert move.coordinate_notation() == coordinates
    assert str(move) == short
