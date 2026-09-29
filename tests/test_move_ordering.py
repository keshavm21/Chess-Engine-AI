"""Tests for quiet-move ordering: killer moves and the history heuristic."""

import pytest

from chess_ai import search
from chess_ai.benchmark import SEARCH_POSITIONS
from chess_ai.engine import GameState


def moves_by_name(gs):
    return {m.coordinate_notation(): m for m in gs.get_legal_moves()}


def test_killers_keep_the_two_latest_quiet_cutoff_moves():
    gs = GameState()
    moves = moves_by_name(gs)
    searcher = search.Searcher()
    for name in ("g1f3", "b1c3", "g1f3", "e2e4"):
        searcher._remember_quiet_cutoff(moves[name], depth=2, ply=3)
    killers = searcher._killers[3]
    assert [m.coordinate_notation() for m in killers] == ["e2e4", "b1c3"]
    # History accumulates depth squared per piece and target square.
    assert searcher._history[search._history_key(moves["g1f3"])] == 8


def test_order_is_captures_then_killers_then_history():
    gs = GameState.from_fen("4k3/8/8/3p4/4P3/8/8/R3K2R w KQ -")
    moves = moves_by_name(gs)
    searcher = search.Searcher()
    searcher._remember_quiet_cutoff(moves["a1a7"], depth=3, ply=2)  # killer
    searcher._history[search._history_key(moves["h1h7"])] = 50
    ordered = sorted(
        moves.values(),
        key=lambda m: searcher._quiet_order(m, searcher._killers[2]),
        reverse=True,
    )
    names = [m.coordinate_notation() for m in ordered]
    assert names[:3] == ["e4d5", "a1a7", "h1h7"]


def test_ordering_can_be_switched_off():
    searcher = search.Searcher(max_depth=4, history_ordering=False)
    searcher.search(GameState())
    assert searcher._killers == {} and searcher._history == {}


def test_search_records_killers_and_history():
    searcher = search.Searcher(max_depth=4)
    searcher.search(GameState())
    assert searcher._killers and searcher._history


@pytest.mark.parametrize(
    "depth", [3, pytest.param(4, marks=pytest.mark.slow)], ids=["depth-3", "depth-4"]
)
@pytest.mark.parametrize(
    "name,fen", SEARCH_POSITIONS, ids=[n for n, _ in SEARCH_POSITIONS]
)
def test_same_result_as_without_the_ordering(name, fen, depth):
    """Ordering only changes how much is searched, not the result."""
    with_ordering = search.Searcher(max_depth=depth).search(GameState.from_fen(fen))
    without = search.Searcher(max_depth=depth, history_ordering=False).search(
        GameState.from_fen(fen)
    )
    assert (with_ordering.move, with_ordering.score) == (without.move, without.score)
