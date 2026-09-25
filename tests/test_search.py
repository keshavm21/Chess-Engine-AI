"""
Regression tests for findBestMoveMinMax() / findMoveMinMaxAlphaBeta().

Run with:
    python3 tests/test_search.py
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import chessEngine
import SmartMoveFinder


class Skipped(Exception):
    pass


def set_position_from_fen(gs, fen):
    """Minimal FEN loader (board, side to move, castling, en passant)."""
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
    gs.enpassantPossible = () if ep == "-" else (
        8 - int(ep[1]), ord(ep[0]) - ord("a"),
    )
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


def test_three_legal_moves_finds_the_free_queen_capture():
    """r1bqkbr1/pp1p2pp/n3pp2/2p4Q/7P/3PP1n1/PPP2PP1/RNB1KBNR b Q -

    Black is in check from the White queen on h5 (it checks along the
    h5-e8 diagonal). Black has exactly three legal replies: Ke7, g6, or
    Nxh5 -- and Nxh5 both captures the checking queen outright *and*
    resolves the check in the same move. validMoves[0] (board-scan
    order) is Ke7, a mere retreat that leaves the queen on the board.
    This holds regardless of whether the attack-cache fix has also been
    applied (verified against all four fix combinations), unlike an
    earlier candidate position that turned out to be sensitive to it.
    """
    gs = chessEngine.GameState()
    set_position_from_fen(
        gs, "r1bqkbr1/pp1p2pp/n3pp2/2p4Q/7P/3PP1n1/PPP2PP1/RNB1KBNR b Q -"
    )

    moves = gs.getValidMoves()
    assert len(moves) == 3, f"expected exactly 3 legal moves, got {len(moves)}"
    assert moves[0].getChessNotation() == "e0e7", (
        "this test assumes validMoves[0] is the king retreat (Ke7); if "
        "move-generation order changed, re-verify which index the "
        "shortcut would actually return."
    )

    chosen = SmartMoveFinder.findBestMoveMinMax(gs, list(moves))

    assert chosen.pieceMoved == "bN" and chosen.endRow == 3 and chosen.endCol == 7, (
        f"expected the knight to capture the checking queen on h5 "
        f"(Nxh5), but the engine chose {chosen.pieceMoved} to "
        f"{chr(ord('a') + chosen.endCol)}{8 - chosen.endRow} -- a <=3-style "
        f"shortcut (or an equivalent regression) is picking a move "
        f"without evaluating it."
    )


def test_single_legal_move_is_still_immediate():
    """A position with exactly one legal move should still return
    instantly without needing to run the full search -- that part of the
    original shortcut was sound and should be kept."""
    gs = chessEngine.GameState()
    set_position_from_fen(gs, "7k/8/6K1/8/8/8/8/6R1 b - -")

    moves = gs.getValidMoves()
    assert len(moves) == 1, f"expected exactly 1 legal move, got {len(moves)}"

    import time
    t0 = time.time()
    chosen = SmartMoveFinder.findBestMoveMinMax(gs, list(moves))
    elapsed = time.time() - t0

    assert chosen is moves[0]
    assert elapsed < 0.5, (
        f"the only legal move took {elapsed:.2f}s to return -- the "
        f"single-legal-move fast path appears to have been lost."
    )


def test_mate_distance_scoring_prefers_faster_mate():
    """A mate found with more search depth remaining (i.e. reached in
    fewer actual moves) must score more extremely than one found with
    less depth remaining, so the search can tell them apart instead of
    treating every mate as identical. Skipped gracefully if scoreBoard()
    doesn't accept a depth argument yet (Patch B not applied)."""
    if "depth" not in SmartMoveFinder.scoreBoard.__code__.co_varnames:
        raise Skipped("scoreBoard() has no depth parameter -- Patch B not applied yet")

    gs = chessEngine.GameState()
    gs.checkmate = True

    gs.whiteToMove = False  # White has just delivered mate to Black
    fast_mate = SmartMoveFinder.scoreBoard(gs, depth=2)
    slow_mate = SmartMoveFinder.scoreBoard(gs, depth=0)
    assert fast_mate > slow_mate > 0, (
        f"expected a faster mate to score higher than a slower one "
        f"(got fast={fast_mate}, slow={slow_mate})"
    )

    gs.whiteToMove = True  # Black has just delivered mate to White
    fast_loss = SmartMoveFinder.scoreBoard(gs, depth=2)
    slow_loss = SmartMoveFinder.scoreBoard(gs, depth=0)
    assert fast_loss < slow_loss < 0, (
        f"expected getting mated faster to score lower (worse) than "
        f"getting mated slower (got fast={fast_loss}, slow={slow_loss})"
    )


if __name__ == "__main__":
    tests = [
        test_three_legal_moves_finds_the_free_queen_capture,
        test_single_legal_move_is_still_immediate,
        test_mate_distance_scoring_prefers_faster_mate,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Skipped as e:
            print(f"SKIPPED: {test.__name__}\n  {e}")
        except AssertionError as e:
            failures += 1
            print(f"FAILED: {test.__name__}\n  {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR:  {test.__name__}\n  {type(e).__name__}: {e}")
        else:
            print(f"PASSED: {test.__name__}")

    if failures:
        print(f"\n{failures} test(s) failed.")
        sys.exit(1)
    else:
        print("\nAll search tests passed.")
        sys.exit(0)