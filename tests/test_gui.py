"""Tests for GUI logic that can run without a window (pygame's dummy driver)."""

import os
import queue

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from chess_ai import gui, search  # noqa: E402  (needs the SDL settings above)
from chess_ai.engine import GameState  # noqa: E402
from chess_ai.evaluation import CHECKMATE  # noqa: E402

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
        app.new_game(fen=self.WHITE_PAWN_ON_A7)
        click(app, "a7")
        click(app, "a8")
        assert app.state == gui.PROMOTING
        assert not app.gs.move_log  # nothing is played before the choice
        click(app, choice)  # the picker runs down from a8: Q, R, B, N
        assert coordinates(app.gs) == ["a7a8" + piece.lower()]
        assert app.gs.board[0][0] == "w" + piece

    def test_black_promotes_with_a_picker_running_up_the_board(self, app):
        app.new_game(fen="4k3/8/8/8/8/8/p7/4K3 b - -")
        click(app, "a2")
        click(app, "a1")
        assert app.state == gui.PROMOTING
        click(app, "a3")  # a1 queen, a2 rook, a3 bishop, a4 knight
        assert coordinates(app.gs) == ["a2a1b"]

    def test_a_capture_can_promote_too(self, app):
        app.new_game(fen="1r2k3/P7/8/8/8/8/8/4K3 w - -")
        click(app, "a7")
        click(app, "b8")
        click(app, "b5")  # the fourth square of the b-file column: a knight
        assert coordinates(app.gs) == ["a7b8n"]

    def test_escape_or_a_click_elsewhere_cancels(self, app):
        app.new_game(fen=self.WHITE_PAWN_ON_A7)
        for cancel in (lambda: press(app, pygame.K_ESCAPE), lambda: click(app, "h1")):
            click(app, "a7")
            click(app, "a8")
            cancel()
            assert app.state == gui.HUMAN_TURN
            assert app.selected is None
            assert not app.gs.move_log

    def test_undo_closes_the_picker(self, app, legal_move):
        app.new_game(fen=self.WHITE_PAWN_ON_A7)
        app._play(legal_move(app.gs, "e1d1"))
        app._play(legal_move(app.gs, "e8d8"))
        click(app, "a7")
        click(app, "a8")
        press(app, pygame.K_z)
        assert app.state == gui.HUMAN_TURN
        assert app.promotion_moves == []


class TestSquareMarks:
    """Finding G6: no last-move or check highlight."""

    def test_the_last_move_is_marked(self, app):
        assert app.square_marks() == []
        click(app, "e2")
        click(app, "e4")
        assert app.square_marks() == [("last move", (6, 4)), ("last move", (4, 4))]

    def test_the_last_move_is_drawn(self, app):
        click(app, "e2")
        click(app, "e4")
        app.draw()
        e2, d3 = gui.square_rect((6, 4)).center, gui.square_rect((5, 3)).center
        assert app.screen.get_at(d3) == gui.LIGHT_SQUARE  # empty, not marked
        assert app.screen.get_at(e2) != gui.LIGHT_SQUARE  # empty, but tinted

    def test_a_king_in_check_is_marked(self, app):
        app.new_game(fen="4k3/8/8/8/8/8/8/4R1K1 b - -")
        assert ("check", (0, 4)) in app.square_marks()

    def test_the_picked_piece_shows_its_moves_and_captures(self, app):
        app.new_game(fen="4k3/8/8/3p4/4P3/8/8/4K3 w - -")
        click(app, "e4")
        assert sorted(app.square_marks()) == [
            ("capture", (3, 3)),  # exd5
            ("move", (3, 4)),  # e5
            ("selected", (4, 4)),
        ]

    def test_a_promotion_square_is_marked_once(self, app):
        app.new_game(fen="4k3/P7/8/8/8/8/8/4K3 w - -")
        click(app, "a7")
        assert app.square_marks().count(("move", (0, 0))) == 1  # not 4 times

    def test_drawing_every_state(self, app, ai_processes):
        """Smoke test: every state draws without errors."""
        app.new_game(fen="4k3/P7/8/8/8/8/8/4K2R w K -")
        click(app, "a7")
        app.draw()  # a piece picked
        click(app, "a8")
        app.draw()  # the promotion picker
        press(app, pygame.K_ESCAPE)
        app.animate = True
        click(app, "h1")
        click(app, "h7")
        app.draw()  # animating
        app.new_game(fen="4k3/8/8/8/8/8/8/4R1K1 b - -")
        app.draw()  # a king in check
        app.new_game(fen="7k/5Q2/6K1/8/8/8/8/8 b - -")
        app.draw()  # game over: stalemate
        app.black_is_human = False
        app.new_game()
        click(app, "e2")
        click(app, "e4")
        app.update()  # the move slides into place ...
        app.animation = (app.animation[0], 0.0)
        app.update()  # ... and the AI starts thinking
        assert app.state == gui.AI_THINKING
        app.draw()


