"""Tests for the tactics suite (chess_ai/tactics.py).

The puzzle answers are re-derived here with exhaustive searches that only use
the (perft-verified) move generator, so the suite cannot silently contain a
wrong answer. The engine must solve every puzzle when given the depth the
puzzle needs; its solve rate under a time limit is reported by
`python -m chess_ai.tactics` (it depends on the machine, so it is not asserted).
"""

import json

import pytest

from chess_ai import search, tactics
from chess_ai.engine import GameState

VALUE = {"p": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
MATE = 1000


# --- exact forced-mate search -------------------------------------------------


def _mates_after(gs, move, n):
    """True if `move` forces mate in <= n moves."""
    gs.make_move(move)
    replies = gs.get_legal_moves()
    if not replies:
        result = gs.in_check()
    elif n == 1:
        result = False
    else:
        result = True
        for reply in replies:
            gs.make_move(reply)
            result = any(_mates_after(gs, m, n - 1) for m in gs.get_legal_moves())
            gs.undo_move()
            if not result:
                break
    gs.undo_move()
    return result


def mating_moves(gs, n):
    return {
        m.coordinate_notation() for m in gs.get_legal_moves() if _mates_after(gs, m, n)
    }


# --- material-only full-width search -------------------------------------------


def _material(gs):
    total = sum(
        VALUE[sq[1]] if sq[0] == "w" else -VALUE[sq[1]]
        for row in gs.board
        for sq in row
        if sq != "--"
    )
    return total if gs.white_to_move else -total


def _quiesce(gs, alpha, beta, ply):
    moves = gs.get_legal_moves()
    in_check = gs.in_check()
    if not moves:
        return -(MATE - ply) if in_check else 0
    best = -(10**9)
    if not in_check:  # stand pat, then only captures and promotions
        best = _material(gs)
        if best >= beta:
            return best
        alpha = max(alpha, best)
        moves = [m for m in moves if m.is_capture or m.is_promotion]
    for move in moves:
        gs.make_move(move)
        score = -_quiesce(gs, -beta, -alpha, ply + 1)
        gs.undo_move()
        best = max(best, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best


def _negamax(gs, depth, alpha, beta, ply):
    moves = gs.get_legal_moves()
    if not moves:
        return -(MATE - ply) if gs.in_check() else 0
    if depth == 0:
        return _quiesce(gs, alpha, beta, ply)
    best = -(10**9)
    for move in moves:
        gs.make_move(move)
        score = -_negamax(gs, depth - 1, -beta, -alpha, ply + 1)
        gs.undo_move()
        best = max(best, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best


def move_values(gs, depth=4):
    """Exact material value (side to move's view) of every root move."""
    values = {}
    for move in gs.get_legal_moves():
        gs.make_move(move)
        values[move.coordinate_notation()] = -_negamax(
            gs, depth - 1, -(10**9), 10**9, 1
        )
        gs.undo_move()
    return values


# --- tests --------------------------------------------------------------------


@pytest.mark.parametrize("puzzle", tactics.PUZZLES, ids=lambda p: p.name)
def test_puzzle_data_is_valid(puzzle):
    assert puzzle.kind in tactics.KINDS
    assert bool(puzzle.solutions) != bool(puzzle.avoid)  # exactly one of them
    legal = {
        m.coordinate_notation()
        for m in GameState.from_fen(puzzle.fen).get_legal_moves()
    }
    assert set(puzzle.solutions) <= legal
    assert set(puzzle.avoid) <= legal
    assert set(puzzle.avoid) != legal  # an avoid puzzle must be solvable


MATE_PUZZLES = [p for p in tactics.PUZZLES if p.kind.startswith("mate")]
MATERIAL_PUZZLES = [p for p in tactics.PUZZLES if p.kind in ("win", "avoid")]


@pytest.mark.parametrize("puzzle", MATE_PUZZLES, ids=lambda p: p.name)
def test_mate_solutions_are_exactly_the_forced_mates(puzzle):
    n = int(puzzle.kind[-1])
    gs = GameState.from_fen(puzzle.fen)
    assert set(puzzle.solutions) == mating_moves(gs, n)
    if n > 1:
        assert not mating_moves(gs, n - 1), "a shorter mate exists"


@pytest.mark.slow
@pytest.mark.parametrize("puzzle", MATERIAL_PUZZLES, ids=lambda p: p.name)
def test_material_answers_match_an_exhaustive_search(puzzle):
    gs = GameState.from_fen(puzzle.fen)
    values = move_values(gs)
    if puzzle.kind == "win":
        best = max(values.values())
        assert set(puzzle.solutions) == {m for m, v in values.items() if v == best}
        assert best - _material(gs) >= 3  # a real gain, not a pawn
    else:
        base = _material(gs)
        assert set(puzzle.avoid) == {m for m, v in values.items() if v <= base - 2}


def test_puzzle_is_solved_by():
    win = tactics.Puzzle("w", "win", "4k3/8/8/8/8/8/8/4K3 w - -", solutions=("e1e2",))
    avoid = tactics.Puzzle("a", "avoid", "4k3/8/8/8/8/8/8/4K3 w - -", avoid=("e1e2",))
    assert win.is_solved_by("e1e2") and not win.is_solved_by("e1d1")
    assert avoid.is_solved_by("e1d1") and not avoid.is_solved_by("e1e2")


def test_runner_reports_solve_rate(tmp_path, monkeypatch):
    easy = [p for p in tactics.PUZZLES if p.kind == "mate1"][:2]
    monkeypatch.setattr(tactics, "PUZZLES", easy)
    out = tmp_path / "tactics.json"

    assert tactics.main(["--depth", "1", "--json", str(out)]) == 0

    report = json.loads(out.read_text())
    assert report["summary"]["all"] == [2, 2]
    assert all(row["solved"] for row in report["results"])


# Plies a puzzle needs in principle: 2n - 1 for mate in n; for the others three
# plies, with the quiescence search playing out the exchanges.
REQUIRED_DEPTH = {"mate1": 1, "mate2": 3, "mate3": 5, "win": 3, "avoid": 3}


@pytest.mark.slow
@pytest.mark.parametrize("puzzle", tactics.PUZZLES, ids=lambda p: p.name)
def test_engine_solves_every_puzzle_at_its_required_depth(puzzle):
    """The Phase 6 strength threshold. A fixed depth (rather than a time
    limit) keeps the test independent of the machine's speed."""
    result = search.Searcher(max_depth=REQUIRED_DEPTH[puzzle.kind]).search(
        GameState.from_fen(puzzle.fen)
    )
    move = result.move.coordinate_notation()
    assert puzzle.is_solved_by(move), f"engine played {move}"
