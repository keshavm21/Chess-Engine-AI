"""Tests for attack detection (GameState.is_attacked_by / is_square_attacked)
and the castling rules that depend on it."""

import random

import pytest

from chess_ai.engine import GameState

KNIGHT_JUMPS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KING_STEPS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
ROOK_RAYS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
BISHOP_RAYS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def reference_attacks(board, white):
    """Squares attacked by one side, computed piece by piece from the rules
    (independently of the engine's scan-from-the-target implementation)."""
    color = "w" if white else "b"
    attacked = set()

    def on_board(r, c):
        return 0 <= r < 8 and 0 <= c < 8

    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece[0] != color:
                continue
            kind = piece[1]
            if kind == "p":
                forward = -1 if white else 1
                steps = [(forward, -1), (forward, 1)]
            elif kind == "N":
                steps = KNIGHT_JUMPS
            elif kind == "K":
                steps = KING_STEPS
            else:
                steps = []
            for dr, dc in steps:
                if on_board(r + dr, c + dc):
                    attacked.add((r + dr, c + dc))

            rays = {"R": ROOK_RAYS, "B": BISHOP_RAYS, "Q": ROOK_RAYS + BISHOP_RAYS}
            for dr, dc in rays.get(kind, []):
                rr, cc = r + dr, c + dc
                while on_board(rr, cc):
                    attacked.add((rr, cc))
                    if board[rr][cc] != "--":
                        break
                    rr, cc = rr + dr, cc + dc
    return attacked


def random_positions(count, seed):
    """Positions reached by random play from a mix of standard positions."""
    starts = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -",
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -",
    ]
    rng = random.Random(seed)
    positions = []
    while len(positions) < count:
        gs = GameState.from_fen(rng.choice(starts))
        for _ in range(rng.randint(0, 40)):
            moves = gs.get_legal_moves()
            if not moves:
                break
            gs.make_move(rng.choice(moves))
        positions.append(gs)
    return positions


def test_attack_detection_matches_reference_on_random_positions():
    for gs in random_positions(300, seed=2026):
        for white in (True, False):
            expected = reference_attacks(gs.board, white)
            for r in range(8):
                for c in range(8):
                    assert gs.is_attacked_by(r, c, white) == ((r, c) in expected), (
                        f"{gs.to_fen()}: square {(r, c)} attacked by "
                        f"{'White' if white else 'Black'} should be {(r, c) in expected}"
                    )


def test_is_square_attacked_means_attacked_by_the_side_not_to_move(load_fen):
    gs = load_fen(
        "4k3/8/8/8/8/8/8/R3K3 w Q -"
    )  # the rook attacks the a-file and rank 1
    assert gs.is_square_attacked(0, 0) is False  # White to move: asks about Black
    gs.white_to_move = False
    assert gs.is_square_attacked(0, 0) is True


@pytest.mark.parametrize(
    ("fen", "illegal_castles"),
    [
        pytest.param("4k3/8/8/8/8/8/4p3/R3K2R w KQ -", {"e1g1", "e1c1"}, id="pawn-e2"),
        pytest.param("4k3/8/8/8/8/8/7p/4K2R w K -", {"e1g1"}, id="pawn-h2"),
        pytest.param("4k3/8/8/8/8/8/1p6/R3K3 w Q -", {"e1c1"}, id="pawn-b2"),
        pytest.param("r3k2r/4P3/8/8/8/8/8/4K3 b kq -", {"e8g8", "e8c8"}, id="pawn-e7"),
    ],
)
def test_cannot_castle_through_a_square_attacked_by_a_pawn(
    fen, illegal_castles, load_fen
):
    """Regression test for finding R7: attacks on empty squares by pawns were
    not seen, so the king could castle through a pawn-attacked square."""
    castles = {m.coordinate_notation() for m in load_fen(fen).get_legal_moves()}
    assert not castles & illegal_castles


def test_queenside_castling_may_pass_an_attacked_b_file_square(load_fen):
    """Control case: only the squares the king crosses must be safe, so a pawn
    attacking b1 does not prevent O-O-O."""
    castles = [m for m in load_fen("4k3/8/8/8/8/8/p7/R3K3 w Q -").get_legal_moves()]
    assert "e1c1" in {m.coordinate_notation() for m in castles if m.is_castle}
