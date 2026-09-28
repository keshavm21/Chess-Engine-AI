"""Move search: negamax (minimax) with alpha-beta pruning and move ordering."""

import math
import random
import time
import traceback
from dataclasses import dataclass

from chess_ai.evaluation import (
    PIECE_VALUES,
    STALEMATE,
    clear_attack_cache,
    evaluate,
    is_opening_phase,
    mate_score,
)

MAX_DEPTH = 3  # default search depth in plies: raise for strength, lower for speed


# ---------- Move Ordering Heuristics ----------
def get_move_priority(move, gs, is_white):
    """Assign priority to moves for better alpha-beta pruning"""
    priority = 0

    # Captures get highest priority
    if move.piece_captured != "--":
        captured_value = PIECE_VALUES.get(move.piece_captured[1], 0)
        attacker_value = PIECE_VALUES.get(move.piece_moved[1], 0)
        priority += 1000 + (captured_value * 10 - attacker_value)

    # Queen promotions are very good; underpromotions are rarely best, so
    # they get no bonus and are searched late.
    if move.promotion_piece == "Q":
        priority += 900

    # Checks get good priority
    gs.make_move(move)
    if gs.in_check():
        priority += 800
    gs.undo_move()

    # Developing moves in opening
    if is_opening_phase(gs):
        # Knight development
        if move.piece_moved[1] == "N" and move.start_row in [0, 7]:
            priority += 200

        # Bishop development
        if move.piece_moved[1] == "B" and move.start_row in [0, 7]:
            priority += 150

        # Castling
        if move.piece_moved[1] == "K" and abs(move.start_col - move.end_col) == 2:
            priority += 1000

    # Center control
    if move.end_col in [3, 4] and move.end_row in [3, 4]:
        priority += 50

    return priority


# ---------- Search ----------
def find_random_move(legal_moves):
    """Return a random legal move (the GUI's fallback if the search fails)."""
    return legal_moves[random.randint(0, len(legal_moves) - 1)]


@dataclass
class SearchResult:
    """What a search found, plus statistics about it."""

    move: object  # the chosen Move; None only if there are no legal moves
    score: float | None  # from White's point of view; None if nothing was searched
    depth: int  # search depth in plies (0 if nothing was searched)
    nodes: int  # positions visited
    cutoffs: int  # alpha-beta cutoffs
    elapsed: float  # seconds

    @property
    def nodes_per_second(self):
        return int(self.nodes / self.elapsed) if self.elapsed > 0 else 0


class Searcher:
    """Negamax search with alpha-beta pruning.

    All state of a search (node counters, best root move) lives on the
    instance, so separate searches cannot interfere with each other.
    """

    def __init__(self, max_depth=MAX_DEPTH):
        self.max_depth = max_depth
        self.nodes = 0
        self.cutoffs = 0
        self._best_root_move = None

    def search(self, gs, legal_moves=None):
        """Search the position and return a SearchResult."""
        start = time.perf_counter()
        if legal_moves is None:
            legal_moves = gs.get_legal_moves()
        self.nodes = self.cutoffs = 0
        clear_attack_cache(gs)  # start every search with an empty attack cache

        # No move, or a single legal move: nothing to decide. Two or three
        # legal moves are a real decision (often the only replies to a
        # check) and are always searched.
        if len(legal_moves) <= 1:
            move = legal_moves[0] if legal_moves else None
            return SearchResult(move, None, 0, 0, 0, time.perf_counter() - start)

        move, score = self.search_depth(gs, legal_moves, self.max_depth)
        return SearchResult(
            move if move is not None else legal_moves[0],
            score,
            self.max_depth,
            self.nodes,
            self.cutoffs,
            time.perf_counter() - start,
        )

    def search_depth(self, gs, legal_moves, depth):
        """One alpha-beta search `depth` plies deep.

        Returns (best move, score from White's point of view). The best move is
        None when there are no legal moves.
        """
        self._best_root_move = None
        color = 1 if gs.white_to_move else -1
        # The root window must be unbounded: mate scores are
        # CHECKMATE + depth, i.e. >= CHECKMATE, so a [-CHECKMATE, CHECKMATE]
        # window made the first mate found (even a slow one) cause a cutoff
        # before a faster mate further down the move list was examined.
        score = self._negamax(gs, legal_moves, depth, -math.inf, math.inf, color, 0)
        return self._best_root_move, color * score

    def _negamax(self, gs, legal_moves, depth, alpha, beta, color, ply):
        """Alpha-beta negamax search, `depth` plies deep.

        Scores are from the point of view of the side to move: `color` is +1
        when White is to move and -1 when Black is, and a child's score is
        negated for its parent. This is minimax written once for both sides.
        `ply` is the distance from the root; the best move at the root is
        recorded in `_best_root_move`.
        """
        self.nodes += 1

        # No legal moves: checkmate or stalemate (decided here, not via flags
        # set as a side effect of move generation).
        if not legal_moves:
            return color * (mate_score(gs, depth) if gs.in_check() else STALEMATE)
        if depth == 0:
            return color * evaluate(gs, depth)

        # Sort moves at the top two plies for better pruning
        if ply <= 1:
            moves = sorted(
                legal_moves,
                key=lambda m: get_move_priority(m, gs, color == 1),
                reverse=True,
            )
        else:
            moves = legal_moves

        best_score = -math.inf
        for move in moves:
            gs.make_move(move)
            next_moves = gs.get_legal_moves()
            score = -self._negamax(
                gs, next_moves, depth - 1, -beta, -alpha, -color, ply + 1
            )
            gs.undo_move()

            if score > best_score:
                best_score = score
                if ply == 0:
                    self._best_root_move = move

            alpha = max(alpha, score)
            if alpha >= beta:
                self.cutoffs += 1
                break
        return best_score


def find_best_move(gs, legal_moves, return_queue=None, max_depth=MAX_DEPTH):
    """Return the best move for the side to move (see Searcher).

    When `return_queue` is given (the GUI runs this in a child process), the
    move is put on the queue instead of returned. Exceptions are printed and
    the first legal move is used, so the GUI never waits forever.
    """
    try:
        result = Searcher(max_depth).search(gs, legal_moves).move
    except Exception:
        traceback.print_exc()
        result = legal_moves[0] if legal_moves else None

    if return_queue is not None:
        try:
            return_queue.put(result)
        except Exception:
            pass
    else:
        return result
