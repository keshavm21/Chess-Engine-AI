"""Regression tests for the search (search.Searcher / search.find_best_move)."""

import time

import pytest

from chess_ai import search
from chess_ai.evaluation import CHECKMATE


def best_move(gs):
    return search.find_best_move(gs, list(gs.get_legal_moves()))


def delivers_checkmate(gs, move):
    """True if playing `move` checkmates the opponent. Leaves `gs` unchanged."""
    gs.make_move(move)
    gs.update_game_status()
    mated = gs.checkmate
    gs.undo_move()
    return mated


def test_three_legal_moves_finds_the_free_queen_capture(load_fen):
    """r1bqkbr1/pp1p2pp/n3pp2/2p4Q/7P/3PP1n1/PPP2PP1/RNB1KBNR b Q -

    Black is in check from the White queen on h5 (it checks along the
    h5-e8 diagonal). Black has exactly three legal replies: Ke7, g6, or
    Nxh5 -- and Nxh5 both captures the checking queen outright *and*
    resolves the check in the same move. legal_moves[0] (board-scan
    order) is Ke7, a mere retreat that leaves the queen on the board.
    This holds regardless of whether the attack-cache fix has also been
    applied (verified against all four fix combinations), unlike an
    earlier candidate position that turned out to be sensitive to it.
    """
    gs = load_fen("r1bqkbr1/pp1p2pp/n3pp2/2p4Q/7P/3PP1n1/PPP2PP1/RNB1KBNR b Q -")

    moves = gs.get_legal_moves()
    assert len(moves) == 3, f"expected exactly 3 legal moves, got {len(moves)}"
    assert moves[0].coordinate_notation() == "e8e7", (
        "this test assumes legal_moves[0] is the king retreat (Ke7); if "
        "move-generation order changed, re-verify which index the "
        "shortcut would actually return."
    )

    chosen = search.find_best_move(gs, list(moves))

    assert chosen.piece_moved == "bN" and chosen.end_row == 3 and chosen.end_col == 7, (
        f"expected the knight to capture the checking queen on h5 "
        f"(Nxh5), but the engine chose {chosen.piece_moved} to "
        f"{chr(ord('a') + chosen.end_col)}{8 - chosen.end_row} -- a <=3-style "
        f"shortcut (or an equivalent regression) is picking a move "
        f"without evaluating it."
    )


def test_single_legal_move_is_still_immediate(load_fen):
    """A position with exactly one legal move should still return
    instantly without needing to run the full search -- that part of the
    original shortcut was sound and should be kept."""
    gs = load_fen("7k/8/6K1/8/8/8/8/6R1 b - -")

    moves = gs.get_legal_moves()
    assert len(moves) == 1, f"expected exactly 1 legal move, got {len(moves)}"

    t0 = time.time()
    chosen = search.find_best_move(gs, list(moves))
    elapsed = time.time() - t0

    assert chosen is moves[0]
    assert elapsed < 0.5, (
        f"the only legal move took {elapsed:.2f}s to return -- the "
        f"single-legal-move fast path appears to have been lost."
    )


@pytest.mark.parametrize(
    ("fen", "expected"),
    [
        pytest.param("6k1/5ppp/8/8/8/8/8/R5K1 w - -", CHECKMATE - 1, id="mate-in-1"),
        pytest.param("7k/8/5K2/8/8/8/8/6R1 w - -", CHECKMATE - 3, id="mate-in-2"),
        pytest.param("r5k1/8/8/8/8/8/5PPP/6K1 b - -", -(CHECKMATE - 1), id="black-1"),
    ],
)
def test_mate_scores_count_the_plies_to_mate(fen, expected, load_fen):
    """A mate delivered `n` plies from the root scores CHECKMATE - n (from
    White's point of view, negative when Black mates), so faster mates always
    score higher and every mate has the same score at every search depth."""
    gs = load_fen(fen)
    _, score = search.Searcher().search_depth(gs, gs.get_legal_moves(), 3)
    assert score == expected


def test_finds_back_rank_mate_in_one(load_fen):
    """Control case for the mate-in-one tests below: Ra8# is the first
    checking move searched, so the engine already finds it today."""
    gs = load_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - -")
    assert delivers_checkmate(gs, best_move(gs))


@pytest.mark.parametrize(
    "fen",
    [
        pytest.param("3k4/5R2/8/2K5/4Q3/8/8/8 w - -", id="Qa8#-not-Qd5+"),
        pytest.param("8/8/1R2Q3/8/8/8/8/k1K5 w - -", id="Ra6#-not-Qe5+"),
        # The same two positions with colours swapped: Black to move and mate.
        pytest.param("8/8/8/4q3/2k5/8/5r2/3K4 b - -", id="black-Qa1#-not-Qd4+"),
        pytest.param("K1k5/8/8/8/8/1r2q3/8/8 b - -", id="black-Rb8#-not-Qe4+"),
    ],
)
def test_prefers_mate_in_one_over_slower_mate(fen, load_fen):
    """Regression test for finding S1: the root search window used to be
    [-CHECKMATE, CHECKMATE] while mate scores are >= CHECKMATE, so a slower
    mate searched first caused a cutoff before the mate in one was examined.
    In each position a checking move that mates in two is ordered before the
    mate in one."""
    gs = load_fen(fen)
    chosen = best_move(gs)
    assert delivers_checkmate(gs, chosen), (
        f"a mate in one is available but the engine chose {chosen.coordinate_notation()}"
    )


@pytest.mark.parametrize(
    "fen",
    [
        pytest.param("3k4/5R2/8/2K5/4Q3/8/8/8 w - -", id="Qa8#-not-Qd5+"),
        pytest.param("8/8/1R2Q3/8/8/8/8/k1K5 w - -", id="Ra6#-not-Qe5+"),
    ],
)
def test_single_depth_three_pass_prefers_mate_in_one(fen, load_fen):
    """The exact path of finding S1: one depth-3 pass without iterative
    deepening (which would already stop at depth 1 with the mate)."""
    gs = load_fen(fen)
    move, _ = search.Searcher().search_depth(gs, gs.get_legal_moves(), 3)
    assert delivers_checkmate(gs, move)
