"""Regression tests for evaluation.get_all_attacks() and its cache.

Two bugs were fixed in commit cad80b8:

1. The cache was keyed on id(gs.board). GameState mutates its board in
   place, so the id never changes and every later position was served the
   attack set of the first position that was cached.
2. Asking for the attacks of the side *not* on move left the live
   en-passant square active. A pawn of that side could then "capture en
   passant" onto it, and the make/undo round trip left a phantom pawn on
   the board.

The first three tests fail against the pre-fix code. The fourth guards the
fix itself: the en-passant square it temporarily suppresses must be
restored afterwards.
"""

from chess_ai import evaluation


def fresh_attacks(gs, white):
    """get_all_attacks() computed with an empty cache, leaving any existing
    cache on `gs` untouched."""
    saved = gs.__dict__.pop("_attack_cache", None)
    try:
        return evaluation.get_all_attacks(gs, white)
    finally:
        if saved is None:
            gs.__dict__.pop("_attack_cache", None)
        else:
            gs._attack_cache = saved


def test_cached_attacks_follow_the_position_as_moves_are_made(load_fen, legal_move):
    """The same GameState (and board list object) is reused across moves;
    the cached answer must always match a fresh computation."""
    gs = load_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -")

    start_white = evaluation.get_all_attacks(gs, True)
    for coordinates in ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4"):
        gs.make_move(legal_move(gs, coordinates))
        for white in (True, False):
            cached = evaluation.get_all_attacks(gs, white)
            assert cached == fresh_attacks(gs, white), (
                f"stale cached attacks after {coordinates} (white={white})"
            )

    assert evaluation.get_all_attacks(gs, True) != start_white


def test_en_passant_square_is_part_of_the_cache_key(load_fen):
    """Same board, with and without an en-passant target: the exd6 capture
    square must only appear when en passant is actually available."""
    gs = load_fen("4k3/8/8/3pP3/8/8/8/4K3 w - d6")
    d6 = (2, 3)

    assert d6 in evaluation.get_all_attacks(gs, True)

    gs.en_passant_square = ()
    assert d6 not in evaluation.get_all_attacks(gs, True)


def test_off_turn_query_does_not_invent_en_passant_captures(load_fen, state_snapshot):
    """Black to move after White's d2-d4 (en-passant square d3). Asking what
    *White* attacks must not let the c2/e2 pawns "capture en passant" on d3,
    which would leave a phantom black pawn on d2 after undo."""
    gs = load_fen("4k3/8/8/8/3P4/8/2P1P3/4K3 b - d3")
    before = state_snapshot(gs)

    white_attacks = evaluation.get_all_attacks(gs, True)

    assert state_snapshot(gs) == before
    assert (5, 3) not in white_attacks  # d3


def test_off_turn_query_preserves_side_to_move_and_en_passant(load_fen):
    gs = load_fen("4k3/8/8/3pP3/8/8/8/4K3 w - d6")

    evaluation.get_all_attacks(gs, False)

    assert gs.white_to_move is True
    assert gs.en_passant_square == (2, 3)


def test_off_turn_query_leaves_game_over_flags_alone(load_fen):
    """Regression test for finding R5. White to move, not stalemated. Black
    *would* be stalemated if it were Black's turn, but asking for Black's
    attacks must not mark the current position as stalemate."""
    gs = load_fen("7k/5Q2/6K1/8/8/8/8/8 w - -")
    gs.update_game_status()
    assert (gs.checkmate, gs.stalemate) == (False, False)

    evaluation.get_all_attacks(gs, False)

    assert (gs.checkmate, gs.stalemate) == (False, False)
