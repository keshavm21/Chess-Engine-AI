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


def play_scripted_game(monkeypatch, moves, max_frames=600):
    """Run the real GUI loop (gui.main) headlessly. White's moves are clicked on
    the board; Black's come from a stand-in for the AI process. Returns the
    end-of-game messages the GUI drew and the final GameState."""
    games = []
    real_game_state = gui.GameState

    def recording_game_state(*args, **kwargs):
        games.append(real_game_state(*args, **kwargs))
        return games[-1]

    class ScriptedAIProcess:
        def __init__(self, target=None, args=(), kwargs=None):
            self.args = args

        def start(self):
            gs, legal_moves, queue = self.args
            wanted = moves[len(gs.move_log)]
            queue.put(next(m for m in legal_moves if m.coordinate_notation() == wanted))

        def is_alive(self):
            return False

        def terminate(self):
            pass

    messages = []
    real_end_text = gui.draw_end_game_text

    def recording_end_text(screen, text):
        messages.append(text)
        real_end_text(screen, text)

    state = {"frames": 0, "clicks": [], "pos": (0, 0), "quit_in": None}

    def centre(name):
        row, col = 8 - int(name[1]), ord(name[0]) - ord("a")
        return (
            gui.EVAL_BAR_WIDTH + col * gui.SQ_SIZE + gui.SQ_SIZE // 2,
            row * gui.SQ_SIZE + gui.SQ_SIZE // 2,
        )

    def events(*args, **kwargs):
        state["frames"] += 1
        gs = games[-1] if games else None
        out = []
        if state["clicks"]:
            state["pos"] = state["clicks"].pop(0)
            out.append(
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=state["pos"], button=1)
            )
        elif gs and not messages and gs.white_to_move and len(gs.move_log) < len(moves):
            move = moves[len(gs.move_log)]
            state["clicks"] = [centre(move[:2]), centre(move[2:4])]
        finished = messages or (gs and len(gs.move_log) >= len(moves))
        if finished and state["quit_in"] is None:
            state["quit_in"] = 5  # let the GUI draw a few more frames
        if state["quit_in"] is not None:
            state["quit_in"] -= 1
        if state["quit_in"] == 0 or state["frames"] > max_frames:
            out.append(pygame.event.Event(pygame.QUIT))
        return out

    monkeypatch.setattr(gui, "GameState", recording_game_state)
    monkeypatch.setattr(gui, "Process", ScriptedAIProcess)
    monkeypatch.setattr(gui, "draw_end_game_text", recording_end_text)
    monkeypatch.setattr(pygame.event, "get", events)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: state["pos"])
    gui.main()
    return messages, games[-1]


@pytest.mark.slow
@pytest.mark.parametrize(
    ("moves", "draw_at_ply"),
    [
        pytest.param(
            "e2e4 e7e6 d1g4 e8e7 g4g5 e7e8 g5g4 e8e7 g4g5 e7e8 g5g4 e8e7 g4g5 e7e8",
            12,
            id="repetition-with-checks",
        ),
        pytest.param(
            "e2e4 g8f6 g1f3 f6g8 f3g1 g8f6 g1f3 f6g8 f3g1 g8f6 g1f3 f6g8 f3g1",
            9,
            id="first-occurrence-after-e4",
        ),
    ],
)
def test_the_game_window_declares_threefold_repetition(monkeypatch, moves, draw_at_ply):
    messages, gs = play_scripted_game(monkeypatch, moves.split())
    assert messages and messages[-1] == "Draw by threefold repetition"
    assert len(gs.move_log) == draw_at_ply  # the game stopped at the draw
