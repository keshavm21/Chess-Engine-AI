"""
Performance benchmark for Chess-Engine-AI.

Two parts:

- Perft: counts all legal move sequences to a fixed depth from standard
  positions. It measures move generation plus make/undo on their own, and
  checks the counts against the published values.
- Search: runs the AI's search on representative positions, once to a fixed
  depth and once with a time limit per position, and records the depth
  reached, time, nodes, nodes per second, alpha-beta cutoffs and chosen move.

The fixed-depth search is deterministic, so its node counts and chosen moves
only change when search or evaluation behaviour changes; time and nodes per
second vary a little between runs, and the time-limited search depends on the
machine. Record meaningful results in docs/benchmarks.md.

Run with:
    python -m chess_ai.benchmark                 # perft + search (~10 s)
    python -m chess_ai.benchmark --time-limit 2  # 2 s per timed search
    python -m chess_ai.benchmark --perft-only    # just move generation
    python -m chess_ai.benchmark --json out.json # also save the results
"""

import argparse
import json
import platform
import sys
import time

from chess_ai import search
from chess_ai.engine import GameState

# (name, FEN, depth, published node count)
PERFT_POSITIONS = [
    (
        "Starting position",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
        4,
        197281,
    ),
    (
        "Kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        3,
        97862,
    ),
]

SEARCH_POSITIONS = [
    (
        "Starting position",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
    ),
    (
        "Italian Game (after 1.e4 e5 2.Nf3 Nc6 3.Bc4)",
        "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -",
    ),
    (
        "Middlegame (rich tactical)",
        "r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ -",
    ),
    (
        "Kiwipete (stress position)",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
    ),
]


def perft(gs, depth):
    """Number of legal move sequences of exactly `depth` plies."""
    if depth == 0:
        return 1
    moves = gs.get_legal_moves()
    if depth == 1:
        return len(moves)
    total = 0
    for move in moves:
        gs.make_move(move)
        total += perft(gs, depth - 1)
        gs.undo_move()
    return total


def per_second(count, seconds):
    return int(count / seconds) if seconds > 0 else 0


def run_perft():
    print(
        f"{'Perft position':<42} {'Depth':>5} {'Nodes':>10} {'Time':>8} {'Nodes/s':>10}"
    )
    print("-" * 80)
    results = []
    for name, fen, depth, expected in PERFT_POSITIONS:
        gs = GameState.from_fen(fen)
        t0 = time.perf_counter()
        nodes = perft(gs, depth)
        elapsed = time.perf_counter() - t0
        ok = nodes == expected
        results.append(
            {
                "name": name,
                "fen": fen,
                "depth": depth,
                "nodes": nodes,
                "expected_nodes": expected,
                "correct": ok,
                "time_s": elapsed,
                "nodes_per_s": per_second(nodes, elapsed),
            }
        )
        flag = "" if ok else f"  MISMATCH (expected {expected:,})"
        print(
            f"{name:<42} {depth:>5} {nodes:>10,} {elapsed:>7.2f}s "
            f"{per_second(nodes, elapsed):>10,}{flag}"
        )
    print()
    return results


def run_search(max_depth=None, time_limit=None):
    """Search every position with the given limits and print a table."""
    if time_limit is None:
        title = f"Search, fixed depth {max_depth}"
    else:
        title = f"Search, {time_limit:g} s per position"
    print(
        f"{title:<42} {'Time':>7} {'Depth':>5} {'Nodes':>8} {'NPS':>7} "
        f"{'Cutoffs':>7} {'Move':>6}"
    )
    print("-" * 88)
    results = []
    for name, fen in SEARCH_POSITIONS:
        gs = GameState.from_fen(fen)
        legal_moves = gs.get_legal_moves()
        result = search.Searcher(max_depth, time_limit).search(gs, list(legal_moves))
        move = result.move.coordinate_notation() if result.move else "None"
        results.append(
            {
                "name": name,
                "fen": fen,
                "max_depth": max_depth,
                "time_limit_s": time_limit,
                "depth": result.depth,
                "legal_moves": len(legal_moves),
                "time_s": result.elapsed,
                "nodes": result.nodes,
                "nps": result.nodes_per_second,
                "cutoffs": result.cutoffs,
                "timed_out": result.timed_out,
                "move": move,
            }
        )
        print(
            f"{name:<42} {result.elapsed:>6.2f}s {result.depth:>5} "
            f"{result.nodes:>8,} {result.nodes_per_second:>7,} "
            f"{result.cutoffs:>7,} {move:>6}"
        )

    total_nodes = sum(r["nodes"] for r in results)
    total_time = sum(r["time_s"] for r in results)
    print("-" * 88)
    print(
        f"{'Total':<42} {total_time:>6.2f}s {'':>5} {total_nodes:>8,} "
        f"{per_second(total_nodes, total_time):>7,}"
    )
    print()
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument(
        "--perft-only", action="store_true", help="skip the (slower) search part"
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="time per position for the time-limited search (0 to skip it)",
    )
    parser.add_argument("--json", metavar="PATH", help="also write results as JSON")
    args = parser.parse_args(argv)

    environment = {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "machine": platform.machine(),
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    print("=" * 82)
    print("CHESS ENGINE AI — PERFORMANCE BENCHMARK")
    print("=" * 82)
    print(
        f"Python {environment['python']} on {environment['platform']} "
        f"({environment['machine']})"
    )
    print()

    report = {"environment": environment, "perft": run_perft()}
    if not args.perft_only:
        report["search"] = run_search(max_depth=search.MAX_DEPTH)
        if args.time_limit > 0:
            report["timed_search"] = run_search(time_limit=args.time_limit)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Results written to {args.json}")

    return 0 if all(r["correct"] for r in report["perft"]) else 1


if __name__ == "__main__":
    sys.exit(main())
