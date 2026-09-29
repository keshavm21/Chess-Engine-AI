"""
Self-play match between two engine configurations.

Every opening is played twice with the colours swapped, so neither engine
profits from a better opening position. A game ends by checkmate or stalemate,
by threefold repetition, the fifty-move rule or insufficient material (the
engine's draw rules), or at a move limit: then the side that is at
least a rook ahead in material is awarded the win, otherwise it is a draw.

Run with:
    python -m chess_ai.match default depth-1 --depth 2            # sanity check
    python -m chess_ai.match A B --time 0.3 --jobs 4 --json out.json
"""

import argparse
import json
import math
import multiprocessing
import sys

from chess_ai import search
from chess_ai.engine import GameState

# Engine configurations: keyword arguments for search.Searcher. They are merged
# over the match's limits (--time / --depth), so a configuration can also
# handicap an engine, e.g. with a lower max_depth.
CONFIGS = {
    "default": {},
    "depth-1": {"max_depth": 1},
    "no-quiescence": {"quiescence": False},
}

# Well-known openings (coordinate notation), roughly balanced for both sides.
OPENINGS = [
    ("Italian Game", "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5"),
    ("Ruy Lopez", "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6"),
    ("Sicilian Defence", "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6"),
    ("French Defence", "e2e4 e7e6 d2d4 d7d5 b1c3 g8f6"),
    ("Caro-Kann Defence", "e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4"),
    ("Queen's Gambit Declined", "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6"),
    ("Slav Defence", "d2d4 d7d5 c2c4 c7c6 g1f3 g8f6"),
    ("King's Indian Defence", "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6"),
    ("English Opening", "c2c4 e7e5 b1c3 g8f6 g2g3 d7d5"),
    ("Scandinavian Defence", "e2e4 d7d5 e4d5 d8d5 b1c3 d5a5"),
]

MATERIAL = {"p": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}


def opening_position(moves):
    """GameState after playing the space-separated coordinate moves."""
    gs = GameState()
    for text in moves.split():
        move = next(
            (m for m in gs.get_legal_moves() if m.coordinate_notation() == text), None
        )
        if move is None:
            raise ValueError(f"illegal opening move {text!r} in {moves!r}")
        gs.make_move(move)
    return gs


def material_balance(board):
    """White's material minus Black's, in pawns."""
    return sum(
        MATERIAL[sq[1]] if sq[0] == "w" else -MATERIAL[sq[1]]
        for row in board
        for sq in row
        if sq != "--"
    )


def game_result(gs, legal_moves, plies, max_plies):
    """(result, reason) if the game is over, else None. Results are "1-0",
    "0-1" or "1/2-1/2"."""
    if not legal_moves:
        if gs.in_check():
            return ("0-1" if gs.white_to_move else "1-0"), "checkmate"
        return "1/2-1/2", "stalemate"
    reason = gs.draw_by_rule()
    if reason:
        return "1/2-1/2", reason
    if plies >= max_plies:
        balance = material_balance(gs.board)
        if balance >= 5:
            return "1-0", "move limit, adjudicated on material"
        if balance <= -5:
            return "0-1", "move limit, adjudicated on material"
        return "1/2-1/2", "move limit"
    return None


def play_game(white, black, opening, limits, max_plies=200):
    """Play one game between configurations `white` and `black` (names in
    CONFIGS) from the named opening. `limits` are Searcher keyword arguments
    such as {"time_limit": 0.3}."""
    name, moves = opening
    gs = opening_position(moves)
    played = []
    while True:
        legal_moves = gs.get_legal_moves()
        over = game_result(gs, legal_moves, len(played), max_plies)
        if over:
            break
        config = white if gs.white_to_move else black
        searcher = search.Searcher(**{**limits, **CONFIGS[config]})
        move = searcher.search(gs, legal_moves).move
        gs.make_move(move)
        played.append(move.coordinate_notation())
    result, reason = over
    return {
        "opening": name,
        "white": white,
        "black": black,
        "result": result,
        "reason": reason,
        "plies": len(played),
        "moves": played,
    }


def _play(task):
    return play_game(*task)


def score_for(engine, game):
    """Points (1, 0.5 or 0) that `engine` scored in `game`."""
    if game["result"] == "1/2-1/2":
        return 0.5
    winner = game["white"] if game["result"] == "1-0" else game["black"]
    return 1.0 if winner == engine else 0.0


def elo_difference(score):
    """Elo difference implied by a score fraction (0 < score < 1)."""
    if score <= 0:
        return -math.inf
    if score >= 1:
        return math.inf
    return -400 * math.log10(1 / score - 1)


def run_match(a, b, limits, openings=OPENINGS, max_plies=200, jobs=1, verbose=True):
    """Play every opening twice (A as White, then as Black) and return the games."""
    tasks = []
    for opening in openings:
        tasks.append((a, b, opening, limits, max_plies))
        tasks.append((b, a, opening, limits, max_plies))
    if jobs > 1:
        with multiprocessing.Pool(jobs) as pool:
            games = pool.map(_play, tasks)
    else:
        games = [_play(task) for task in tasks]
    if verbose:
        for game in games:
            print(
                f"{game['opening']:<26} {game['white']:>14} - {game['black']:<14} "
                f"{game['result']:<8} {game['reason']} ({game['plies']} plies)"
            )
    return games


def summarize(a, b, games):
    points = sum(score_for(a, g) for g in games)
    wins = sum(score_for(a, g) == 1 for g in games)
    losses = sum(score_for(a, g) == 0 for g in games)
    draws = len(games) - wins - losses
    fraction = points / len(games)
    return {
        "a": a,
        "b": b,
        "games": len(games),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score": points,
        "score_fraction": fraction,
        "elo_difference": elo_difference(fraction),
        "adjudicated": sum("adjudicated" in g["reason"] for g in games),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("a", choices=CONFIGS, help="engine A (scores are A's)")
    parser.add_argument("b", choices=CONFIGS, help="engine B")
    limits = parser.add_mutually_exclusive_group()
    limits.add_argument("--time", type=float, help="seconds per move (default 0.3)")
    limits.add_argument("--depth", type=int, help="fixed search depth instead")
    parser.add_argument(
        "--openings", type=int, default=len(OPENINGS), help="use the first N openings"
    )
    parser.add_argument("--max-plies", type=int, default=200)
    parser.add_argument("--jobs", type=int, default=1, help="games played in parallel")
    parser.add_argument("--json", metavar="PATH", help="also write the games as JSON")
    args = parser.parse_args(argv)

    if args.depth is not None:
        limit = {"max_depth": args.depth}
    else:
        limit = {"time_limit": args.time if args.time is not None else 0.3}
    openings = OPENINGS[: args.openings]
    print(
        f"{args.a} vs {args.b}: {2 * len(openings)} games, {limit}, "
        f"max {args.max_plies} plies\n"
    )

    games = run_match(args.a, args.b, limit, openings, args.max_plies, args.jobs)
    stats = summarize(args.a, args.b, games)
    print(
        f"\n{args.a}: +{stats['wins']} ={stats['draws']} -{stats['losses']}, "
        f"score {stats['score']:g}/{stats['games']} ({100 * stats['score_fraction']:.0f}%), "
        f"Elo difference about {stats['elo_difference']:+.0f} "
        f"(rough with this few games; {stats['adjudicated']} adjudicated)"
    )
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"limits": limit, "summary": stats, "games": games}, f, indent=2)
        print(f"Games written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
