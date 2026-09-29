"""Tests for GUI logic that can run without a window (pygame's dummy driver)."""

import os
import queue

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


@pytest.fixture
def app():
    """The game window on pygame's dummy video driver. Both sides are human,
    so no AI process starts, and moves are not animated."""
    window = gui.App()
    window.white_is_human = window.black_is_human = True
    window.animate = False
    yield window
    pygame.quit()


@pytest.fixture
def ai_processes(monkeypatch):
    """Replaces the AI's search process with FakeAIProcess; returns the list
    of processes the window starts."""
    started = []

    class FakeAIProcess:
        """Runs the real search target, but only when the test calls answer()."""

        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self.target, self.args, self.kwargs = target, args, kwargs or {}
            self.daemon = daemon
            self.alive = self.terminated = False
            started.append(self)

        def start(self):
            self.alive = True

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.alive, self.terminated = False, True

        def join(self, timeout=None):
            pass

        def answer(self):
            """Search (1 ply, to be quick) and end, as the real process does."""
            self.target(
                *self.args, **{**self.kwargs, "max_depth": 1, "time_limit": None}
            )
            self.alive = False

    monkeypatch.setattr(gui, "Process", FakeAIProcess)
    monkeypatch.setattr(gui, "Queue", queue.Queue)
    return started


def centre(name):
    """Screen position of the centre of square `name`, White at the bottom."""
    row, col = 8 - int(name[1]), ord(name[0]) - ord("a")
    return (
        gui.EVAL_BAR_WIDTH + col * gui.SQ_SIZE + gui.SQ_SIZE // 2,
        row * gui.SQ_SIZE + gui.SQ_SIZE // 2,
    )


def click(app, name):
    app.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=centre(name), button=1)
    )


def press(app, key):
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


def coordinates(gs):
    return [move.coordinate_notation() for move in gs.move_log]


class TestApp:
    def test_a_piece_then_a_square_it_can_reach_plays_the_move(self, app):
        click(app, "e2")
        click(app, "e4")
        assert coordinates(app.gs) == ["e2e4"]
        assert app.state == gui.HUMAN_TURN  # Black, also human, to move

    def test_picking_a_piece(self, app):
        click(app, "e2")
        assert app.selected == (6, 4)
        click(app, "d2")  # another own piece
        assert app.selected == (6, 3)
        click(app, "d2")  # the same piece again
        assert app.selected is None
        click(app, "e7")  # an opponent's piece
        assert app.selected is None
        click(app, "e2")
        click(app, "e5")  # a square the pawn cannot reach
        assert app.selected is None
        assert not app.gs.move_log

    def test_a_move_slides_into_place_before_the_game_goes_on(self, app):
        app.animate = True
        click(app, "e2")
        click(app, "e4")
        assert app.state == gui.ANIMATING
        click(app, "e7")  # input waits for the animation
        assert app.selected is None
        move, started = app.animation
        app.animation = (move, started - gui.animation_seconds(move))  # time is up
        app.update()
        assert app.state == gui.HUMAN_TURN

    def test_the_ai_replies_from_its_own_process(self, app, ai_processes):
        app.black_is_human = False
        click(app, "e2")
        click(app, "e4")
        assert app.state == gui.AI_THINKING
        (process,) = ai_processes
        app.update()
        assert app.state == gui.AI_THINKING  # still searching
        process.answer()
        app.update()
        assert len(app.gs.move_log) == 2
        assert app.state == gui.HUMAN_TURN

    def test_undo_while_the_ai_is_thinking_stops_it(self, app, ai_processes):
        app.black_is_human = False
        click(app, "e2")
        click(app, "e4")
        press(app, pygame.K_z)
        assert ai_processes[0].terminated
        assert not app.gs.move_log
        assert app.state == gui.HUMAN_TURN

    def test_a_new_game_while_the_ai_is_thinking_stops_it(self, app, ai_processes):
        app.black_is_human = False
        click(app, "e2")
        click(app, "e4")
        press(app, pygame.K_r)
        assert ai_processes[0].terminated
        assert not app.gs.move_log
        assert app.state == gui.HUMAN_TURN

    def test_the_ai_process_never_outlives_the_window(self, app, ai_processes):
        app.black_is_human = False
        click(app, "e2")
        click(app, "e4")
        (process,) = ai_processes
        assert process.daemon  # ends with the program, whatever happens
        app.close()
        assert process.terminated

    def test_closing_the_window_while_the_ai_thinks_stops_it(self, app, ai_processes):
        """Finding G9: the program used to live on until the search finished."""
        app.black_is_human = False
        click(app, "e2")
        click(app, "e4")
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        app.run()
        assert ai_processes[0].terminated

    def test_an_ai_process_that_ends_without_answering(
        self, app, ai_processes, monkeypatch
    ):
        monkeypatch.setattr(gui, "AI_ANSWER_TIMEOUT", 0.01)
        app.black_is_human = False
        click(app, "e2")
        click(app, "e4")
        ai_processes[0].alive = False  # it ended, but never put a move
        app.update()
        assert len(app.gs.move_log) == 2  # a legal move instead of a hang
        assert app.state == gui.HUMAN_TURN

    def test_game_over(self, app, legal_move):
        for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
            app._play(legal_move(app.gs, move))
        assert app.state == gui.GAME_OVER
        assert gui.game_over_text(app.gs) == "Black wins by checkmate"
        click(app, "e2")  # no more moves
        assert app.selected is None


