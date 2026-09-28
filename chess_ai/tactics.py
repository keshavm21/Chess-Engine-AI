"""
Tactics suite: positions with verified answers, used to measure playing strength.

Each puzzle lists either the moves that solve it (`solutions`) or, for "avoid"
puzzles, the moves that lose material or the win (`avoid`). The answer sets are
exact: tests/test_tactics.py re-derives them with an exhaustive search (a
forced-mate search for mate puzzles; a full-width material-only search, 4 plies
plus captures, for the others).

Kinds: "mate1" / "mate2" / "mate3" (mate in one / two / three), "win" (win
material) and "avoid" (do not blunder). The mate-in-3 and the poisoned-pawn
puzzles need more than 3 plies of look-ahead.

Run with:
    python -m chess_ai.tactics                  # default difficulty's time limit
    python -m chess_ai.tactics --depth 3        # fixed depth (deterministic)
    python -m chess_ai.tactics --time-limit 5 --json out.json
"""

import argparse
import json
import sys
from dataclasses import dataclass

from chess_ai import search
from chess_ai.engine import GameState


@dataclass(frozen=True)
class Puzzle:
    name: str
    kind: str  # "mate1", "mate2", "mate3", "win" or "avoid"
    fen: str
    solutions: tuple = ()  # the engine's move must be one of these ...
    avoid: tuple = ()  # ... or, for "avoid" puzzles, none of these

    def is_solved_by(self, move):
        """True if `move` (coordinate notation, e.g. "e2e4") solves the puzzle."""
        if self.solutions:
            return move in self.solutions
        return move not in self.avoid


PUZZLES = [
    Puzzle(
        "Back-rank mate",
        "mate1",
        "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - -",
        solutions=("d1d8",),
    ),
    Puzzle(
        "Smothered mate", "mate1", "6rk/6pp/8/6N1/8/8/8/6K1 w - -", solutions=("g5f7",)
    ),
    Puzzle(
        "Queen mate with king support",
        "mate1",
        "k7/8/1K6/8/8/8/8/6Q1 w - -",
        solutions=("g1g8",),
    ),
    Puzzle(
        "Mate by promotion",
        "mate1",
        "k7/2P5/1K6/8/8/8/8/8 w - -",
        solutions=("c7c8q", "c7c8r"),
    ),
    Puzzle(
        "Back-rank mate (Black)",
        "mate1",
        "3r2k1/5ppp/8/8/8/8/5PPP/6K1 b - -",
        solutions=("d8d1",),
    ),
    Puzzle(
        "Doubled rooks on the back rank",
        "mate2",
        "r5k1/5ppp/8/8/8/8/3R1PPP/3R2K1 w - -",
        solutions=("d2d8",),
    ),
    Puzzle("King and rook", "mate2", "7k/8/5K2/8/8/8/8/6R1 w - -", solutions=("f6f7",)),
    Puzzle(
        "Queen and king",
        "mate2",
        "7k/8/5K2/8/8/8/8/4Q3 w - -",
        solutions=("e1e7", "e1g1", "e1g3", "f6f7", "f6g6"),
    ),
    Puzzle(
        "Doubled rooks (Black)",
        "mate2",
        "3r2k1/3r1ppp/8/8/8/8/5PPP/R5K1 b - -",
        solutions=("d7d1",),
    ),
    Puzzle(
        "King and rook, mate in 3",
        "mate3",
        "7k/8/8/5K2/8/8/8/6R1 w - -",
        solutions=("f5g6",),
    ),
    Puzzle(
        "Two rooks, mate in 3",
        "mate3",
        "8/8/7k/8/8/8/R7/1R4K1 w - -",
        solutions=("a2g2",),
    ),
    Puzzle(
        "King and rook, mate in 3 (Black)",
        "mate3",
        "6r1/8/8/8/5k2/8/8/7K b - -",
        solutions=("f4g3",),
    ),
    Puzzle(
        "Knight fork of king and rook",
        "win",
        "r3k3/8/8/3N4/8/8/8/4K3 w - -",
        solutions=("d5c7",),
    ),
    Puzzle(
        "Knight fork of king and queen",
        "win",
        "2q1k3/8/8/1N6/8/8/8/4K3 w - -",
        solutions=("b5d6",),
    ),
    Puzzle("Rook skewer", "win", "4q3/8/8/4k3/8/8/K7/7R w - -", solutions=("h1e1",)),
    Puzzle(
        "Discovered attack on the queen",
        "win",
        "4k3/4q3/8/8/8/8/4B3/4R1K1 w - -",
        solutions=("e2b5", "e2h5"),
    ),
    Puzzle(
        "Knight fork (Black)",
        "win",
        "4k3/8/8/8/3n4/8/8/R3K3 b - -",
        solutions=("d4c2",),
    ),
    Puzzle("Hanging queen", "win", "4k3/8/8/3q4/8/8/8/3RK3 w - -", solutions=("d1d5",)),
    Puzzle(
        "Back-rank threat",
        "avoid",
        "3r2k1/p4ppp/8/8/1Q6/8/5PPP/6K1 w - -",
        avoid=(
            "b4a3",
            "b4a5",
            "b4b2",
            "b4b5",
            "b4b6",
            "b4b7",
            "b4b8",
            "b4c3",
            "b4c4",
            "b4c5",
            "b4d2",
            "b4d4",
            "b4d6",
            "b4e4",
            "b4e7",
            "b4f4",
            "b4f8",
            "b4h4",
            "g1h1",
        ),
    ),
    Puzzle(
        "Do not stalemate",
        "avoid",
        "7k/8/6K1/8/8/8/8/5Q2 w - -",
        avoid=("f1c4", "f1f7"),
    ),
    Puzzle(
        "Poisoned pawn: Nxe5?? Qa5+",
        "avoid",
        "3qk3/8/8/4p3/8/5N2/PP3PPP/4K2R w K -",
        avoid=("e1f1", "f3d4", "f3e5", "f3g5", "f3h4", "g2g3", "g2g4"),
    ),
    Puzzle(
        "Poisoned pawn (Black): Nxe4?? Qa4+",
        "avoid",
        "4k2r/pp3ppp/5n2/8/4P3/8/8/3QK3 b k -",
        avoid=("e8f8", "f6d5", "f6e4", "f6g4", "f6h5", "g7g5", "g7g6"),
    ),
]

