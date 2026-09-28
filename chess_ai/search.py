"""Move search: minimax with alpha-beta pruning and move ordering."""

import math
import random
import traceback

from chess_ai.evaluation import (
    PIECE_VALUES,
    clear_attack_cache,
    evaluate,
    is_opening_phase,
)

MAX_DEPTH = 3  # search depth in plies: raise for strength, lower for speed

# Search state for the current search (module-level until Phase 5 of the plan).
next_move = None  # best root move found so far
nodes_explored = 0  # nodes visited, read by the benchmark


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


# ---------- Optimized Minimax with alpha-beta ----------
def find_random_move(legal_moves):
    """Return a random legal move (the GUI's fallback if the search fails)."""
    return legal_moves[random.randint(0, len(legal_moves) - 1)]


def find_best_move(gs, legal_moves, return_queue=None):
    """Return the best move for the side to move, searching MAX_DEPTH plies.

    When `return_queue` is given (the GUI runs this in a child process), the
    move is put on the queue instead of returned. Exceptions are printed and
    the first legal move is used, so the GUI never waits forever.
    """
    global next_move, nodes_explored
    next_move = None
    nodes_explored = 0

    clear_attack_cache(gs)  # start every search with an empty attack cache

    try:
        # A single legal move needs no evaluation: it is the only move
        # available regardless of what search would find, so returning it
        # immediately is free and carries zero risk. Two or three legal
        # moves is a different story -- that is a real decision (often
        # the only replies to a check), and skipping search there can
        # pick an objectively much worse move purely by coincidence of
        # move-generation order.
        if len(legal_moves) == 1:
            result = legal_moves[0]
        else:
            # The root window must be unbounded: mate scores are
            # CHECKMATE + depth, i.e. >= CHECKMATE, so a [-CHECKMATE, CHECKMATE]
            # window made the first mate found (even a slow one) cause a cutoff
            # before a faster mate further down the move list was examined.
            _ = minimax_alpha_beta(
                gs, legal_moves, MAX_DEPTH, -math.inf, math.inf, gs.white_to_move
            )
            result = next_move if next_move else legal_moves[0]
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


def minimax_alpha_beta(gs, legal_moves, depth, alpha, beta, white_to_move):
    """Minimax with alpha-beta pruning, `depth` plies deep.

    Returns the score from White's point of view and records the best move at
    the root (depth == MAX_DEPTH) in `next_move`.
    """
    global next_move, nodes_explored
    nodes_explored += 1

    # Quick terminal node check
    if depth == 0 or gs.checkmate or gs.stalemate:
        return evaluate(gs, depth)

    # Sort moves once at the beginning for better pruning
    if depth == MAX_DEPTH or depth == MAX_DEPTH - 1:
        moves = sorted(
            legal_moves,
            key=lambda m: get_move_priority(m, gs, white_to_move),
            reverse=True,
        )
    else:
        moves = legal_moves

    if white_to_move:
        max_score = -math.inf
        for move in moves:
            gs.make_move(move)
            next_moves = gs.get_legal_moves()
            score = minimax_alpha_beta(gs, next_moves, depth - 1, alpha, beta, False)
            gs.undo_move()

            if score > max_score:
                max_score = score
                if depth == MAX_DEPTH:
                    next_move = move

            alpha = max(alpha, score)
            if beta <= alpha:
                break
        return max_score
    else:
        min_score = math.inf
        for move in moves:
            gs.make_move(move)
            next_moves = gs.get_legal_moves()
            score = minimax_alpha_beta(gs, next_moves, depth - 1, alpha, beta, True)
            gs.undo_move()

            if score < min_score:
                min_score = score
                if depth == MAX_DEPTH:
                    next_move = move

            beta = min(beta, score)
            if beta <= alpha:
                break
        return min_score
