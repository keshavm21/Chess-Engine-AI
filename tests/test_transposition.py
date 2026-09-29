"""Tests for the transposition table."""

import pytest

from chess_ai import search
from chess_ai.benchmark import SEARCH_POSITIONS
from chess_ai.engine import GameState
from chess_ai.evaluation import CHECKMATE


@pytest.mark.parametrize("score", [0, 37, -250, CHECKMATE - 3, -(CHECKMATE - 4)])
@pytest.mark.parametrize("ply", [0, 1, 5])
def test_scores_round_trip_through_the_table(score, ply):
    assert search._score_from_tt(search._score_to_tt(score, ply), ply) == score


def test_mate_scores_are_stored_relative_to_the_node():
    # A mate 5 plies from the root, seen at a node 2 plies from the root, is a
    # mate 3 plies from that node -- wherever the node is reached later.
    stored = search._score_to_tt(CHECKMATE - 5, ply=2)
    assert stored == CHECKMATE - 3
    assert search._score_from_tt(stored, ply=4) == CHECKMATE - 7


@pytest.mark.parametrize(
    ("fen", "expected_move", "expected_score"),
    [
        ("8/8/7k/8/8/8/R7/1R4K1 w - -", "a2g2", CHECKMATE - 5),  # mate in 3
        ("6r1/8/8/8/5k2/8/8/7K b - -", "f4g3", -(CHECKMATE - 5)),  # Black mates
    ],
)
def test_mate_distance_is_exact_with_the_table(fen, expected_move, expected_score):
    result = search.Searcher(max_depth=6).search(GameState.from_fen(fen))
    assert result.move.coordinate_notation() == expected_move
    assert result.score == expected_score


@pytest.mark.parametrize(
    "name,fen", SEARCH_POSITIONS, ids=[n for n, _ in SEARCH_POSITIONS]
)
def test_same_result_with_fewer_nodes(name, fen):
    """On these positions the table changes how much is searched, not the
    result (in general it may differ where it reuses a deeper search)."""
    with_table = search.Searcher(max_depth=3).search(GameState.from_fen(fen))
    without = search.Searcher(max_depth=3, transposition_table=False).search(
        GameState.from_fen(fen)
    )
    assert (with_table.move, with_table.score) == (without.move, without.score)
    assert with_table.nodes <= without.nodes


def test_positions_reached_twice_are_answered_from_the_table():
    kiwipete = SEARCH_POSITIONS[3][1]
    result = search.Searcher(max_depth=4).search(GameState.from_fen(kiwipete))
    assert result.tt_hits > 0


def test_the_root_entry_holds_the_chosen_move():
    gs = GameState()
    searcher = search.Searcher(max_depth=3)
    result = searcher.search(gs)
    depth, _, bound, move = searcher.tt[gs.zobrist_key]
    assert (depth, bound, move) == (3, search.EXACT, result.move)


def test_the_table_size_is_capped(monkeypatch):
    monkeypatch.setattr(search, "TT_MAX_ENTRIES", 50)
    searcher = search.Searcher(max_depth=3)
    searcher.search(GameState())
    assert 0 < len(searcher.tt) <= 50


def test_the_table_can_be_switched_off():
    searcher = search.Searcher(max_depth=2, transposition_table=False)
    result = searcher.search(GameState())
    assert searcher.tt is None and result.tt_hits == 0
