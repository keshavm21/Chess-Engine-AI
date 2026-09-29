"""Tests for GUI logic that can run without a window (pygame's dummy driver)."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from chess_ai import gui  # noqa: E402  (needs the SDL settings above)
from chess_ai.engine import GameState  # noqa: E402

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def play(gs, legal_move, *moves):
    for coordinates in moves:
        gs.make_move(legal_move(gs, coordinates))


class TestTakeBackMove:
    """Finding G1: pressing Z against the AI used to undo only the AI's reply,
    after which the AI immediately played again."""

    def test_after_the_ai_replied_both_moves_are_taken_back(self, legal_move):
        gs = GameState()
        play(gs, legal_move, "e2e4", "e7e5")  # human (White), then AI (Black)

        gui.take_back_move(gs, white_is_human=True, black_is_human=False)

        assert gs.to_fen() == START

    def test_while_the_ai_is_thinking_only_the_human_move_is_taken_back(
        self, legal_move
    ):
        gs = GameState()
        play(gs, legal_move, "e2e4")  # the AI has not replied yet

        gui.take_back_move(gs, white_is_human=True, black_is_human=False)

        assert gs.to_fen() == START

    def test_human_playing_black(self, legal_move):
        gs = GameState()
        play(gs, legal_move, "e2e4", "e7e5", "g1f3")  # AI, human, AI

        gui.take_back_move(gs, white_is_human=False, black_is_human=True)

        assert gs.to_fen().startswith("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/")
        assert not gs.white_to_move  # the human (Black) is to move again

    def test_two_humans_undo_one_move_at_a_time(self, legal_move):
        gs = GameState()
        play(gs, legal_move, "e2e4", "e7e5")

        gui.take_back_move(gs, white_is_human=True, black_is_human=True)

        assert len(gs.move_log) == 1

    def test_nothing_to_undo(self):
        gs = GameState()
        gui.take_back_move(gs, white_is_human=True, black_is_human=False)
        assert gs.to_fen() == START


class RecordingScreen:
    """Stands in for the display surface and records where things are drawn."""

    def __init__(self):
        self.blits = []

    def blit(self, surface, dest):
        # blit() only uses the top-left of `dest`; the drawn area has the
        # size of the surface being drawn.
        topleft = pygame.Rect(dest).topleft
        self.blits.append(pygame.Rect(topleft, surface.get_size()))


def test_end_game_text_is_centred_on_the_board():
    """Finding G4: the message used to be drawn 40 px right of centre."""
    pygame.font.init()
    screen = RecordingScreen()

    gui.draw_end_game_text(screen, "White wins by checkmate")

    text_rect = screen.blits[0]
    board_centre = (gui.EVAL_BAR_WIDTH + gui.BOARD_WIDTH // 2, gui.BOARD_HEIGHT // 2)
    assert abs(text_rect.centerx - board_centre[0]) <= 1
    assert abs(text_rect.centery - board_centre[1]) <= 1