class TestSidesAndLevels:
    """Finding G7: always White, no difficulty choice, no board flip."""

    @pytest.mark.parametrize("flipped", [False, True])
    def test_squares_and_screen_positions_match(self, flipped):
        for row in range(8):
            for col in range(8):
                rect = gui.square_rect((row, col), flipped)
                assert gui.square_at(rect.center, flipped) == (row, col)
                assert gui.square_at(rect.topleft, flipped) == (row, col)
        board_top_left = (gui.EVAL_BAR_WIDTH, 0)
        assert gui.square_at(board_top_left, flipped) == ((7, 7) if flipped else (0, 0))
        assert gui.square_at((gui.EVAL_BAR_WIDTH - 1, 0), flipped) is None  # eval bar
        assert gui.square_at((gui.PANEL_LEFT, 0), flipped) is None  # side panel

    def test_playing_black_flips_the_board_and_the_ai_opens(self, app, ai_processes):
        app.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, pos=gui.BUTTONS["black"].center, button=1
            )
        )
        assert app.flipped
        assert (app.white_is_human, app.black_is_human) == (False, True)
        assert app.state == gui.AI_THINKING
        ai_processes[0].answer()
        app.update()
        assert app.state == gui.HUMAN_TURN
        # The human now clicks where e7 and e5 are shown: near the bottom.
        e7, e5 = gui.square_rect((1, 4), flipped=True), gui.square_rect((3, 4), True)
        assert e7.bottom > gui.BOARD_HEIGHT // 2
        for rect in (e7, e5):
            app.handle_event(
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)
            )
        assert coordinates(app.gs)[-1] == "e7e5"

    @pytest.mark.parametrize("level", list(search.DIFFICULTIES))
    def test_the_level_sets_the_ai_search_limits(self, app, ai_processes, level):
        app.black_is_human = False
        app.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, pos=gui.BUTTONS[level].center, button=1
            )
        )
        assert app.difficulty == level
        click(app, "e2")
        click(app, "e4")
        limits = search.DIFFICULTIES[level]
        assert ai_processes[0].kwargs == {
            "max_depth": limits.max_depth,
            "time_limit": limits.time_limit,
        }

    def test_flip_only_turns_the_board(self, app):
        click(app, "e2")
        press(app, pygame.K_f)
        assert app.flipped
        assert app.selected == (6, 4)  # the same piece stays picked
        assert app.white_is_human
        press(app, pygame.K_f)
        assert not app.flipped

    def test_a_new_game_keeps_the_side_and_level(self, app, ai_processes):
        app.new_game(human_plays_white=False)
        app.difficulty = "hard"
        press(app, pygame.K_r)
        assert app.flipped and not app.human_plays_white
        assert app.difficulty == "hard"

    @pytest.mark.parametrize("flipped", [False, True])
    def test_the_evaluation_bar_grows_from_whites_side(self, flipped):
        pygame.init()
        screen = pygame.Surface(gui.WINDOW_SIZE)
        font = pygame.font.SysFont("Arial", 12)
        top, bottom = (5, 60), (5, gui.BOARD_HEIGHT - 60)
        whites_end, blacks_end = (top, bottom) if flipped else (bottom, top)
        gui.draw_evaluation_bar(screen, 300, font, flipped)  # White is better
        assert screen.get_at(whites_end) == gui.EVAL_WHITE
        assert screen.get_at(blacks_end) == gui.EVAL_BLACK
        gui.draw_evaluation_bar(screen, -(CHECKMATE - 3), font, flipped)  # mated
        assert screen.get_at(whites_end) == gui.EVAL_BLACK


