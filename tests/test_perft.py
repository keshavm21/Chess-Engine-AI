"""
Perft (PERFormance Test) suite for chessEngine.py's move generation.

perft(depth) counts the total number of legal move sequences (leaf nodes)
reachable in exactly `depth` half-moves from a given position. It is the
standard way to validate a chess move generator: the correct counts for
many positions are published and well known, so a mismatch pinpoints a
real bug in move generation, check detection, castling, en passant, or
the makeMove/undoMove pair -- not a matter of opinion or tuning.

This suite also folds in a state-corruption check: after every
makeMove()/undoMove() pair explored during the count, it asserts that the
GameState is byte-for-byte identical to what it was before the move was
made (board contents, side to move, castling rights, en-passant square,
king locations, move-log length). A wrong final count tells you *that*
something is broken; this tells you *which move, at which depth* broke
it, without a second pass over the tree.

Positions used
--------------
1. The standard starting position, depths 1-4.
2. "Kiwipete" (r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R
   w KQkq -), a well-known perft stress position with both-side castling,
   en passant, and pins, depths 1-3.
3. A small custom position (4k3/8/8/8/8/8/5n2/4K2R b K -) where a lone
   black knight can capture White's only rook in one move. This targets
   a specific rule this codebase's castling-move generator relies on but
   does not itself verify: getKingSideCastleMoves()/getQueenSideCastleMoves()
   only check currentCastlingRights and that the in-between squares are
   empty -- they never check that a rook is actually still sitting on the
   corner square. That makes updateCastlRights() correctly revoking
   rights the instant a rook is captured load-bearing; if it doesn't, the
   engine can still "castle" with whatever piece now occupies that
   corner. The starting position and Kiwipete, at the depths used here,
   never get far enough to expose this (no rook is captured within a few
   plies from either), so this position is included specifically to
   cover it. Its expected counts were computed independently with the
   python-chess library, not with this codebase, to avoid validating the
   engine against itself.

All three positions are promotion-free at these depths (a pawn needs at least
5 plies to reach the back rank from the start position, and Kiwipete's
own published stats show zero promotions through depth 3). That's
deliberate: chessEngine.py's makeMove() always auto-queens and never
generates underpromotion moves, so any position/depth where promotions
occur will not match the standard published counts -- that's a known,
already-documented limitation (see the engineering audit), not something
this suite is trying to catch. Extending this suite to deeper depths on
these positions, or to other standard positions with promotions, will
require accounting for that separately.

Run with:
    python3 tests/test_perft.py            # full suite (~12s)
    python3 tests/test_perft.py --fast      # skips the two slowest cases (~0.4s)
"""

import argparse
import os
import sys
import time

# Make sure the repo root (one level up from this file) is importable,
# regardless of the working directory this script is run from.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import chessEngine


STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -"
# A black knight on f2 can play Nxh1, capturing White's only rook, one
# move away from White's (otherwise legal-looking) kingside castle.
ROOK_CAPTURE = "4k3/8/8/8/8/8/5n2/4K2R b K -"

# (name, fen, depth, expected node count, is this one of the slow cases?)
PERFT_CASES = [
    ("startpos",     STARTPOS,     1, 20,      False),
    ("startpos",     STARTPOS,     2, 400,     False),
    ("startpos",     STARTPOS,     3, 8902,    False),
    ("startpos",     STARTPOS,     4, 197281,  True),
    ("kiwipete",     KIWIPETE,     1, 48,      False),
    ("kiwipete",     KIWIPETE,     2, 2039,    False),
    ("kiwipete",     KIWIPETE,     3, 97862,   True),
    ("rook_capture", ROOK_CAPTURE, 1, 11,      False),
    ("rook_capture", ROOK_CAPTURE, 2, 127,     False),
    ("rook_capture", ROOK_CAPTURE, 3, 1319,    False),
]