KINDS = ("mate1", "mate2", "mate3", "win", "avoid")


def run(max_depth=None, time_limit=None, puzzles=None, verbose=True):
    """Let the engine solve every puzzle; return one result dict per puzzle."""
    results = []
    for puzzle in PUZZLES if puzzles is None else puzzles:
        gs = GameState.from_fen(puzzle.fen)
        result = search.Searcher(max_depth, time_limit).search(gs)
        move = result.move.coordinate_notation()
        solved = puzzle.is_solved_by(move)
        results.append(
            {
                "name": puzzle.name,
                "kind": puzzle.kind,
                "fen": puzzle.fen,
                "move": move,
                "solved": solved,
                "depth": result.depth,
                "time_s": result.elapsed,
            }
        )
        if verbose:
            print(
                f"{'solved' if solved else 'FAILED':<7} {puzzle.kind:<6} "
                f"{puzzle.name:<34} {move:<6} depth {result.depth:<2} "
                f"{result.elapsed:5.2f}s"
            )
    return results


def summary(results):
    """Solve rate overall and per kind, e.g. {"all": (15, 17), "win": (5, 5)}."""
    counts = {}
    for key in ("all",) + KINDS:
        rows = [r for r in results if key == "all" or r["kind"] == key]
        if rows:
            counts[key] = (sum(r["solved"] for r in rows), len(rows))
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    limits = parser.add_mutually_exclusive_group()
    limits.add_argument("--depth", type=int, help="fixed search depth in plies")
    limits.add_argument("--time-limit", type=float, metavar="SECONDS")
    parser.add_argument("--json", metavar="PATH", help="also write results as JSON")
    args = parser.parse_args(argv)

    time_limit = args.time_limit
    if args.depth is None and time_limit is None:
        time_limit = search.DIFFICULTIES[search.DEFAULT_DIFFICULTY].time_limit
    limit = f"depth {args.depth}" if args.depth else f"{time_limit:g} s per puzzle"
    print(f"Tactics suite, {len(PUZZLES)} puzzles, {limit}\n")

    results = run(args.depth, time_limit)
    counts = summary(results)
    print()
    for key, (solved, total) in counts.items():
        print(f"{key:<6} {solved:>2}/{total:<2} ({100 * solved / total:.0f}%)")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(
                {"limit": limit, "summary": counts, "results": results}, f, indent=2
            )
        print(f"\nResults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
