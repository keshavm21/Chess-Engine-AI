"""
Baseline search benchmark for Chess-Engine-AI.

Runs the engine's search on a set of representative positions and records:
- Search depth
- Wall-clock time
- Nodes explored
- Nodes per second
- Chosen move

This provides a reproducible baseline before any search improvements
(move ordering, iterative deepening, quiescence search, etc.) are made.

Run with:
    python3 benchmark.py
"""

import os
import sys
import time

# Make sure the repo root is importable.
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import chessEngine
import SmartMoveFinder


# ---------------------------------------------------------------------------
# FEN loader (same pattern used by the test suite)
# ---------------------------------------------------------------------------

def set_position_from_fen(gs, fen):
    """Configure an existing GameState to match a FEN position."""
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


# ---------------------------------------------------------------------------
# Benchmark positions
# ---------------------------------------------------------------------------

POSITIONS = [
    {
        "name": "Starting position",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
    },
    {
        "name": "Italian Game (after 1.e4 e5 2.Nf3 Nc6 3.Bc4)",
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -",
    },
    {
        "name": "Middlegame (rich tactical)",
        "fen": "r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ -",
    },
    {
        "name": "Kiwipete (stress position)",
        "fen": "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
    },
]


# ---------------------------------------------------------------------------
# Run benchmark
# ---------------------------------------------------------------------------

def run_benchmark():
    depth = SmartMoveFinder.MAX_DEPTH

    print("=" * 72)
    print("CHESS ENGINE AI — BASELINE SEARCH BENCHMARK")
    print("=" * 72)
    print(f"Search depth:  {depth}")
    print(f"Python:        {sys.version.split()[0]}")
    print(f"Platform:      {sys.platform}")
    print()

    # Header
    print(f"{'Position':<42} {'Time':>8} {'Nodes':>10} {'NPS':>10} {'Move':>8}")
    print("-" * 82)

    results = []

    for pos in POSITIONS:
        gs = chessEngine.GameState()
        set_position_from_fen(gs, pos["fen"])
        valid_moves = gs.getValidMoves()

        t0 = time.time()
        chosen = SmartMoveFinder.findBestMoveMinMax(gs, list(valid_moves))
        elapsed = time.time() - t0

        nodes = SmartMoveFinder.nodesExplored
        nps = int(nodes / elapsed) if elapsed > 0 else 0
        move_str = chosen.getChessNotation() if chosen else "None"

        result = {
            "name": pos["name"],
            "fen": pos["fen"],
            "depth": depth,
            "time_s": elapsed,
            "nodes": nodes,
            "nps": nps,
            "move": move_str,
            "legal_moves": len(valid_moves),
        }
        results.append(result)

        print(
            f"{pos['name']:<42} {elapsed:>7.2f}s {nodes:>10,} {nps:>10,} {move_str:>8}"
        )

    print("-" * 82)
    print()

    # Summary
    total_nodes = sum(r["nodes"] for r in results)
    total_time = sum(r["time_s"] for r in results)
    overall_nps = int(total_nodes / total_time) if total_time > 0 else 0

    print(f"Total nodes:   {total_nodes:,}")
    print(f"Total time:    {total_time:.2f}s")
    print(f"Overall NPS:   {overall_nps:,}")
    print()

    # Detailed results
    print("=" * 72)
    print("DETAILED RESULTS")
    print("=" * 72)
    for r in results:
        print()
        print(f"  Position:    {r['name']}")
        print(f"  FEN:         {r['fen']}")
        print(f"  Legal moves: {r['legal_moves']}")
        print(f"  Depth:       {r['depth']}")
        print(f"  Nodes:       {r['nodes']:,}")
        print(f"  Time:        {r['time_s']:.3f}s")
        print(f"  NPS:         {r['nps']:,}")
        print(f"  Best move:   {r['move']}")

    print()
    print("=" * 72)
    print("Benchmark complete.")
    return results


if __name__ == "__main__":
    run_benchmark()
