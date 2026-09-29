"""Tests for GameState.from_fen() and GameState.to_fen()."""

import pytest

from chess_ai.engine import STARTING_FEN, GameState

ROUND_TRIP_FENS = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
    "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 12",
    "4k3/8/8/8/3P4/8/2P1P3/4K3 b - d3 0 31",
    "8/8/4k3/8/8/4K3/8/7R w - - 57 90",
]


@pytest.mark.parametrize("fen", ROUND_TRIP_FENS)
def test_round_trip(fen):
    assert GameState.from_fen(fen).to_fen() == fen


def test_move_counters_are_read_and_default_to_0_and_1():
    gs = GameState.from_fen("8/8/4k3/8/8/4K3/8/7R b - - 57 90")
    assert (gs.halfmove_clock, gs.fullmove_number) == (57, 90)
    short = GameState.from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -")
    assert (short.halfmove_clock, short.fullmove_number) == (0, 1)
    assert short.to_fen() == STARTING_FEN


def test_starting_fen_matches_the_default_game_state(state_snapshot):
    assert state_snapshot(GameState.from_fen(STARTING_FEN)) == state_snapshot(
        GameState()
    )


def test_position_details_are_loaded():
    gs = GameState.from_fen("r3k2r/8/8/3pP3/8/8/8/R3K2R w Kq d6")
    assert gs.white_to_move is True
    assert gs.board[0][0] == "bR" and gs.board[3][4] == "wp"
    assert gs.white_king_location == (7, 4) and gs.black_king_location == (0, 4)
    rights = gs.castling_rights
    assert (rights.wks, rights.wqs, rights.bks, rights.bqs) == (
        True,
        False,
        False,
        True,
    )
    assert gs.en_passant_square == (2, 3)
    assert gs.en_passant_log == [(2, 3)] and len(gs.castling_rights_log) == 1


def test_to_fen_follows_make_and_undo(legal_move):
    gs = GameState()
    gs.make_move(legal_move(gs, "e2e4"))
    assert gs.to_fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    gs.make_move(legal_move(gs, "e7e5"))
    gs.make_move(legal_move(gs, "e1e2"))
    assert gs.to_fen() == "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPPKPPP/RNBQ1BNR b kq - 1 2"
    gs.undo_move()
    gs.undo_move()
    gs.undo_move()
    assert gs.to_fen() == STARTING_FEN


@pytest.mark.parametrize(
    "fen",
    [
        pytest.param("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq -", id="7-ranks"),
        pytest.param(
            "rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -", id="9-squares"
        ),
        pytest.param(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNX w KQkq -", id="bad-piece"
        ),
        pytest.param(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq -", id="bad-side"
        ),
        pytest.param(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQxq -", id="bad-castle"
        ),
        pytest.param(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq e4", id="bad-ep"
        ),
        pytest.param(
            "rnbq1bnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -", id="no-king"
        ),
        pytest.param("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w", id="3-fields"),
        pytest.param(STARTING_FEN + " 7", id="7-fields"),
        pytest.param(STARTING_FEN.replace(" 0 1", " -1 1"), id="negative-clock"),
        pytest.param(STARTING_FEN.replace(" 0 1", " 0 0"), id="move-number-0"),
        pytest.param(STARTING_FEN.replace(" 0 1", " x 1"), id="not-a-number"),
    ],
)
def test_malformed_fen_is_rejected(fen):
    with pytest.raises(ValueError):
        GameState.from_fen(fen)