def set_position_from_fen(gs, fen):
    """Configure an existing GameState to match a FEN position. Only the
    fields chessEngine.GameState actually tracks are set (board, side to
    move, castling rights, en-passant square); the halfmove clock and
    fullmove number in a full FEN are ignored, since this engine doesn't
    implement the fifty-move rule or move numbering."""
    placement, side, castling, ep = fen.split()[:4]

    piece_map = {
        "p": "bp", "n": "bN", "b": "bB", "r": "bR", "q": "bQ", "k": "bK",
        "P": "wp", "N": "wN", "B": "wB", "R": "wR", "Q": "wQ", "K": "wK",
    }

    board = []
    for row in placement.split("/"):
        board_row = []
        for ch in row:
            if ch.isdigit():
                board_row.extend(["--"] * int(ch))
            else:
                board_row.append(piece_map[ch])
        board.append(board_row)
    gs.board = board

    gs.whiteToMove = (side == "w")

    gs.currentCastlingRights = chessEngine.CastleRights(
        "K" in castling, "k" in castling, "Q" in castling, "q" in castling,
    )
    gs.castleRightLog = [chessEngine.CastleRights(
        gs.currentCastlingRights.wks, gs.currentCastlingRights.bks,
        gs.currentCastlingRights.wqs, gs.currentCastlingRights.bqs,
    )]

    if ep == "-":
        gs.enpassantPossible = ()
    else:
        col = chessEngine.Move.fileToCols[ep[0]]
        row = chessEngine.Move.ranksToRows[ep[1]]
        gs.enpassantPossible = (row, col)
    gs.enpassantPossibleLog = [gs.enpassantPossible]

    gs.moveLog = []

    for r in range(8):
        for c in range(8):
            if gs.board[r][c] == "wK":
                gs.whiteKingLocation = (r, c)
            elif gs.board[r][c] == "bK":
                gs.blackKingLocation = (r, c)

    gs.checkmate = False
    gs.stalemate = False
    return gs


def _snapshot(gs):
    """A comparable, immutable snapshot of everything makeMove()/undoMove()
    touch. Two snapshots being equal means the state is truly identical,
    not just "the board looks the same"."""
    cr = gs.currentCastlingRights
    return (
        tuple(tuple(row) for row in gs.board),
        gs.whiteToMove,
        (cr.wks, cr.bks, cr.wqs, cr.bqs),
        gs.enpassantPossible,
        gs.whiteKingLocation,
        gs.blackKingLocation,
        len(gs.moveLog),
    )


def perft(gs, depth):
    """Count leaf nodes at `depth` half-moves, asserting along the way that
    every undoMove() exactly restores the state that existed before its
    matching makeMove() -- catching state corruption, not just a wrong
    final count."""
    if depth == 0:
        return 1

    moves = gs.getValidMoves()
    if depth == 1:
        return len(moves)

    nodes = 0
    for move in moves:
        before = _snapshot(gs)
        gs.makeMove(move)
        nodes += perft(gs, depth - 1)
        gs.undoMove()
        after = _snapshot(gs)
        assert after == before, (
            f"undoMove() did not fully restore state after "
            f"{move.getChessNotation()} (depth {depth})"
        )
    return nodes


def run_case(name, fen, depth, expected):
    gs = chessEngine.GameState()
    set_position_from_fen(gs, fen)

    t0 = time.time()
    try:
        actual = perft(gs, depth)
    except AssertionError as e:
        elapsed = time.time() - t0
        print(f"FAILED  {name:<10} depth {depth}  ({elapsed:.2f}s)  {e}")
        return False
    elapsed = time.time() - t0

    passed = actual == expected
    status = "PASSED" if passed else "FAILED"
    print(
        f"{status}  {name:<10} depth {depth}  expected={expected:<8} "
        f"actual={actual:<8} ({elapsed:.2f}s)"
    )
    return passed


def main():
    parser = argparse.ArgumentParser(description="perft suite for chessEngine.py")
    parser.add_argument(
        "--fast", action="store_true",
        help="skip the two slowest cases (startpos depth 4, kiwipete depth 3)",
    )
    args = parser.parse_args()

    failures = 0
    for name, fen, depth, expected, is_slow in PERFT_CASES:
        if args.fast and is_slow:
            continue
        if not run_case(name, fen, depth, expected):
            failures += 1

    if failures:
        print(f"\n{failures} case(s) failed.")
        sys.exit(1)
    else:
        print("\nAll perft cases passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()