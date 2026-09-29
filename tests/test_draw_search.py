"""The search treats draws by rule as draws."""

from chess_ai import search
from chess_ai.engine import GameState

LOST_FOR_BLACK = "7k/8/8/8/8/8/8/3Q2K1 b - -"  # White is a queen up


def play(gs, legal_move, *moves):
    for coordinates in moves:
        gs.make_move(legal_move(gs, coordinates))


def test_the_losing_side_heads_for_a_repetition(legal_move):
    """After Kg8 Qd2 Kh8 Qd1 the position is back where it started. Kg8 now
    repeats a position, which the search scores as a draw: Black, a queen
    down, should take it."""
    gs = GameState.from_fen(LOST_FOR_BLACK)
    play(gs, legal_move, "h8g8", "d1d2", "g8h8", "d2d1")
    result = search.Searcher(max_depth=3).search(gs)
    assert result.move.coordinate_notation() == "h8g8"
    assert result.score == 0


def test_without_history_the_same_position_is_lost():
    result = search.Searcher(max_depth=3).search(GameState.from_fen(LOST_FOR_BLACK))
    assert result.score > 500  # White is winning (scores are White's view)


def test_the_winning_side_avoids_a_repetition(legal_move):
    gs = GameState.from_fen(LOST_FOR_BLACK)
    play(gs, legal_move, "h8g8", "d1d2", "g8h8")
    # White to move: Qd1 would repeat the starting position.
    result = search.Searcher(max_depth=3).search(gs)
    assert result.move.coordinate_notation() != "d2d1"
    assert result.score > 500


def test_the_engine_does_not_trade_into_insufficient_material():
    """Black's last pawn on d5 is free, but taking it leaves K+N v K, which
    cannot be won: the engine keeps the pawn on the board instead of scoring
    the capture as a knight up."""
    fen = "8/8/8/3p4/8/4N3/8/k3K3 w - -"
    result = search.Searcher(max_depth=2).search(GameState.from_fen(fen))
    assert result.move.coordinate_notation() != "e3d5"
    assert result.score > 150  # K+N v K+P still counts as better for White


def test_evaluate_position_shows_draws_by_rule_as_level():
    assert (
        search.evaluate_position(GameState.from_fen("4k3/8/8/8/8/8/8/3NK3 w - -")) == 0
    )
    fifty = GameState.from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 100 90")
    assert search.evaluate_position(fifty) == 0
