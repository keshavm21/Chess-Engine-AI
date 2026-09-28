"""Tests for the quiescence search and captures-only move generation."""

import random

import pytest

from chess_ai import search, tactics
from chess_ai.engine import GameState
from chess_ai.evaluation import TEMPO

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


def test_captures_only_is_exactly_the_captures_and_promotions():
    rng = random.Random(3)
    starts = [
        START,
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -",
    ]
    for _ in range(200):
        gs = GameState.from_fen(rng.choice(starts))
        for _ in range(rng.randint(0, 30)):
            moves = gs.get_legal_moves()
            if not moves:
                break
            gs.make_move(rng.choice(moves))
        expected = [
            m.coordinate_notation()
            for m in gs.get_legal_moves()
            if m.is_capture or m.is_promotion
        ]
        actual = [
            m.coordinate_notation() for m in gs.get_legal_moves(captures_only=True)
        ]
        assert actual == expected, gs.to_fen()


def test_quiet_position_scores_its_static_evaluation():
    gs = GameState.from_fen(START)
    _, score = search.Searcher().search_depth(gs, gs.get_legal_moves(), 0)
    assert score == TEMPO  # no captures to play out


def test_quiescence_sees_the_recapture():
    """Qxd5 wins a pawn at depth 1, but c6xd5 wins the queen back. Without
    quiescence a 1-ply search grabs the pawn; with it, it does not."""
    fen = "4k3/8/2p5/3p4/8/8/8/3QK3 w - -"
    greedy = search.Searcher(max_depth=1, quiescence=False).search(
        GameState.from_fen(fen)
    )
    careful = search.Searcher(max_depth=1).search(GameState.from_fen(fen))
    assert greedy.move.coordinate_notation() == "d1d5"
    assert careful.move.coordinate_notation() != "d1d5"


@pytest.mark.parametrize(
    "puzzle",
    [p for p in tactics.PUZZLES if p.name.startswith("Poisoned pawn")],
    ids=lambda p: p.name,
)
def test_poisoned_pawn_is_refused_at_depth_three(puzzle):
    """The refutation is 4 plies deep: beyond a depth-3 search without
    quiescence, but found by the quiescence search."""
    result = search.Searcher(max_depth=3).search(GameState.from_fen(puzzle.fen))
    assert puzzle.is_solved_by(result.move.coordinate_notation())


def test_quiescence_nodes_are_counted():
    kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -"
    result = search.Searcher(max_depth=1).search(GameState.from_fen(kiwipete))
    assert 0 < result.qnodes < result.nodes
    without = search.Searcher(max_depth=1, quiescence=False).search(
        GameState.from_fen(kiwipete)
    )
    assert without.qnodes == 0
