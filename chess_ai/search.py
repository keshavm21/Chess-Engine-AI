"""Move search: iterative-deepening negamax with alpha-beta pruning.

Searches depth 1, 2, 3, ... until a depth limit or a time limit is reached and
plays the best move of the deepest completed search.
"""

import math
import random
import time
import traceback
from dataclasses import dataclass

from chess_ai.evaluation import CHECKMATE, PIECE_VALUES, STALEMATE, evaluate

DRAW = 0

# Transposition table entry bounds: the stored score is exact, or only a lower
# bound (the search failed high) or an upper bound (it failed low).
EXACT, LOWER_BOUND, UPPER_BOUND = 0, 1, 2
TT_MAX_ENTRIES = 200_000  # about 40 MB; the table is cleared when it is full

MAX_DEPTH = 3  # default search depth in plies: raise for strength, lower for speed
# Safety cap on the depth of a time-limited search.
MAX_SEARCH_DEPTH = 30
# A side that is mated `ply` plies from the root scores -(CHECKMATE - ply), so
# faster mates score higher. Scores beyond this threshold mean a forced mate.
MATE_THRESHOLD = CHECKMATE - 1000

# Piece values for move ordering (in pawns).
ORDER_VALUES = {"K": 0, "Q": 10, "R": 5, "B": 3, "N": 3, "p": 1}

# Quiescence pruning (centipawns): skip a capture that could not raise the score
# even if the captured piece were won for free plus this margin ...
DELTA_MARGIN = 200
# ... or that trades a piece for a defended one worth this much less.
LOSING_CAPTURE_MARGIN = 50


@dataclass(frozen=True)
class Difficulty:
    """Search limits for one difficulty level."""

    time_limit: float  # seconds per move
    max_depth: int | None = None  # optional depth cap in plies


# Measured on an Apple M1 (Phase 5): 0.5 s reaches depth 2-3, 2 s reaches
# depth 3 (sometimes 4-5) and 5 s mostly depth 4 in middlegame positions.
DIFFICULTIES = {
    "easy": Difficulty(time_limit=0.5, max_depth=2),
    "medium": Difficulty(time_limit=2.0),
    "hard": Difficulty(time_limit=5.0),
}
DEFAULT_DIFFICULTY = "medium"


# ---------- Move Ordering Heuristics ----------
def get_move_priority(move, gs, is_white):
    """Assign priority to moves for better alpha-beta pruning"""
    priority = 0

    # Captures get highest priority
    if move.piece_captured != "--":
        captured_value = ORDER_VALUES[move.piece_captured[1]]
        attacker_value = ORDER_VALUES[move.piece_moved[1]]
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
    if _is_opening_phase(gs):
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


def _capture_order(move):
    """Sort key: most valuable victim first, then least valuable attacker
    (MVV-LVA); a queen promotion counts like capturing a queen."""
    victim = ORDER_VALUES[move.piece_captured[1]] if move.is_capture else 0
    promotion = ORDER_VALUES[move.promotion_piece] if move.promotion_piece else 0
    return 10 * (victim + promotion) - ORDER_VALUES[move.piece_moved[1]]


def _score_to_tt(score, ply):
    """Mate scores count plies from the root; in the table they are stored
    relative to the node, so they stay right when reached along another path."""
    if score >= MATE_THRESHOLD:
        return score + ply
    if score <= -MATE_THRESHOLD:
        return score - ply
    return score


def _score_from_tt(score, ply):
    if score >= MATE_THRESHOLD:
        return score - ply
    if score <= -MATE_THRESHOLD:
        return score + ply
    return score


def _history_key(move):
    """History scores are kept per moving piece and target square."""
    return move.piece_moved, move.end_row, move.end_col


def _is_draw(gs):
    """Drawn by rule, as the search sees it: the fifty-move rule, insufficient
    material, or any repetition -- a position that has occurred before can be
    repeated again, so it is scored as a draw (not only at the third time)."""
    return (
        gs.halfmove_clock >= 100
        or gs.repetition_count() >= 2
        or gs.is_insufficient_material()
    )


def _is_opening_phase(gs):
    """More than 28 pieces (including pawns) are still on the board."""
    return sum(sq != "--" for row in gs.board for sq in row) > 28


