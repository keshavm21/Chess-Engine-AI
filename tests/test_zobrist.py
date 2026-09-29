"""Tests for the incrementally updated Zobrist position key."""

import random

from chess_ai.engine import GameState

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


def play(gs, legal_move, *moves):
    for coordinates in moves:
        gs.make_move(legal_move(gs, coordinates))


def test_incremental_key_matches_a_full_recomputation():
    """After every move (castling, en passant and promotions included) and
    every undo, the incrementally updated key equals one computed from scratch."""
    starts = [
        START,
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -",
    ]
    rng = random.Random(9)
    for _ in range(150):
        gs = GameState.from_fen(rng.choice(starts))
        keys = [gs.zobrist_key]
        for _ in range(rng.randint(1, 40)):
            moves = gs.get_legal_moves()
            if not moves:
                break
            gs.make_move(rng.choice(moves))
            assert gs.zobrist_key == gs.compute_zobrist_key(), gs.to_fen()
            keys.append(gs.zobrist_key)
        while gs.move_log:
            gs.undo_move()
            keys.pop()
            assert gs.zobrist_key == keys[-1] == gs.compute_zobrist_key()


def test_same_position_by_different_move_orders_has_the_same_key(legal_move):
    first, second = GameState(), GameState()
    play(first, legal_move, "g1f3", "g8f6", "b1c3", "b8c6")
    play(second, legal_move, "b1c3", "b8c6", "g1f3", "g8f6")
    assert first.zobrist_key == second.zobrist_key
    assert first.zobrist_key != GameState().zobrist_key


def test_start_position_key_is_reproducible():
    assert GameState().zobrist_key == GameState.from_fen(START).zobrist_key


def test_side_to_move_castling_and_en_passant_change_the_key():
    base = GameState.from_fen("r3k2r/8/8/3pP3/8/8/8/R3K2R w KQkq d6").zobrist_key
    variants = [
        "r3k2r/8/8/3pP3/8/8/8/R3K2R b KQkq d6",  # side to move
        "r3k2r/8/8/3pP3/8/8/8/R3K2R w Qkq d6",  # one castling right fewer
        "r3k2r/8/8/3pP3/8/8/8/R3K2R w KQkq -",  # no en-passant square
    ]
    keys = {GameState.from_fen(fen).zobrist_key for fen in variants}
    assert base not in keys and len(keys) == 3


def test_undo_restores_the_key_and_the_history(legal_move):
    gs = GameState()
    play(gs, legal_move, "e2e4", "e7e5")
    assert len(gs.zobrist_log) == 3  # start, after e4, after e5
    gs.undo_move()
    gs.undo_move()
    assert gs.zobrist_log == [GameState().zobrist_key]
    assert gs.zobrist_key == GameState().zobrist_key


def test_an_unusable_en_passant_square_does_not_change_the_key():
    """Only an en-passant capture that is really possible makes a position
    different (FIDE 9.2.3)."""
    none = GameState.from_fen("4k3/8/8/8/3P4/8/8/4K3 b - -").zobrist_key
    unusable = GameState.from_fen("4k3/8/8/8/3P4/8/8/4K3 b - d3").zobrist_key
    assert unusable == none
    # A pawn next to it, but taking en passant would expose its king on the rank.
    pinned_none = GameState.from_fen("8/8/8/8/k2Pp2R/8/8/4K3 b - -").zobrist_key
    pinned = GameState.from_fen("8/8/8/8/k2Pp2R/8/8/4K3 b - d3").zobrist_key
    assert pinned == pinned_none
    # A capture that is possible still counts.
    usable_none = GameState.from_fen("4k3/8/8/8/3Pp3/8/8/4K3 b - -").zobrist_key
    usable = GameState.from_fen("4k3/8/8/8/3Pp3/8/8/4K3 b - d3").zobrist_key
    assert usable != usable_none
