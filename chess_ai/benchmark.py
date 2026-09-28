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
    python -m chess_ai.benchmark
"""

import sys
import time

from chess_ai import search
from chess_ai.engine import GameState

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
    depth = search.MAX_DEPTH

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
        gs = GameState.from_fen(pos["fen"])
        legal_moves = gs.get_legal_moves()

        t0 = time.time()
        chosen = search.find_best_move(gs, list(legal_moves))
        elapsed = time.time() - t0

        nodes = search.nodes_explored
        nps = int(nodes / elapsed) if elapsed > 0 else 0
        move_str = chosen.coordinate_notation() if chosen else "None"

        result = {
            "name": pos["name"],
            "fen": pos["fen"],
            "depth": depth,
            "time_s": elapsed,
            "nodes": nodes,
            "nps": nps,
            "move": move_str,
            "legal_moves": len(legal_moves),
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