# ---------- Search ----------
def find_random_move(legal_moves):
    """Return a random legal move (the GUI's fallback if the search fails)."""
    return legal_moves[random.randint(0, len(legal_moves) - 1)]


@dataclass
class SearchResult:
    """What a search found, plus statistics about it."""

    move: object  # the chosen Move; None only if there are no legal moves
    score: int | None  # centipawns, White's point of view; None if nothing was searched
    depth: int  # deepest completed search in plies (0 if nothing was searched)
    nodes: int  # positions visited (incl. quiescence), incl. a search cut short
    cutoffs: int  # alpha-beta cutoffs
    elapsed: float  # seconds
    timed_out: bool = False  # a deeper search was started but cut short
    qnodes: int = 0  # of `nodes`, those visited by the quiescence search
    tt_hits: int = 0  # nodes answered from the transposition table

    @property
    def nodes_per_second(self):
        return int(self.nodes / self.elapsed) if self.elapsed > 0 else 0


class _SearchTimeoutError(Exception):
    """Raised inside the search when the time limit has been reached."""


class Searcher:
    """Iterative-deepening negamax search with alpha-beta pruning.

    Give a `max_depth`, a `time_limit` in seconds, or both. Without a time
    limit the search is deterministic; with neither, it searches MAX_DEPTH
    plies. All state of a search lives on the instance, so separate searches
    cannot interfere with each other.
    """

    def __init__(
        self,
        max_depth=None,
        time_limit=None,
        evaluator=None,
        quiescence=True,
        transposition_table=True,
        history_ordering=True,
    ):
        if max_depth is None:
            max_depth = MAX_DEPTH if time_limit is None else MAX_SEARCH_DEPTH
        self.max_depth = max_depth
        self.time_limit = time_limit
        # Static evaluation in centipawns from White's point of view.
        self.evaluate = evaluator if evaluator is not None else evaluate
        # Play out captures at the leaves instead of evaluating mid-exchange.
        self.quiescence = quiescence
        # Zobrist key -> (depth, score, bound, best move). Kept across the
        # iterations of a search (and across searches by the same Searcher).
        self.tt = {} if transposition_table else None
        self.tt_hits = 0
        # Quiet-move ordering: two "killer" moves per ply (quiet moves that
        # recently caused a cutoff there) and a history score per piece and
        # target square. Both are reset for every search.
        self.history_ordering = history_ordering
        self._killers = {}
        self._history = {}
        self.nodes = 0
        self.qnodes = 0
        self.cutoffs = 0
        self._deadline = None  # perf_counter() value at which to stop, if any
        self._first_root_move = None  # searched first at the root
        self._best_root_move = None

    def search(self, gs, legal_moves=None):
        """Search the position and return a SearchResult."""
        start = time.perf_counter()
        if legal_moves is None:
            legal_moves = gs.get_legal_moves()
        self.nodes = self.qnodes = self.cutoffs = self.tt_hits = 0
        self._killers, self._history = {}, {}

        # No move, or a single legal move: nothing to decide. Two or three
        # legal moves are a real decision (often the only replies to a
        # check) and are always searched.
        if len(legal_moves) <= 1:
            move = legal_moves[0] if legal_moves else None
            return SearchResult(move, None, 0, 0, 0, time.perf_counter() - start)

        best_move, best_score, completed_depth, timed_out = None, None, 0, False
        log_length = len(gs.move_log)
        for depth in range(1, self.max_depth + 1):
            # Depth 1 always runs to the end, so there is always a searched move.
            if depth > 1 and self.time_limit is not None:
                self._deadline = start + self.time_limit
            try:
                move, score = self.search_depth(
                    gs, legal_moves, depth, first_move=best_move
                )
            except _SearchTimeoutError:
                # Unwind the moves the interrupted search had made on `gs`.
                while len(gs.move_log) > log_length:
                    gs.undo_move()
                timed_out = True
                break
            finally:
                self._deadline = None
            best_move, best_score, completed_depth = move, score, depth

            if abs(score) >= MATE_THRESHOLD:
                break  # a forced mate was found; searching deeper cannot change it
            if self.time_limit is not None:
                # Each depth takes several times longer than all previous ones
                # together, so once half the time is used the next depth would
                # not finish; an unfinished depth is discarded anyway.
                if time.perf_counter() - start >= self.time_limit / 2:
                    break

        return SearchResult(
            best_move if best_move is not None else legal_moves[0],
            best_score,
            completed_depth,
            self.nodes,
            self.cutoffs,
            time.perf_counter() - start,
            timed_out,
            self.qnodes,
            self.tt_hits,
        )

    def search_depth(self, gs, legal_moves, depth, first_move=None):
        """One alpha-beta search `depth` plies deep.

        `first_move` (usually the best move of the previous depth) is searched
        first at the root, which lets alpha-beta prune more. Returns (best move,
        score from White's point of view); the best move is None when there
        are no legal moves.
        """
        self._first_root_move = first_move
        self._best_root_move = None
        color = 1 if gs.white_to_move else -1
        # The root window must be unbounded: with a window that mate scores
        # could reach, the first mate found (even a slow one) caused a cutoff
        # before a faster mate further down the move list was examined (S1).
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
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            raise _SearchTimeoutError

        # No legal moves: checkmate or stalemate (decided here, not via flags
        # set as a side effect of move generation).
        if not legal_moves:
            return -(CHECKMATE - ply) if gs.in_check() else STALEMATE
        # Draws by rule; not at the root, where a move must still be chosen.
        if ply > 0 and _is_draw(gs):
            return DRAW
        if depth == 0:
            if self.quiescence:
                return self._quiesce(gs, alpha, beta, color, ply, legal_moves)
            return color * self.evaluate(gs)

        # Transposition table: reuse a result from an earlier search of this
        # position when it was searched at least as deep and its bound decides
        # this node; otherwise its best move is at least searched first.
        alpha_original = alpha
        tt_move = None
        if self.tt is not None:
            entry = self.tt.get(gs.zobrist_key)
            if entry is not None:
                entry_depth, entry_score, bound, tt_move = entry
                if ply > 0 and entry_depth >= depth:
                    score = _score_from_tt(entry_score, ply)
                    if (
                        bound == EXACT
                        or (bound == LOWER_BOUND and score >= beta)
                        or (bound == UPPER_BOUND and score <= alpha)
                    ):
                        self.tt_hits += 1
                        return score

        # Sort moves at the top two plies for better pruning
        if ply <= 1:
            moves = sorted(
                legal_moves,
                key=lambda m: get_move_priority(m, gs, color == 1),
                reverse=True,
            )
            if ply == 0 and self._first_root_move in moves:
                moves.remove(self._first_root_move)
                moves.insert(0, self._first_root_move)
        elif self.history_ordering:
            # Deeper down a cheap ordering: captures (MVV-LVA), then killer
            # moves, then the other quiet moves by their history score.
            killers = self._killers.get(ply, ())
            moves = sorted(
                legal_moves,
                key=lambda m: self._quiet_order(m, killers),
                reverse=True,
            )
        else:
            moves = sorted(legal_moves, key=_capture_order, reverse=True)
        first = self._first_root_move if ply == 0 else None
        if tt_move is not None and first is None and tt_move in moves:
            moves.remove(tt_move)
            moves.insert(0, tt_move)

        best_score, best_move = -math.inf, None
        for move in moves:
            gs.make_move(move)
            next_moves = gs.get_legal_moves()
            score = -self._negamax(
                gs, next_moves, depth - 1, -beta, -alpha, -color, ply + 1
            )
            gs.undo_move()

            if score > best_score:
                best_score, best_move = score, move
                if ply == 0:
                    self._best_root_move = move

            alpha = max(alpha, score)
            if alpha >= beta:
                self.cutoffs += 1
                if self.history_ordering and not (move.is_capture or move.is_promotion):
                    self._remember_quiet_cutoff(move, depth, ply)
                break

        if self.tt is not None:
            if best_score <= alpha_original:
                bound = UPPER_BOUND
            elif best_score >= beta:
                bound = LOWER_BOUND
            else:
                bound = EXACT
            if len(self.tt) >= TT_MAX_ENTRIES:
                self.tt.clear()
            self.tt[gs.zobrist_key] = (
                depth,
                _score_to_tt(best_score, ply),
                bound,
                best_move,
            )
        return best_score

    def _quiet_order(self, move, killers):
        """Sort key: captures and promotions first (MVV-LVA), then killers,
        then quiet moves by history score."""
        if move.is_capture or move.is_promotion:
            return (2, _capture_order(move))
        if move in killers:
            return (1, -killers.index(move))
        return (0, self._history.get(_history_key(move), 0))

    def _remember_quiet_cutoff(self, move, depth, ply):
        killers = self._killers.setdefault(ply, [])
        if move not in killers:
            killers.insert(0, move)
            del killers[2:]
        key = _history_key(move)
        self._history[key] = self._history.get(key, 0) + depth * depth

    def _quiesce(self, gs, alpha, beta, color, ply, legal_moves=None):
        """Quiescence search: keep playing captures (and queen promotions) until
        the position is quiet, so it is never evaluated in the middle of an
        exchange -- the "horizon effect".

        The side to move may also "stand pat" on the static evaluation instead
        of capturing, except when in check: then every legal move is searched,
        so mates are still found. `legal_moves`, when the caller already has
        them, saves generating them again.
        """
        self.nodes += 1
        self.qnodes += 1
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            raise _SearchTimeoutError

        if gs.in_check():
            moves = legal_moves if legal_moves is not None else gs.get_legal_moves()
            if not moves:
                return -(CHECKMATE - ply)
            best_score = -math.inf
        elif gs.is_insufficient_material():
            return DRAW  # e.g. the last pawn was just captured in K+N v K+P
        else:
            best_score = color * self.evaluate(gs)  # stand pat
            if best_score >= beta:
                return best_score
            alpha = max(alpha, best_score)
            if legal_moves is None:
                moves = gs.get_legal_moves(captures_only=True)
            else:
                moves = [m for m in legal_moves if m.is_capture or m.is_promotion]
            # Underpromotions are almost never better than a queen.
            moves = [m for m in moves if m.promotion_piece in (None, "Q")]

        in_check = best_score == -math.inf
        moves.sort(key=_capture_order, reverse=True)
        for move in moves:
            if not in_check and self._futile_capture(gs, move, best_score, alpha):
                continue
            gs.make_move(move)
            score = -self._quiesce(gs, -beta, -alpha, -color, ply + 1)
            gs.undo_move()
            if score > best_score:
                best_score = score
            alpha = max(alpha, score)
            if alpha >= beta:
                self.cutoffs += 1
                break
        return best_score

    @staticmethod
    def _futile_capture(gs, move, stand_pat, alpha):
        """True for a quiescence capture that is not worth searching: either it
        cannot raise the score even if the captured piece comes for free (delta
        pruning), or a more valuable piece takes a defended one (a cheap stand-in
        for a static exchange evaluation). Only used when not in check."""
        gain = PIECE_VALUES[move.piece_captured[1]] if move.is_capture else 0
        if move.promotion_piece:
            gain += PIECE_VALUES[move.promotion_piece] - PIECE_VALUES["p"]
        if stand_pat + gain + DELTA_MARGIN < alpha:
            return True
        attacker = PIECE_VALUES[move.piece_moved[1]]
        if move.is_capture and attacker - gain > LOSING_CAPTURE_MARGIN:
            defended = gs.is_attacked_by(
                move.end_row, move.end_col, not gs.white_to_move
            )
            return defended
        return False


def evaluate_position(gs, legal_moves=None):
    """The engine's quick verdict on a position, e.g. for the GUI's evaluation
    bar: the static evaluation after the quiescence search has played out any
    pending captures, in centipawns from White's point of view. Checkmate and
    stalemate are recognised."""
    if legal_moves is None:
        legal_moves = gs.get_legal_moves()
    if legal_moves and gs.draw_by_rule():
        return DRAW
    return Searcher().search_depth(gs, legal_moves, 0)[1]


def find_best_move(gs, legal_moves, return_queue=None, max_depth=None, time_limit=None):
    """Return the best move for the side to move (see Searcher).

    When `return_queue` is given (the GUI runs this in a child process), the
    move is put on the queue instead of returned. Exceptions are printed and
    the first legal move is used, so the GUI never waits forever.
    """
    try:
        result = Searcher(max_depth, time_limit).search(gs, legal_moves).move
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
