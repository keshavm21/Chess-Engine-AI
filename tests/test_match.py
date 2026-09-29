"""Tests for the self-play match tool (chess_ai/match.py)."""

import json
import math

import pytest

from chess_ai import match
from chess_ai.engine import GameState


@pytest.mark.parametrize("opening", match.OPENINGS, ids=lambda o: o[0])
def test_openings_are_legal(opening):
    gs = match.opening_position(opening[1])
    assert len(gs.move_log) == len(opening[1].split())


def test_openings_are_distinct():
    fens = {match.opening_position(moves).to_fen() for _, moves in match.OPENINGS}
    assert len(fens) == len(match.OPENINGS)


def test_illegal_opening_is_rejected():
    with pytest.raises(ValueError):
        match.opening_position("e2e5")


def result_of(gs, plies=0, max_plies=200):
    if isinstance(gs, str):
        gs = GameState.from_fen(gs)
    return match.game_result(gs, gs.get_legal_moves(), plies, max_plies)


def test_game_result_rules(legal_move):
    assert result_of("3R2k1/5ppp/8/8/8/8/8/6K1 b - -") == ("1-0", "checkmate")
    assert result_of("7k/8/6QK/8/8/8/8/8 b - -") == ("1/2-1/2", "stalemate")
    assert result_of("4k3/8/8/8/8/8/8/4K3 w - -")[1] == "insufficient material"
    assert result_of("4k3/8/8/8/8/8/8/2B1K3 w - -")[1] == "insufficient material"
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
    assert result_of(start) is None
    assert result_of(start + " 100 60")[1] == "fifty-move rule"
    assert result_of(start, plies=200) == ("1/2-1/2", "move limit")
    gs = GameState()
    for _ in range(2):  # knights out and back twice: the start position again
        for move in ("g1f3", "g8f6", "f3g1", "f6g8"):
            gs.make_move(legal_move(gs, move))
    assert result_of(gs)[1] == "threefold repetition"


def test_move_limit_is_adjudicated_on_material():
    rook_up = "4k3/8/8/8/8/8/PPPP4/R3K3 w - -"
    assert result_of(rook_up, plies=200)[0] == "1-0"


def test_score_and_elo():
    assert match.score_for("a", {"result": "1-0", "white": "a", "black": "b"}) == 1
    assert match.score_for("a", {"result": "1-0", "white": "b", "black": "a"}) == 0
    assert (
        match.score_for("a", {"result": "1/2-1/2", "white": "b", "black": "a"}) == 0.5
    )
    assert match.elo_difference(0.5) == 0
    assert match.elo_difference(0.75) == pytest.approx(190.85, abs=0.01)
    assert match.elo_difference(1.0) == math.inf


def test_short_match_runs_and_scores_add_up(tmp_path):
    out = tmp_path / "match.json"
    assert (
        match.main(
            ["default", "depth-1", "--depth", "1", "--openings", "1",
             "--max-plies", "6", "--json", str(out)]
        )
        == 0
    )  # fmt: skip
    report = json.loads(out.read_text())
    games = report["games"]
    assert len(games) == 2
    assert {g["white"] for g in games} == {"default", "depth-1"}
    stats = report["summary"]
    assert stats["wins"] + stats["draws"] + stats["losses"] == 2
    assert all(g["plies"] <= 6 for g in games)
