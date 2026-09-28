"""Tests for iterative deepening and the time limit (search.Searcher)."""

import time

import pytest

from chess_ai import search
from chess_ai.engine import GameState

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -"


def is_legal(gs, move):
    return any(move == legal for legal in gs.get_legal_moves())


def test_fixed_depth_search_reaches_exactly_that_depth():
    result = search.Searcher(max_depth=3).search(GameState.from_fen(START))
    assert result.depth == 3
    assert result.timed_out is False
    assert result.nodes > 0 and result.cutoffs > 0


def test_fixed_depth_search_is_deterministic():
    first = search.Searcher(max_depth=3).search(GameState.from_fen(START))
    second = search.Searcher(max_depth=3).search(GameState.from_fen(START))
    assert (first.move, first.score, first.nodes) == (
        second.move,
        second.score,
        second.nodes,
    )


@pytest.mark.parametrize(
    "fen",
    [
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -",
        pytest.param(
            "r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/R4RK1 b - -",
            marks=pytest.mark.slow,
        ),
    ],
)
def test_iterative_deepening_finds_the_same_value_as_one_search(fen):
    """Alpha-beta returns the exact minimax value whatever the move order, so
    deepening 1-2-3 (which reorders the root) must agree with one depth-3 pass."""
    deepened = search.Searcher(max_depth=3).search(GameState.from_fen(fen))
    gs = GameState.from_fen(fen)
    _, single_pass_score = search.Searcher().search_depth(gs, gs.get_legal_moves(), 3)
    assert deepened.score == single_pass_score


def test_time_limit_is_respected():
    gs = GameState.from_fen(KIWIPETE)
    t0 = time.perf_counter()
    result = search.Searcher(time_limit=0.3).search(gs)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.3 + 0.35  # small margin for the node in progress and slow CI
    assert result.depth >= 1
    assert is_legal(gs, result.move)


def test_tiny_time_limit_still_returns_a_searched_move():
    gs = GameState.from_fen(KIWIPETE)
    result = search.Searcher(time_limit=0.001).search(gs)
    assert result.depth >= 1  # depth 1 is never interrupted
    assert is_legal(gs, result.move)


class FakeClock:
    """Stands in for time.perf_counter: every reading advances it by 1 ms, so a
    search's timing depends only on how often it reads the clock (roughly once
    per node) and never on the machine's speed or load."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 0.001
        return self.now


def test_interrupted_search_restores_the_position(state_snapshot, monkeypatch):
    gs = GameState.from_fen(KIWIPETE)
    before = state_snapshot(gs)
    # Depth 1 never reads the clock and always completes; depth 2 reads it at
    # every node and needs thousands of nodes here, so 0.1 s (100 readings)
    # always interrupts it.
    monkeypatch.setattr(search.time, "perf_counter", FakeClock())

    result = search.Searcher(time_limit=0.1).search(gs)

    assert result.timed_out is True
    assert result.depth == 1
    assert state_snapshot(gs) == before
    assert is_legal(gs, result.move)


def test_a_found_mate_stops_the_deepening():
    gs = GameState.from_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - -")  # Ra8#
    result = search.Searcher(max_depth=5).search(gs)
    assert result.depth == 1
    assert result.move.coordinate_notation() == "a1a8"


def test_find_best_move_accepts_a_time_limit():
    gs = GameState.from_fen(START)
    move = search.find_best_move(gs, gs.get_legal_moves(), time_limit=0.2)
    assert is_legal(gs, move)


def test_difficulty_presets_are_well_formed():
    assert search.DEFAULT_DIFFICULTY in search.DIFFICULTIES
    limits = [search.DIFFICULTIES[name] for name in ("easy", "medium", "hard")]
    assert all(level.time_limit > 0 for level in limits)
    # Harder levels think longer.
    assert [level.time_limit for level in limits] == sorted(
        level.time_limit for level in limits
    )


def test_easy_preset_respects_its_depth_cap_and_time():
    easy = search.DIFFICULTIES["easy"]
    gs = GameState.from_fen(START)
    result = search.Searcher(easy.max_depth, easy.time_limit).search(gs)
    assert result.depth <= easy.max_depth
    assert result.elapsed < easy.time_limit + 0.35
    assert is_legal(gs, result.move)
