"""Tests for game-status detection (finding R5): legal-move generation is a
pure query, and checkmate/stalemate are set only by update_game_status()."""

import math

import pytest

from chess_ai import search
from chess_ai.evaluation import CHECKMATE, STALEMATE

CHECKMATED = "3R2k1/5ppp/8/8/8/8/8/6K1 b - -"  # back-rank mate: Black to move
STALEMATED = "7k/8/6QK/8/8/8/8/8 b - -"  # Black to move, no legal moves
NORMAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


@pytest.mark.parametrize("fen", [CHECKMATED, STALEMATED, NORMAL])
def test_get_legal_moves_does_not_change_the_position(fen, load_fen, state_snapshot):
    gs = load_fen(fen)
    before = (state_snapshot(gs), gs.checkmate, gs.stalemate)

    gs.get_legal_moves()

    assert (state_snapshot(gs), gs.checkmate, gs.stalemate) == before


@pytest.mark.parametrize(
    ("fen", "expected"),
    [
        pytest.param(CHECKMATED, (True, False), id="checkmate"),
        pytest.param(STALEMATED, (False, True), id="stalemate"),
        pytest.param(NORMAL, (False, False), id="normal"),
    ],
)
def test_update_game_status(fen, expected, load_fen):
    gs = load_fen(fen)
    gs.update_game_status()
    assert (gs.checkmate, gs.stalemate) == expected

    # Passing precomputed legal moves gives the same answer.
    gs.checkmate = gs.stalemate = None
    gs.update_game_status(gs.get_legal_moves())
    assert (gs.checkmate, gs.stalemate) == expected


def test_update_game_status_clears_stale_flags(load_fen):
    gs = load_fen(NORMAL)
    gs.checkmate = True
    gs.update_game_status()
    assert (gs.checkmate, gs.stalemate) == (False, False)


@pytest.mark.parametrize("depth", [0, 2])
def test_search_scores_checkmate_from_empty_move_list(depth, load_fen):
    """The search decides terminal positions from the (empty) legal move list,
    without the flags; Black is mated here, so the score is +(CHECKMATE + depth)."""
    gs = load_fen(CHECKMATED)
    score = search.minimax_alpha_beta(gs, [], depth, -math.inf, math.inf, False)
    assert score == CHECKMATE + depth


def test_search_scores_stalemate_from_empty_move_list(load_fen):
    gs = load_fen(STALEMATED)
    assert search.minimax_alpha_beta(gs, [], 2, -math.inf, math.inf, False) == STALEMATE