class TestPromotionPicker:
    """Finding G2: a human's pawn always became a queen."""

    WHITE_PAWN_ON_A7 = "4k3/P7/8/8/8/8/8/4K3 w - -"

    @pytest.mark.parametrize(
        ("choice", "piece"), [("a8", "Q"), ("a7", "R"), ("a6", "B"), ("a5", "N")]
    )
    def test_each_piece_can_be_chosen(self, app, choice, piece):
        app.new_game(self.WHITE_PAWN_ON_A7)
        click(app, "a7")
        click(app, "a8")
        assert app.state == gui.PROMOTING
        assert not app.gs.move_log  # nothing is played before the choice
        click(app, choice)  # the picker runs down from a8: Q, R, B, N
        assert coordinates(app.gs) == ["a7a8" + piece.lower()]
        assert app.gs.board[0][0] == "w" + piece

    def test_black_promotes_with_a_picker_running_up_the_board(self, app):
        app.new_game("4k3/8/8/8/8/8/p7/4K3 b - -")
        click(app, "a2")
        click(app, "a1")
        assert app.state == gui.PROMOTING
        click(app, "a3")  # a1 queen, a2 rook, a3 bishop, a4 knight
        assert coordinates(app.gs) == ["a2a1b"]

    def test_a_capture_can_promote_too(self, app):
        app.new_game("1r2k3/P7/8/8/8/8/8/4K3 w - -")
        click(app, "a7")
        click(app, "b8")
        click(app, "b5")  # the fourth square of the b-file column: a knight
        assert coordinates(app.gs) == ["a7b8n"]

    def test_escape_or_a_click_elsewhere_cancels(self, app):
        app.new_game(self.WHITE_PAWN_ON_A7)
        for cancel in (lambda: press(app, pygame.K_ESCAPE), lambda: click(app, "h1")):
            click(app, "a7")
            click(app, "a8")
            cancel()
            assert app.state == gui.HUMAN_TURN
            assert app.selected is None
            assert not app.gs.move_log

    def test_undo_closes_the_picker(self, app, legal_move):
        app.new_game(self.WHITE_PAWN_ON_A7)
        app._play(legal_move(app.gs, "e1d1"))
        app._play(legal_move(app.gs, "e8d8"))
        click(app, "a7")
        click(app, "a8")
        press(app, pygame.K_z)
        assert app.state == gui.HUMAN_TURN
        assert app.promotion_moves == []


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
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self.args = args

        def start(self):
            gs, legal_moves, queue = self.args
            wanted = moves[len(gs.move_log)]
            queue.put(next(m for m in legal_moves if m.coordinate_notation() == wanted))

        def is_alive(self):
            return False

        def terminate(self):
            pass

        def join(self, timeout=None):
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
