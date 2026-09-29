"""Tests for the draw rules: fifty-move rule, repetition, insufficient material."""

import pytest

from chess_ai.engine import GameState


def play(gs, legal_move, *moves):
    for coordinates in moves:
        gs.make_move(legal_move(gs, coordinates))


def test_halfmove_clock_counts_quiet_moves_and_resets(legal_move):
    gs = GameState()
    play(gs, legal_move, "g1f3", "g8f6")
    assert gs.halfmove_clock == 2
    play(gs, legal_move, "e2e4")  # pawn move
    assert gs.halfmove_clock == 0
    play(gs, legal_move, "f6e4")  # capture
    assert gs.halfmove_clock == 0
    play(gs, legal_move, "b1c3")
    assert gs.halfmove_clock == 1
    gs.undo_move()
    gs.undo_move()
    assert gs.halfmove_clock == 0
    gs.undo_move()
    assert gs.halfmove_clock == 2


def test_move_number_grows_after_blacks_move(legal_move):
    gs = GameState()
    play(gs, legal_move, "e2e4")
    assert gs.fullmove_number == 1
    play(gs, legal_move, "e7e5")
    assert gs.fullmove_number == 2
    gs.undo_move()
    assert gs.fullmove_number == 1


def test_threefold_repetition(legal_move):
    gs = GameState()
    shuffle = ("g1f3", "g8f6", "f3g1", "f6g8")
    play(gs, legal_move, *shuffle)
    assert gs.repetition_count() == 2
    assert gs.draw_by_rule() is None
    play(gs, legal_move, *shuffle)
    assert gs.repetition_count() == 3
    assert gs.draw_by_rule() == "threefold repetition"
    gs.update_game_status()
    assert gs.draw_reason == "threefold repetition"
    gs.undo_move()
    assert gs.draw_reason is None  # undo clears it


def test_a_pawn_move_ends_the_repetition_history(legal_move):
    gs = GameState()
    play(gs, legal_move, "g1f3", "g8f6", "f3g1", "f6g8")
    play(gs, legal_move, "e2e3", "e7e6")  # irreversible
    play(gs, legal_move, "g1f3", "g8f6", "f3g1", "f6g8")
    assert gs.repetition_count() == 2  # the first shuffle no longer counts


def test_lost_castling_rights_make_a_different_position(legal_move):
    gs = GameState.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq -")
    play(gs, legal_move, "e1f1", "e8f8", "f1e1", "f8e8")  # kings back, rights gone
    assert gs.board == GameState.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w - -").board
    assert gs.repetition_count() == 1


@pytest.mark.parametrize(
    ("fen", "insufficient"),
    [
        ("4k3/8/8/8/8/8/8/4K3 w - -", True),  # K v K
        ("4k3/8/8/8/8/8/8/3NK3 w - -", True),  # K + N v K
        ("4k3/8/8/8/8/8/8/3BK3 w - -", True),  # K + B v K
        ("4k3/8/8/8/8/8/8/3bKB2 w - -", True),  # d1, f1: same-coloured bishops
        ("4k3/8/8/8/8/8/8/2b1KB2 w - -", False),  # c1, f1: different colours
        ("4k3/8/8/8/8/8/8/2NNK3 w - -", False),  # two knights: mate is possible
        ("4k3/8/8/8/8/8/4P3/4K3 w - -", False),  # a pawn can promote
        ("4k3/8/8/8/8/8/8/3RK3 w - -", False),
    ],
)
def test_insufficient_material(fen, insufficient):
    gs = GameState.from_fen(fen)
    assert gs.is_insufficient_material() is insufficient
    assert (gs.draw_by_rule() == "insufficient material") is insufficient


def test_fifty_move_rule(legal_move):
    gs = GameState.from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 99 80")
    assert gs.draw_by_rule() is None
    play(gs, legal_move, "a1a2")
    assert gs.halfmove_clock == 100
    assert gs.draw_by_rule() == "fifty-move rule"


def test_checkmate_takes_precedence_over_the_fifty_move_rule(legal_move):
    gs = GameState.from_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - - 99 80")
    play(gs, legal_move, "a1a8")  # checkmate on the 100th quiet ply
    gs.update_game_status()
    assert gs.checkmate is True
    assert gs.draw_reason is None


def test_repetition_whose_first_occurrence_follows_a_two_square_pawn_move(legal_move):
    """After 1.e4 no black pawn can take en passant, so the position after 1.e4
    recurs after each knight shuffle: the third time (ply 9) is a draw.
    Before the fix the en-passant square made the first occurrence look
    different, so this position alone would only have been drawn at its fourth
    occurrence (here the draw came one ply late, through another position)."""
    gs = GameState()
    play(gs, legal_move, "e2e4")
    for _ in range(2):
        play(gs, legal_move, "g8f6", "g1f3", "f6g8", "f3g1")
    assert len(gs.move_log) == 9
    assert gs.repetition_count() == 3
    assert gs.draw_by_rule() == "threefold repetition"
