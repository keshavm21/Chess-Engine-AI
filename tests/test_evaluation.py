"""Tests for the static evaluation (chess_ai/evaluation.py)."""

import random

import pytest

from chess_ai import evaluation
from chess_ai.engine import GameState
from chess_ai.evaluation import CHECKMATE, TEMPO, evaluate

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


def mirror(fen):
    """The same position with the colours swapped (board flipped vertically)."""
    placement, side, castling, ep = fen.split()[:4]
    placement = "/".join(rank.swapcase() for rank in reversed(placement.split("/")))
    side = "b" if side == "w" else "w"
    if castling != "-":
        castling = "".join(sorted(castling.swapcase(), key="KQkq".index))
    if ep != "-":
        ep = ep[0] + str(9 - int(ep[1]))
    return f"{placement} {side} {castling} {ep}"


def random_positions(count, seed):
    rng = random.Random(seed)
    starts = [
        START,
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -",
        "r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ -",
    ]
    positions = []
    while len(positions) < count:
        gs = GameState.from_fen(rng.choice(starts))
        for _ in range(rng.randint(0, 80)):
            moves = gs.get_legal_moves()
            if not moves:
                break
            gs.make_move(rng.choice(moves))
        positions.append(gs.to_fen())
    return positions


def score(fen):
    return evaluate(GameState.from_fen(fen))


def test_start_position_is_level_apart_from_the_tempo_bonus():
    assert score(START) == TEMPO
    assert score(START.replace(" w ", " b ")) == -TEMPO


def test_evaluation_is_an_integer():
    assert isinstance(score(START), int)


def test_colour_mirrored_positions_score_exactly_opposite():
    for fen in random_positions(300, seed=6):
        assert score(mirror(fen)) == -score(fen), fen


def test_evaluation_does_not_change_the_position(state_snapshot):
    for fen in random_positions(20, seed=7):
        gs = GameState.from_fen(fen)
        before = state_snapshot(gs)
        evaluate(gs)
        assert state_snapshot(gs) == before
        assert not hasattr(gs, "_attack_cache")


def test_game_over_flags_are_honoured():
    gs = GameState.from_fen(START)
    gs.checkmate = True
    assert evaluate(gs) == -CHECKMATE  # White to move and mated
    gs.white_to_move = False
    assert evaluate(gs) == CHECKMATE
    gs.checkmate, gs.stalemate = False, True
    assert evaluate(gs) == 0


def test_an_extra_queen_is_worth_a_queen():
    without_black_queen = START.replace("rnbqkbnr", "rnb1kbnr")
    assert 800 < score(without_black_queen) - score(START) < 1000


@pytest.mark.parametrize("piece", ["P", "N", "B", "R", "Q"])
def test_material_counts(piece):
    fen = f"4k3/8/8/8/3{piece}4/8/8/4K3 w - -"
    assert score(fen) > score("4k3/8/8/8/8/8/8/4K3 w - -")


def test_a_passed_pawn_is_better_than_a_blocked_one():
    # The black pawn on d7 stops White's e6 pawn from being passed; on a7 it
    # does not.
    passed = score("4k3/p7/4P3/8/8/8/8/4K3 w - -")
    not_passed = score("4k3/3p4/4P3/8/8/8/8/4K3 w - -")
    assert passed > not_passed


def test_passed_pawns_gain_value_as_they_advance():
    values = [
        score("k7/8/8/4P3/8/8/8/K7 w - -"),
        score("k7/8/4P3/8/8/8/8/K7 w - -"),
        score("k7/4P3/8/8/8/8/8/K7 w - -"),
    ]
    assert values[0] < values[1] < values[2]


def test_doubled_isolated_pawns_are_worse_than_connected_ones():
    healthy = score("4k3/8/8/8/8/8/3PP3/4K3 w - -")
    doubled = score("4k3/8/8/8/8/4P3/4P3/4K3 w - -")
    assert healthy > doubled


def test_a_rook_likes_an_open_file():
    open_file = score("4k3/8/8/8/8/8/P7/3RK3 w - -")
    closed_file = score("4k3/8/8/8/8/8/3P4/3RK3 w - -")
    assert open_file > closed_file


def test_pawn_shield():
    shield = evaluation._pawn_shield
    board = GameState.from_fen("4k3/8/8/8/8/8/5PPP/6K1 w - -").board
    assert shield(board, (7, 6), "w") == 3 * evaluation.SHIELD_PAWN[0]
    board = GameState.from_fen("4k3/8/8/8/8/5PPP/8/6K1 w - -").board
    assert shield(board, (7, 6), "w") == 3 * evaluation.SHIELD_PAWN[1]
    board = GameState.from_fen("4k3/8/8/8/4K3/8/5PPP/8 w - -").board
    assert shield(board, (4, 4), "w") == 0  # the king has left its home ranks


def test_the_king_centralises_in_the_endgame():
    centre = score("4k3/8/8/8/4K3/8/P7/8 w - -")
    corner = score("4k3/8/8/8/8/8/P7/K7 w - -")
    assert centre > corner


def test_the_king_stays_home_in_the_middlegame():
    castled = score("r2qk2r/pppppppp/8/8/8/8/PPPPPPPP/R2Q1RK1 w kq -")
    wandering = score("r2qk2r/pppppppp/8/8/4K3/8/PPPPPPPP/R2Q1R2 w kq -")
    assert castled > wandering
