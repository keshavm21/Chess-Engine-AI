"""
Perft (PERFormance Test) suite for the move generation in chess_ai/engine.py.

perft(depth) counts the total number of legal move sequences (leaf nodes)
reachable in exactly `depth` half-moves from a given position. It is the
standard way to validate a chess move generator: the correct counts for
many positions are published and well known, so a mismatch pinpoints a
real bug in move generation, check detection, castling, en passant, or
the make_move/undo_move pair -- not a matter of opinion or tuning.

This suite also folds in a state-corruption check: after every
make_move()/undo_move() pair explored during the count, it checks that the
GameState is identical to what it was before the move was made (board
contents, side to move, castling rights, en-passant square, king
locations, move-log length). A wrong final count tells you *that*
something is broken; this tells you *which move, at which depth* broke
it, without a second pass over the tree.

Positions used
--------------
- The standard starting position.
- "Kiwipete", a well-known perft stress position with both-side castling,
  en passant, and pins.
- A small custom position (4k3/8/8/8/8/8/5n2/4K2R b K -) where a lone
  black knight can capture White's only rook in one move. The castling
  generator only checks castling rights and empty squares -- it never
  checks that a rook is still on the corner -- so _update_castling_rights()
  revoking rights the instant a rook is captured is load-bearing. The
  other positions never capture a rook within a few plies, so this one
  covers it. Its expected counts were computed independently with the
  python-chess library, not with this codebase.
- Chess Programming Wiki perft positions 3, 4 and 5
  (https://www.chessprogramming.org/Perft_Results). Position 3 stresses
  en passant with discovered checks along the rank; positions 4 and 5
  contain promotions.

Promotions: positions 4 and 5 contain promotions, including
underpromotions, so they also check that all four promotion pieces are
generated and that make/undo handles them. (Before Phase 3 the engine only
promoted to a queen and these cases were strict xfails.)

Run with:
    pytest tests/test_perft.py              # everything (~30s)
    pytest tests/test_perft.py -m "not slow" # skips the deep cases (~3s)
"""

import pytest

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -"
# A black knight on f2 can play Nxh1, capturing White's only rook, one
# move away from White's (otherwise legal-looking) kingside castle.
ROOK_CAPTURE = "4k3/8/8/8/8/8/5n2/4K2R b K -"
POSITION_3 = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -"
POSITION_4 = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -"
POSITION_5 = "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -"

SLOW = pytest.mark.slow

PERFT_CASES = [
    pytest.param(STARTPOS, 1, 20, id="startpos-d1"),
    pytest.param(STARTPOS, 2, 400, id="startpos-d2"),
    pytest.param(STARTPOS, 3, 8902, id="startpos-d3"),
    pytest.param(STARTPOS, 4, 197281, id="startpos-d4", marks=SLOW),
    pytest.param(KIWIPETE, 1, 48, id="kiwipete-d1"),
    pytest.param(KIWIPETE, 2, 2039, id="kiwipete-d2"),
    pytest.param(KIWIPETE, 3, 97862, id="kiwipete-d3", marks=SLOW),
    pytest.param(ROOK_CAPTURE, 1, 11, id="rook_capture-d1"),
    pytest.param(ROOK_CAPTURE, 2, 127, id="rook_capture-d2"),
    pytest.param(ROOK_CAPTURE, 3, 1319, id="rook_capture-d3"),
    pytest.param(POSITION_3, 1, 14, id="position3-d1"),
    pytest.param(POSITION_3, 2, 191, id="position3-d2"),
    pytest.param(POSITION_3, 3, 2812, id="position3-d3"),
    pytest.param(POSITION_3, 4, 43238, id="position3-d4", marks=SLOW),
    pytest.param(POSITION_4, 1, 6, id="position4-d1"),
    pytest.param(POSITION_4, 2, 264, id="position4-d2"),
    pytest.param(POSITION_4, 3, 9467, id="position4-d3"),
    pytest.param(POSITION_4, 4, 422333, id="position4-d4", marks=SLOW),
    pytest.param(POSITION_5, 1, 44, id="position5-d1"),
    pytest.param(POSITION_5, 2, 1486, id="position5-d2"),
    pytest.param(POSITION_5, 3, 62379, id="position5-d3", marks=SLOW),
]


def perft(gs, depth, snapshot):
    """Count leaf nodes at `depth` half-moves, checking along the way that
    every undo_move() exactly restores the state that existed before its
    matching make_move() -- catching state corruption, not just a wrong
    final count."""
    if depth == 0:
        return 1

    moves = gs.get_legal_moves()
    if depth == 1:
        return len(moves)

    nodes = 0
    for move in moves:
        before = snapshot(gs)
        gs.make_move(move)
        nodes += perft(gs, depth - 1, snapshot)
        gs.undo_move()
        if snapshot(gs) != before:
            pytest.fail(
                f"undo_move() did not fully restore state after "
                f"{move.coordinate_notation()} (depth {depth})"
            )
    return nodes


@pytest.mark.parametrize(("fen", "depth", "expected"), PERFT_CASES)
def test_perft(fen, depth, expected, load_fen, state_snapshot):
    gs = load_fen(fen)
    assert perft(gs, depth, state_snapshot) == expected