@pytest.mark.parametrize(
    ("score", "text"),
    [
        (35, "+0.35"),
        (-120, "-1.20"),
        (0, "+0.00"),
        (CHECKMATE - 1, "+M1"),  # White mates on the next ply
        (CHECKMATE - 3, "+M2"),
        (-(CHECKMATE - 2), "-M1"),  # Black mates with its next move
        (-(CHECKMATE - 4), "-M2"),
    ],
)
def test_format_score(score, text):
    assert gui.format_score(score) == text


def test_describe_search():
    assert gui.describe_search(None) == ""
    result = search.SearchResult(None, -35, 5, 12345, 100, 1.94)
    assert gui.describe_search(result) == "AI: depth 5, eval -0.35, 1.9 s"
    only_move = search.SearchResult(None, None, 0, 0, 0, 0.0)
    assert gui.describe_search(only_move) == "AI: the only legal move"


class TestStatusLines:
    def test_the_players(self, app, ai_processes):
        assert app.status_lines()[1] == "You play White against the medium AI"
        app.difficulty = "hard"
        app.new_game(human_plays_white=False)
        assert app.status_lines()[1] == "You play Black against the hard AI"

    def test_through_a_game_against_the_ai(self, app, ai_processes):
        app.black_is_human = False
        assert app.status_lines()[0] == "Your move"
        click(app, "e2")
        click(app, "e4")
        assert app.status_lines()[0].startswith("AI is thinking... ")
        assert app.status_lines()[2] == ""
        ai_processes[0].answer()
        app.update()
        headline, _, search_info = app.status_lines()
        assert headline == "Your move"
        assert search_info.startswith("AI: depth 1, eval ")
        press(app, pygame.K_z)
        assert app.status_lines()[2] == ""  # it was about a move taken back

    def test_check_promotion_and_game_over(self, app):
        app.new_game(fen="4k3/P7/8/8/8/8/8/4K2R b K -")
        click(app, "e8")
        click(app, "d7")
        assert app.status_lines()[0] == "Your move"
        click(app, "h1")
        click(app, "h7")
        assert app.status_lines()[0] == "Check! Your move"
        click(app, "d7")
        click(app, "c8")
        click(app, "a7")
        click(app, "a8")
        assert app.status_lines()[0] == "Choose the promotion piece"
        click(app, "a8")  # a queen: mate, as the rook on h7 guards the 7th rank
        assert coordinates(app.gs)[-1] == "a7a8q"
        assert app.status_lines()[0] == "White wins by checkmate"
        app.new_game(fen="7k/5Q2/6K1/8/8/8/8/8 b - -")
        assert app.status_lines()[0] == "Stalemate"


def test_move_log_lines():
    assert gui.move_log_lines([]) == []
    assert gui.move_log_lines(["e4", "e5", "Nf3"]) == [
        ("1.", "e4", "e5"),
        ("2.", "Nf3", ""),
    ]
    assert gui.move_log_lines(["Kd7", "Rh7+"], 40, black_first=True) == [
        ("40.", "...", "Kd7"),
        ("41.", "Rh7+", ""),
    ]


