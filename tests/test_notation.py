"""Tests for Move's coordinate notation (coordinate_notation), its short
notation (str(move)) and standard algebraic notation (GameState.san)."""

import random

import pytest

from chess_ai.engine import GameState

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


@pytest.mark.parametrize(
    ("fen", "coordinates", "short"),
    [
        pytest.param(STARTPOS, "e2e4", "e4", id="pawn-push"),
        pytest.param(STARTPOS, "g1f3", "Nf3", id="knight"),
        pytest.param("4k3/8/8/3p4/4P3/8/8/4K3 w - -", "e4d5", "exd5", id="capture"),
        pytest.param("4k3/8/8/8/8/8/8/4K2R w K -", "e1g1", "O-O", id="castle-short"),
        pytest.param("4k3/8/8/8/8/8/8/R3K3 w Q -", "e1c1", "O-O-O", id="castle-long"),
    ],
)
def test_notation_on_ranks_1_to_7(fen, coordinates, short, load_fen, legal_move):
    move = legal_move(load_fen(fen), coordinates)
    assert move.coordinate_notation() == coordinates
    assert str(move) == short


@pytest.mark.parametrize(
    ("fen", "coordinates", "short"),
    [
        pytest.param("8/7k/8/8/8/8/8/R3K3 w - -", "a1a8", "Ra8", id="rook-to-8"),
        pytest.param("4k3/8/6N1/8/8/8/8/4K3 w - -", "g6f8", "Nf8", id="knight-to-8"),
        pytest.param("4k3/8/8/8/8/8/8/4K3 b - -", "e8e7", "Ke7", id="king-from-8"),
    ],
)
def test_notation_on_rank_8(fen, coordinates, short, load_fen, legal_move):
    """Regression test for finding R2: rank 8 used to be written as "0"."""
    move = legal_move(load_fen(fen), coordinates)
    assert move.coordinate_notation() == coordinates
    assert str(move) == short


# ---------- Standard algebraic notation (SAN) ----------


@pytest.mark.parametrize(
    ("fen", "coordinates", "san"),
    [
        pytest.param(STARTPOS, "e2e4", "e4", id="pawn-push"),
        pytest.param(STARTPOS, "g1f3", "Nf3", id="knight"),
        pytest.param("4k3/8/8/3p4/4P3/8/8/4K3 w - -", "e4d5", "exd5", id="capture"),
        pytest.param("4k3/8/8/3pP3/8/8/8/4K3 w - d6", "e5d6", "exd6", id="en-passant"),
        pytest.param("5k2/8/8/8/8/8/8/4K2R w K -", "e1g1", "O-O+", id="castle-check"),
        pytest.param("4k3/8/8/8/8/8/8/R3K3 w Q -", "e1c1", "O-O-O", id="castle-long"),
        pytest.param("6k1/5ppp/8/8/8/8/8/R5K1 w - -", "a1a8", "Ra8#", id="mate"),
        pytest.param("k7/4P3/8/8/8/8/8/4K3 w - -", "e7e8q", "e8=Q+", id="promote-Q"),
        pytest.param("k7/4P3/8/8/8/8/8/4K3 w - -", "e7e8r", "e8=R+", id="promote-R"),
        pytest.param("k7/4P3/8/8/8/8/8/4K3 w - -", "e7e8b", "e8=B", id="promote-B"),
        pytest.param("k7/4P3/8/8/8/8/8/4K3 w - -", "e7e8n", "e8=N", id="promote-N"),
        pytest.param(
            "3rk3/4P3/8/8/8/8/8/4K3 w - -", "e7d8n", "exd8=N", id="capture-promote"
        ),
        pytest.param(
            "4k3/8/8/R7/8/8/8/R3K3 w - -", "a1a3", "R1a3", id="same-file-uses-rank"
        ),
        pytest.param(
            "4k3/8/8/8/8/8/8/R4RK1 w - -", "a1d1", "Rad1", id="same-rank-uses-file"
        ),
        pytest.param(
            "4k3/8/1Q6/8/8/8/1Q3Q2/7K w - -", "b2d4", "Qb2d4", id="file-and-rank"
        ),
        pytest.param(
            "4r1k1/8/8/8/8/2N1N3/8/4K3 w - -", "c3d5", "Nd5", id="pinned-rival"
        ),
        pytest.param("4k3/8/8/8/8/8/8/R3K2R w KQ -", "h1f1", "Rf1", id="one-rook-fits"),
    ],
)
def test_san(fen, coordinates, san, load_fen, legal_move):
    gs = load_fen(fen)
    assert gs.san(legal_move(gs, coordinates)) == san


def test_san_of_a_complete_game(legal_move):
    """Morphy's "Opera Game" (Paris, 1858), compared with its published score."""
    coordinates = (
        "e2e4 e7e5 g1f3 d7d6 d2d4 c8g4 d4e5 g4f3 d1f3 d6e5 f1c4 g8f6 "
        "f3b3 d8e7 b1c3 c7c6 c1g5 b7b5 c3b5 c6b5 c4b5 b8d7 e1c1 a8d8 "
        "d1d7 d8d7 h1d1 e7e6 b5d7 f6d7 b3b8 d7b8 d1d8"
    ).split()
    published = (
        "e4 e5 Nf3 d6 d4 Bg4 dxe5 Bxf3 Qxf3 dxe5 Bc4 Nf6 "
        "Qb3 Qe7 Nc3 c6 Bg5 b5 Nxb5 cxb5 Bxb5+ Nbd7 O-O-O Rd8 "
        "Rxd7 Rxd7 Rd1 Qe6 Bxd7+ Nxd7 Qb8+ Nxb8 Rd8#"
    ).split()
    gs = GameState()
    written = []
    for move_text in coordinates:
        move = legal_move(gs, move_text)
        written.append(gs.san(move))
        gs.make_move(move)
    assert written == published


def test_san_is_unambiguous_and_leaves_the_position_unchanged(state_snapshot):
    """In random positions every legal move gets its own SAN, and asking for it
    changes nothing, including the game-over flags."""
    rng = random.Random(8)
    starts = [
        STARTPOS,
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -",
        "4k3/8/8/1N3N2/8/1N3N2/8/4K3 w - -",  # four knights around d4
    ]
    for _ in range(150):
        gs = GameState.from_fen(rng.choice(starts))
        for _ in range(rng.randint(0, 30)):
            moves = gs.get_legal_moves()
            if not moves:
                break
            gs.make_move(rng.choice(moves))
        moves = gs.get_legal_moves()
        gs.update_game_status(moves)
        before = state_snapshot(gs), gs.checkmate, gs.stalemate, gs.draw_reason
        written = [gs.san(move, moves) for move in moves]
        assert len(set(written)) == len(written), (gs.to_fen(), written)
        after = state_snapshot(gs), gs.checkmate, gs.stalemate, gs.draw_reason
        assert after == before


def test_san_keeps_a_draw_that_was_already_declared(legal_move):
    gs = GameState.from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 100 80")
    gs.update_game_status()
    assert gs.draw_reason == "fifty-move rule"
    gs.san(legal_move(gs, "a1a2"))
    assert gs.draw_reason == "fifty-move rule"