class TestMoveLog:
    """Finding G3: the log had no check marks or disambiguation, and long games
    ran off the panel."""

    # Giuoco Piano, Moller attack: 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3 Nf6 5.d4
    # exd4 6.cxd4 Bb4+ 7.Nc3 Nxe4 8.O-O Bxc3 9.d5 Bf6 10.Re1 Ne7 11.Rxe4 d6
    # 12.Bg5 Bxg5 13.Nxg5 O-O
    GAME = (
        "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6 d2d4 e5d4 c3d4 c5b4 b1c3 "
        "f6e4 e1g1 b4c3 d4d5 c3f6 f1e1 c6e7 e1e4 d7d6 c1g5 f6g5 f3g5 e8g8"
    ).split()
    SAN = (
        "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d4 exd4 cxd4 Bb4+ Nc3 Nxe4 O-O Bxc3 "
        "d5 Bf6 Re1 Ne7 Rxe4 d6 Bg5 Bxg5 Nxg5 O-O"
    ).split()

    def play(self, app, moves):
        for move in moves:
            click(app, move[:2])
            click(app, move[2:4])

    def test_moves_are_written_in_san(self, app):
        self.play(app, self.GAME)
        assert app.san_log == self.SAN
        assert app.log_lines()[-1] == ("13.", "Nxg5", "O-O")

    def test_the_ai_and_the_promotion_picker_write_san_too(self, app, ai_processes):
        fen = "4k3/P7/8/8/8/8/8/4K3 w - -"
        app.new_game(fen=fen)
        app.black_is_human = False
        self.play(app, ["a7a8"])
        click(app, "a7")  # the rook, second in the picker
        ai_processes[0].answer()
        app.update()
        promotion, reply = app.gs.move_log
        replay = GameState.from_fen(fen)
        replay.make_move(promotion)
        assert app.san_log == ["a8=R+", replay.san(reply)]
        assert app.san_log[1].startswith("K")  # the king must leave the check

    def test_undo_takes_the_moves_off_the_log(self, app):
        self.play(app, self.GAME[:3])
        press(app, pygame.K_z)
        assert app.san_log == ["e4", "e5"]

    def test_a_game_from_a_position_with_black_to_move(self, app):
        app.new_game(fen="4k3/8/8/8/8/8/8/4K2R b K - 0 40")
        self.play(app, ["e8d7", "h1h7"])
        assert app.log_lines() == [("40.", "...", "Kd7"), ("41.", "Rh7+", "")]

    def test_the_log_follows_the_game_and_scrolls_back(self, app):
        wheel = pygame.MOUSEWHEEL
        self.play(app, self.GAME[:-2])  # 12 lines, one more than fit
        assert gui.LOG_CAPACITY == 11
        lines, first = app.visible_log_lines()
        assert (lines[0][0], lines[-1][0], first) == ("2.", "12.", 1)
        app.handle_event(pygame.event.Event(wheel, x=0, y=5))  # back
        lines, first = app.visible_log_lines()
        assert (lines[0][0], first, app.log_scroll) == ("1.", 0, 1)  # no further
        app.handle_event(pygame.event.Event(wheel, x=0, y=-5))  # forward
        assert app.log_scroll == 0
        app.handle_event(pygame.event.Event(wheel, x=0, y=1))
        self.play(app, self.GAME[-2:])  # a new move shows the newest again
        assert app.log_scroll == 0
        assert app.visible_log_lines()[0][-1] == ("13.", "Nxg5", "O-O")


def play_scripted_game(monkeypatch, moves, human_plays_white=True, max_frames=600):
    """Run the real GUI loop (gui.main) headlessly. The human's moves are
    clicked on the board (to play Black, the "Black" button is clicked first);
    the AI's come from a stand-in for its process. Returns the end-of-game
    messages the GUI drew and the final GameState."""
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
            move = next(m for m in legal_moves if m.coordinate_notation() == wanted)
            queue.put(search.SearchResult(move, 0, 1, 1, 0, 0.0))

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
    if not human_plays_white:
        state["clicks"] = [gui.BUTTONS["black"].center]

    def centre(name):
        row, col = 8 - int(name[1]), ord(name[0]) - ord("a")
        if not human_plays_white:  # the board is shown with Black at the bottom
            row, col = 7 - row, 7 - col
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
        elif (
            gs
            and not messages
            and gs.white_to_move == human_plays_white
            and len(gs.move_log) < len(moves)
        ):
            move = moves[len(gs.move_log)]
            state["clicks"] = [centre(move[:2]), centre(move[2:4])]
        if messages and (state["quit_in"] is None or state["quit_in"] > 5):
            state["quit_in"] = 5  # let the GUI draw a few more frames
        elif gs and len(gs.move_log) >= len(moves) and state["quit_in"] is None:
            state["quit_in"] = 60  # time for the last move to slide into place
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


@pytest.mark.slow
def test_a_game_as_black_in_the_game_window(monkeypatch):
    """Black is chosen with its button, the board is flipped, the AI opens."""
    messages, gs = play_scripted_game(
        monkeypatch, "f2f3 e7e5 g2g4 d8h4".split(), human_plays_white=False
    )
    assert messages and messages[-1] == "Black wins by checkmate"
    assert len(gs.move_log) == 4
