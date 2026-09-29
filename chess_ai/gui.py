"""pygame front end: draws the game, handles input and runs the AI.

The window is an App that is in exactly one state at a time:

- HUMAN_TURN: the player picks a move: a piece, then a square it can reach
  (with two clicks, or by dragging the piece there),
- PROMOTING: the player picks the piece a pawn promotes to,
- AI_THINKING: the AI searches in a separate process, so the window stays
  responsive,
- ANIMATING: the last move slides into place,
- GAME_OVER: checkmate, stalemate or a draw by rule.

Every change of position (a move, an undo, a new game) goes through
App._position_changed(), which decides the next state.
"""

import math
import os
import queue
import time
from multiprocessing import Process, Queue

# pygame prints a banner when imported, unless told not to.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame as p  # noqa: E402

from chess_ai import search  # noqa: E402
from chess_ai.engine import PROMOTION_PIECES, GameState  # noqa: E402
from chess_ai.evaluation import CHECKMATE  # noqa: E402

# Piece sprites live next to this module.
IMAGE_PATH = os.path.join(os.path.dirname(__file__), "assets", "pieces")

# 400 is another good option and it depends on how good the
# images you have in terms of quality and resolution and 512 is a power of 2
BOARD_WIDTH = BOARD_HEIGHT = 512
EVAL_BAR_WIDTH = 40  # Width of evaluation bar
PANEL_WIDTH = 300  # the side panel right of the board
# the chess board is 8x8 :)
DIMENSION = 8
SQ_SIZE = BOARD_HEIGHT // DIMENSION
BOARD_LEFT = EVAL_BAR_WIDTH  # the board is drawn right of the evaluation bar
PANEL_LEFT = BOARD_LEFT + BOARD_WIDTH
WINDOW_SIZE = (PANEL_LEFT + PANEL_WIDTH, BOARD_HEIGHT)
FPS = 30
ANIMATION_FPS = 60  # while a piece slides
# How long to wait for the answer of a search process that has ended; it has
# normally written it already, but it may have died without answering.
AI_ANSWER_TIMEOUT = 1.0
IMAGES = {}
LIGHT_SQUARE = (240, 217, 181)
DARK_SQUARE = (181, 136, 99)
BOARD_COLORS = (LIGHT_SQUARE, DARK_SQUARE)  # (row + col) % 2 == 0 is light
# Square marks (RGBA): see App.square_marks().
LAST_MOVE_TINT = (205, 210, 60, 130)
SELECTED_TINT = (20, 110, 40, 110)
MOVE_HINT = (20, 85, 30, 100)  # dots and rings where the picked piece can go
CHECK_GLOW = (230, 20, 20)
EVAL_WHITE, EVAL_BLACK, EVAL_MIDLINE = (240, 240, 240), (64, 62, 58), (140, 140, 140)
PANEL_BG = (38, 36, 33)
PANEL_LINE = (70, 67, 62)
TEXT_COLOR = (232, 230, 227)
MUTED_TEXT = (155, 152, 148)
BUTTON_COLOR, BUTTON_HOVER, BUTTON_ACTIVE = (62, 59, 55), (82, 79, 74), (98, 138, 52)

# Side panel layout (y coordinates): the status lines, the move log, then
# the buttons.
PANEL_PADDING = 14
HEADLINE_Y, PLAYERS_Y, SEARCH_INFO_Y = 12, 38, 56
LOG_TOP, LOG_BOTTOM = 84, 334
LOG_LINE_HEIGHT = 22
LOG_CAPACITY = (LOG_BOTTOM - LOG_TOP) // LOG_LINE_HEIGHT  # lines shown at once
SIDE_LABEL_Y, SIDE_BUTTONS_Y = 344, 362
LEVEL_LABEL_Y, LEVEL_BUTTONS_Y = 396, 414
ACTION_BUTTONS_Y = 452
HELP_Y = 484  # two lines of help below the buttons
HELP_LINES = (
    "Click or drag a piece to move it. Esc cancels.",
    "Mouse wheel: scroll through the moves.",
)
BUTTON_HEIGHT = 28


def _button_row(y, names, gap=8):
    """Rectangles for buttons side by side across the panel."""
    left = PANEL_LEFT + PANEL_PADDING
    width = (PANEL_WIDTH - 2 * PANEL_PADDING - gap * (len(names) - 1)) // len(names)
    return {
        name: p.Rect(left + i * (width + gap), y, width, BUTTON_HEIGHT)
        for i, name in enumerate(names)
    }


BUTTONS = {
    **_button_row(SIDE_BUTTONS_Y, ("white", "black")),
    **_button_row(LEVEL_BUTTONS_Y, tuple(search.DIFFICULTIES)),
    **_button_row(ACTION_BUTTONS_Y, ("undo", "new", "flip")),
}
BUTTON_LABELS = {
    "white": "White",
    "black": "Black",
    **{level: level.capitalize() for level in search.DIFFICULTIES},
    "undo": "Undo (Z)",
    "new": "New game (R)",
    "flip": "Flip (F)",
}

# App states
HUMAN_TURN = "human turn"
PROMOTING = "choosing a promotion"
AI_THINKING = "AI thinking"
ANIMATING = "animating"
GAME_OVER = "game over"


def load_images():
    """Load the piece sprites into IMAGES once at startup, scaled to one square."""
    pieces = ["wp", "wN", "wB", "wR", "wQ", "wK", "bp", "bN", "bB", "bR", "bQ", "bK"]
    for piece in pieces:
        img = os.path.join(IMAGE_PATH, piece + ".png")
        IMAGES[piece] = p.transform.scale(p.image.load(img), (SQ_SIZE, SQ_SIZE))


def square_at(pos, flipped=False):
    """The board square (row, col) under the screen position `pos`, or None.
    `flipped`: the board is shown with Black at the bottom."""
    x, y = pos[0] - BOARD_LEFT, pos[1]
    if not (0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT):
        return None
    row, col = y // SQ_SIZE, x // SQ_SIZE
    return (7 - row, 7 - col) if flipped else (row, col)


def square_rect(square, flipped=False):
    """The screen rectangle of the board square (row, col)."""
    row, col = square
    if flipped:
        row, col = 7 - row, 7 - col
    return p.Rect(BOARD_LEFT + col * SQ_SIZE, row * SQ_SIZE, SQ_SIZE, SQ_SIZE)


def mark_surfaces():
    """One transparent square-sized image per kind of square mark."""

    def square():
        return p.Surface((SQ_SIZE, SQ_SIZE), p.SRCALPHA)

    centre = (SQ_SIZE // 2, SQ_SIZE // 2)
    surfaces = {kind: square() for kind in ("last move", "selected", "move", "capture")}
    surfaces["last move"].fill(LAST_MOVE_TINT)
    surfaces["selected"].fill(SELECTED_TINT)
    p.draw.circle(surfaces["move"], MOVE_HINT, centre, SQ_SIZE // 6)  # a dot
    # A ring around a piece that can be taken.
    p.draw.circle(surfaces["capture"], MOVE_HINT, centre, SQ_SIZE // 2, SQ_SIZE // 12)
    # A red glow under a king in check, strongest in the middle.
    surfaces["check"] = square()
    for i in range(8):
        radius = SQ_SIZE // 2 - i * SQ_SIZE // 20
        p.draw.circle(surfaces["check"], (*CHECK_GLOW, 50 + 25 * i), centre, radius)
    return surfaces


def animation_seconds(move):
    """How long `move` takes to slide into place: longer moves take longer."""
    distance = math.hypot(move.end_row - move.start_row, move.end_col - move.start_col)
    return 0.1 + 0.04 * distance


def take_back_move(gs, white_is_human, black_is_human):
    """Undo the last move, and against the AI also the move before it.

    After undoing, if it is the AI's turn (and a human is playing), the AI's
    reply is taken back too, so the human is to move again instead of the AI
    immediately replaying.
    """
    gs.undo_move()
    ai_to_move = not (white_is_human if gs.white_to_move else black_is_human)
    if ai_to_move and (white_is_human or black_is_human) and gs.move_log:
        gs.undo_move()


def format_score(score):
    """A search score (centipawns, White's point of view) as text: "+0.35",
    "-1.20", or "+M2" / "-M1" when White / Black mates in that many moves."""
    if abs(score) >= search.MATE_THRESHOLD:
        plies = CHECKMATE - abs(score)  # to the mate, counted from the search root
        return f"{'+' if score > 0 else '-'}M{(plies + 1) // 2}"
    return f"{score / 100:+.2f}"


def describe_search(result):
    """One line about the AI's search for its last move, e.g.
    "AI: depth 5, eval +0.35, 1.9 s" ("" if there is nothing to tell)."""
    if result is None:
        return ""
    if result.depth == 0:
        return "AI: the only legal move"
    return (
        f"AI: depth {result.depth}, eval {format_score(result.score)}, "
        f"{result.elapsed:.1f} s"
    )


def game_over_text(gs):
    """The result of a finished game, e.g. "White wins by checkmate"."""
    if gs.checkmate:
        winner = "Black" if gs.white_to_move else "White"
        return f"{winner} wins by checkmate"
    if gs.stalemate:
        return "Stalemate"
    return f"Draw by {gs.draw_reason}"


def draw_evaluation_bar(screen, evaluation, font, flipped=False):
    """Draw the evaluation bar left of the board, as on chess.com or lichess.

    `evaluation` is in centipawns from White's point of view. White's share of
    the bar grows from White's side of the board (the bottom unless
    `flipped`), and the leading side's end shows the score in pawns, or "M"
    for a forced mate.
    """
    mate = abs(evaluation) >= search.MATE_THRESHOLD
    if mate:
        white_share = 1.0 if evaluation > 0 else 0.0
    else:
        # A sigmoid: +1 pawn fills 56 % of the bar, +5 pawns 76 %, +10 91 %.
        pawns = max(-50.0, min(50.0, evaluation / 100))
        white_share = 1 / (1 + 10 ** (-pawns / 10))
    white_height = round(BOARD_HEIGHT * white_share)
    white_top = 0 if flipped else BOARD_HEIGHT - white_height
    p.draw.rect(screen, EVAL_BLACK, (0, 0, EVAL_BAR_WIDTH, BOARD_HEIGHT))
    p.draw.rect(screen, EVAL_WHITE, (0, white_top, EVAL_BAR_WIDTH, white_height))
    middle = BOARD_HEIGHT // 2
    p.draw.line(screen, EVAL_MIDLINE, (0, middle), (EVAL_BAR_WIDTH - 1, middle))

    white_leads = evaluation >= 0
    label = "M" if mate else f"{abs(evaluation) / 100:.1f}"
    text = font.render(label, True, EVAL_BLACK if white_leads else EVAL_WHITE)
    rect = text.get_rect(centerx=EVAL_BAR_WIDTH // 2)
    if white_leads != flipped:  # the leading side is at the bottom
        rect.bottom = BOARD_HEIGHT - 6
    else:
        rect.top = 6
    screen.blit(text, rect)


def draw_end_game_text(screen, text):
    """The result in white with a dark shadow, centred on the board."""
    font = p.font.SysFont("Helvetica", 32, True, False)
    label = font.render(text, True, (255, 255, 255))
    shadow = font.render(text, True, (0, 0, 0))
    both = p.Surface((label.get_width() + 2, label.get_height() + 2), p.SRCALPHA)
    both.blit(shadow, (2, 2))
    both.blit(label, (0, 0))
    board_centre = (EVAL_BAR_WIDTH + BOARD_WIDTH // 2, BOARD_HEIGHT // 2)
    screen.blit(both, both.get_rect(center=board_centre))


def move_log_lines(sans, first_number=1, black_first=False):
    """The moves (in SAN) as numbered lines of one move pair each, such as
    ("12.", "Nf3", "Nc6"). A game that starts with Black to move begins with
    ("<first_number>.", "...", <Black's move>)."""
    moves = (["..."] if black_first else []) + list(sans)
    return [
        (
            f"{first_number + i // 2}.",
            moves[i],
            moves[i + 1] if i + 1 < len(moves) else "",
        )
        for i in range(0, len(moves), 2)
    ]


class App:
    """The game window: the game, the AI's search process and the display."""

    def __init__(self):
        p.init()
        p.display.set_caption("Chess AI")
        self.screen = p.display.set_mode(WINDOW_SIZE)
        self.clock = p.time.Clock()
        self.move_log_font = p.font.SysFont("Arial", 16)
        self.eval_font = p.font.SysFont("Arial", 12, bold=True)
        self.headline_font = p.font.SysFont("Arial", 18, bold=True)
        self.detail_font = p.font.SysFont("Arial", 13)
        panel_font = p.font.SysFont("Arial", 13)
        self.panel_labels = {
            text: panel_font.render(text, True, MUTED_TEXT)
            for text in ("New game as", "AI level (from its next move)")
        }
        help_font = p.font.SysFont("Arial", 12)
        self.help_labels = [help_font.render(t, True, MUTED_TEXT) for t in HELP_LINES]
        button_font = p.font.SysFont("Arial", 13)
        self.button_labels = {
            name: button_font.render(label, True, TEXT_COLOR)
            for name, label in BUTTON_LABELS.items()
        }
        load_images()
        self.marks = mark_surfaces()
        # Coordinate labels in the colour of the other kind of square.
        coordinate_font = p.font.SysFont("Arial", 12, bold=True)
        self.coordinate_labels = {
            (text, light): coordinate_font.render(
                text, True, DARK_SQUARE if light else LIGHT_SQUARE
            )
            for text in "abcdefgh12345678"
            for light in (True, False)
        }
        # Who plays which side: a human or the AI (see new_game).
        self.human_plays_white = True
        self.white_is_human = True
        self.black_is_human = False
        self.flipped = False  # Black at the bottom of the board
        self.difficulty = search.DEFAULT_DIFFICULTY  # a key of search.DIFFICULTIES
        self.animate = True  # slide moves into place
        self.running = True
        self._ai_process = None
        self._ai_queue = None
        self.new_game()

    # ---------- Game flow ----------

    def new_game(self, human_plays_white=None, *, fen=None):
        """Start again from the initial position, or from `fen` if given.
        The human keeps their side unless `human_plays_white` says otherwise;
        their pieces are shown at the bottom."""
        self._stop_ai()
        if human_plays_white is not None:
            self.human_plays_white = human_plays_white
            self.white_is_human = human_plays_white
            self.black_is_human = not human_plays_white
            self.flipped = not human_plays_white
        self.gs = GameState.from_fen(fen) if fen else GameState()
        self.san_log = []  # the moves played, in standard algebraic notation
        self.first_move_number = self.gs.fullmove_number
        self.black_moved_first = not self.gs.white_to_move
        self.log_scroll = 0  # lines scrolled back from the newest move
        self.last_search = None  # the SearchResult behind the AI's last move
        self._clear_input()
        self._position_changed()

    def undo(self):
        """Take back the last move; against the AI, back to the human's turn."""
        self._stop_ai()
        take_back_move(self.gs, self.white_is_human, self.black_is_human)
        del self.san_log[len(self.gs.move_log) :]
        self.log_scroll = 0
        self.last_search = None
        self._clear_input()
        self._position_changed()

    def _clear_input(self):
        """Forget a half-entered move."""
        self.selected = None  # the square of the piece the human picked
        self.promotion_moves = []  # the moves the promotion picker offers
        # While the mouse button is held on a piece: (its square, whether it
        # was already picked); the piece follows the mouse.
        self.drag = None

    def _human_to_move(self):
        return self.white_is_human if self.gs.white_to_move else self.black_is_human

    def _position_changed(self):
        """Refresh what depends on the position and decide what happens next:
        the game is over, the human moves, or the AI starts thinking."""
        self.animation = None
        self.legal_moves = self.gs.get_legal_moves()
        self.gs.update_game_status(self.legal_moves)
        # The engine's own evaluation (captures played out), in centipawns.
        self.evaluation = search.evaluate_position(self.gs, self.legal_moves)
        if self.gs.checkmate or self.gs.stalemate or self.gs.draw_reason:
            self.state = GAME_OVER
        elif self._human_to_move():
            self.state = HUMAN_TURN
        else:
            self._start_ai()

    def _play(self, move):
        """Play a legal move for the side to move, then let it slide into place."""
        self.san_log.append(self.gs.san(move, self.legal_moves))  # before the move
        self.log_scroll = 0  # show the newest move
        self.gs.make_move(move)
        self._clear_input()
        if self.animate:
            self.animation = (move, time.perf_counter())
            self.state = ANIMATING
        else:
            self._position_changed()

    def _moves_between(self, start, end):
        """The legal moves from square `start` to square `end` (four for a
        promotion, one per piece)."""
        return [
            move
            for move in self.legal_moves
            if (move.start_row, move.start_col) == start
            and (move.end_row, move.end_col) == end
        ]

    # ---------- AI ----------

    def _start_ai(self):
        level = search.DIFFICULTIES[self.difficulty]
        self._ai_queue = Queue()
        self._ai_process = Process(
            target=search.search_to_queue,
            args=(self.gs, self.legal_moves, self._ai_queue),
            kwargs={"max_depth": level.max_depth, "time_limit": level.time_limit},
            daemon=True,  # never outlives the window
        )
        self._ai_process.start()
        self._ai_started = time.perf_counter()
        self.state = AI_THINKING

    def _poll_ai(self):
        """Play the AI's move once its search process has finished."""
        if self._ai_process.is_alive():
            return
        try:
            result = self._ai_queue.get(timeout=AI_ANSWER_TIMEOUT)
        except queue.Empty:
            result = None  # the process died without answering
        self._stop_ai()
        move = result.move if result is not None else None
        if move not in self.legal_moves:  # never leave the game stuck
            move = search.find_random_move(self.legal_moves)
        self.last_search = result
        self._play(move)

    def _stop_ai(self):
        """Stop the AI's search process, if there is one, and wait for it to
        end, so that no search outlives an undo, a new game or the window."""
        if self._ai_process is not None:
            if self._ai_process.is_alive():
                self._ai_process.terminate()
            self._ai_process.join(timeout=1)
        self._ai_process = self._ai_queue = None

    # ---------- Input ----------

    def run(self):
        """The main loop: handle input, advance the game and draw it, until
        the window is closed."""
        try:
            while self.running:
                for event in p.event.get():
                    self.handle_event(event)
                self.update()
                self.draw()
                p.display.flip()
                smooth = self.state == ANIMATING or self.drag is not None
                self.clock.tick(ANIMATION_FPS if smooth else FPS)
        finally:
            self.close()

    def close(self):
        """Stop the AI and close the window."""
        self._stop_ai()
        p.quit()

    def handle_event(self, event):
        if event.type == p.QUIT:
            self.running = False
        elif event.type == p.MOUSEWHEEL:
            self._scroll_log(event.y)
        elif event.type == p.MOUSEBUTTONDOWN and event.button == 1:
            self._on_press(event.pos)
        elif event.type == p.MOUSEBUTTONUP and event.button == 1:
            self._on_release(event.pos)
        elif event.type == p.KEYDOWN:
            if event.key == p.K_z:  # undo: back to the human's previous turn
                self.undo()
            elif event.key == p.K_r:  # reset the board
                self.new_game()
            elif event.key == p.K_f:  # flip the board
                self.flipped = not self.flipped
            elif event.key == p.K_ESCAPE:
                self._cancel_move()

    def _cancel_move(self):
        """Drop the picked piece, or close the promotion picker."""
        self._clear_input()
        if self.state == PROMOTING:
            self.state = HUMAN_TURN

    def log_lines(self):
        return move_log_lines(
            self.san_log, self.first_move_number, self.black_moved_first
        )

    def _scroll_log(self, lines):
        """Scroll the move log back (lines > 0) or forward (lines < 0)."""
        most = max(0, len(self.log_lines()) - LOG_CAPACITY)
        self.log_scroll = max(0, min(self.log_scroll + lines, most))

    def visible_log_lines(self):
        """The part of the move log the panel has room for, and the number of
        the first line shown."""
        lines = self.log_lines()
        first = max(0, len(lines) - LOG_CAPACITY - self.log_scroll)
        return lines[first : first + LOG_CAPACITY], first

    def _press_button(self, name):
        if name in ("white", "black"):
            self.new_game(human_plays_white=name == "white")
        elif name in search.DIFFICULTIES:
            self.difficulty = name
        elif name == "undo":
            self.undo()
        elif name == "new":
            self.new_game()
        elif name == "flip":
            self.flipped = not self.flipped

    def _on_press(self, pos):
        """Pick up a piece, move the picked piece to a square it can reach
        (the second click of a move), or press a button."""
        for name, rect in BUTTONS.items():
            if rect.collidepoint(pos):
                self._press_button(name)
                return
        if self.state == PROMOTING:
            self._choose_promotion(pos)
            return
        if self.state != HUMAN_TURN:
            return
        square = square_at(pos, self.flipped)
        if square is None:
            self.selected = None  # a click off the board
            return
        if self.selected is not None and self._moves_between(self.selected, square):
            self._move_piece(self.selected, square)
            return
        r, c = square
        own_color = "w" if self.gs.white_to_move else "b"
        if self.gs.board[r][c][0] == own_color:
            self.drag = (square, square == self.selected)
            self.selected = square
        else:
            self.selected = None

    def _on_release(self, pos):
        """Put down a dragged piece: on a square it can reach, that is its move."""
        if self.drag is None:
            return
        start, was_picked = self.drag
        self.drag = None
        square = square_at(pos, self.flipped)
        if square == start:
            if was_picked:
                self.selected = None  # a second click on the picked piece
        elif square is not None and self._moves_between(start, square):
            self._move_piece(start, square)
        else:
            self.selected = None  # dropped where it cannot go

    def _move_piece(self, start, end):
        """Play the move from `start` to `end`; for a promotion, open the
        picker so the player chooses the piece first."""
        moves = self._moves_between(start, end)
        if len(moves) == 1:
            self._play(moves[0])
            return
        moves.sort(key=lambda move: PROMOTION_PIECES.index(move.promotion_piece))
        self.selected = start
        self.promotion_moves = moves
        self.state = PROMOTING

    def _promotion_choices(self):
        """(screen rectangle, move) for each piece the picker offers: a column
        that starts on the promotion square and runs toward the middle of the
        board, queen first."""
        target = self.promotion_moves[0]
        first = square_rect((target.end_row, target.end_col), self.flipped)
        step = SQ_SIZE if first.top == 0 else -SQ_SIZE
        return [
            (first.move(0, i * step), move)
            for i, move in enumerate(self.promotion_moves)
        ]

    def _choose_promotion(self, pos):
        for rect, move in self._promotion_choices():
            if rect.collidepoint(pos):
                self._play(move)
                return
        self._cancel_move()  # a click anywhere else

    def update(self):
        """Advance what moves on by itself: the AI's search and animations."""
        if self.state == AI_THINKING:
            self._poll_ai()
        elif self.state == ANIMATING:
            move, started = self.animation
            if time.perf_counter() - started >= animation_seconds(move):
                self._position_changed()

    # ---------- Drawing ----------

    def status_lines(self):
        """The three lines at the top of the side panel: what is happening,
        who plays whom, and how the AI found its last move."""
        gs = self.gs
        if self.state == GAME_OVER:
            headline = game_over_text(gs)
        elif self.state == PROMOTING:
            headline = "Choose the promotion piece"
        elif self.state == AI_THINKING:
            elapsed = time.perf_counter() - self._ai_started
            headline = f"AI is thinking... {elapsed:.1f} s"
        elif self._human_to_move():
            headline = "Check! Your move" if gs.in_check() else "Your move"
        else:
            headline = ("White" if gs.white_to_move else "Black") + " to move"
        side = "White" if self.human_plays_white else "Black"
        players = f"You play {side} against the {self.difficulty} AI"
        return headline, players, describe_search(self.last_search)

    def square_marks(self):
        """The marked squares as (kind, square) pairs. The kinds: "last move"
        (its start and end), "check" (a king in check), "selected" (the picked
        piece), and "move" / "capture" (where the picked piece can go)."""
        gs = self.gs
        marks = []
        if gs.move_log:
            last = gs.move_log[-1]
            marks.append(("last move", (last.start_row, last.start_col)))
            marks.append(("last move", (last.end_row, last.end_col)))
        if self.selected is not None:
            marks.append(("selected", self.selected))
            targets = {
                (move.end_row, move.end_col): "capture" if move.is_capture else "move"
                for move in self.legal_moves
                if (move.start_row, move.start_col) == self.selected
            }
            marks += [(kind, square) for square, kind in targets.items()]
        if gs.in_check():  # last, so that it shows over the other tints
            king = (
                gs.white_king_location if gs.white_to_move else gs.black_king_location
            )
            marks.append(("check", king))
        return marks

    def draw(self):
        draw_evaluation_bar(self.screen, self.evaluation, self.eval_font, self.flipped)
        self._draw_board()
        marks = self.square_marks()
        # Tints go under the pieces, move hints over them (a ring must show
        # around the piece it can take).
        self._draw_marks(marks, ("last move", "selected", "check"))
        self._draw_coordinates()
        self._draw_pieces()
        self._draw_marks(marks, ("move", "capture"))
        if self.state == ANIMATING:
            self._draw_animation()
        if self.state == PROMOTING:
            self._draw_promotion_picker()
        self._draw_panel()
        if self.drag is not None:
            self._draw_dragged_piece()
        if self.state == GAME_OVER:
            band = p.Surface((BOARD_WIDTH, 2 * SQ_SIZE), p.SRCALPHA)
            band.fill((0, 0, 0, 140))  # so the text stands out from the pieces
            self.screen.blit(band, (BOARD_LEFT, BOARD_HEIGHT // 2 - SQ_SIZE))
            draw_end_game_text(self.screen, game_over_text(self.gs))

    def _draw_board(self):
        for r in range(DIMENSION):
            for c in range(DIMENSION):
                color = BOARD_COLORS[(r + c) % 2]
                p.draw.rect(self.screen, color, square_rect((r, c), self.flipped))

    def _draw_marks(self, marks, kinds):
        for kind, square in marks:
            if kind in kinds:
                self.screen.blit(self.marks[kind], square_rect(square, self.flipped))

    def _draw_coordinates(self):
        """Rank numbers down the left edge of the board and file letters
        along its bottom edge, whichever squares are shown there."""
        for i in range(DIMENSION):
            left_edge = square_at((BOARD_LEFT, i * SQ_SIZE), self.flipped)
            bottom_edge = square_at(
                (BOARD_LEFT + i * SQ_SIZE, BOARD_HEIGHT - 1), self.flipped
            )
            for (row, col), is_rank in ((left_edge, True), (bottom_edge, False)):
                text = str(8 - row) if is_rank else "abcdefgh"[col]
                label = self.coordinate_labels[(text, (row + col) % 2 == 0)]
                rect = square_rect((row, col), self.flipped)
                if is_rank:
                    self.screen.blit(label, (rect.x + 3, rect.y + 2))
                else:
                    self.screen.blit(
                        label,
                        (
                            rect.right - label.get_width() - 3,
                            rect.bottom - label.get_height(),
                        ),
                    )

    def _draw_pieces(self):
        # While a move slides into place, its target square shows what stood
        # there before (drawn by _draw_animation).
        hidden = None
        if self.state == ANIMATING:
            move = self.animation[0]
            hidden = (move.end_row, move.end_col)
        elif self.drag is not None:
            hidden = self.drag[0]  # drawn at the mouse instead
        for r, row in enumerate(self.gs.board):
            for c, piece in enumerate(row):
                if piece != "--" and (r, c) != hidden:
                    self.screen.blit(IMAGES[piece], square_rect((r, c), self.flipped))

    def _draw_dragged_piece(self):
        """The dragged piece under the mouse, and a frame around the square it
        would move to if dropped there."""
        start = self.drag[0]
        mouse = p.mouse.get_pos()
        target = square_at(mouse, self.flipped)
        if target is not None and self._moves_between(start, target):
            frame = square_rect(target, self.flipped)
            p.draw.rect(self.screen, TEXT_COLOR, frame, 3)
        piece = self.gs.board[start[0]][start[1]]
        self.screen.blit(IMAGES[piece], IMAGES[piece].get_rect(center=mouse))

    def _draw_panel(self):
        screen = self.screen
        p.draw.rect(screen, PANEL_BG, (PANEL_LEFT, 0, PANEL_WIDTH, BOARD_HEIGHT))
        left, right = (
            PANEL_LEFT + PANEL_PADDING,
            PANEL_LEFT + PANEL_WIDTH - PANEL_PADDING,
        )
        headline, players, search_info = self.status_lines()
        for text, font, color, y in (
            (headline, self.headline_font, TEXT_COLOR, HEADLINE_Y),
            (players, self.detail_font, MUTED_TEXT, PLAYERS_Y),
            (search_info, self.detail_font, MUTED_TEXT, SEARCH_INFO_Y),
        ):
            screen.blit(font.render(text, True, color), (left, y))
        p.draw.line(screen, PANEL_LINE, (left, LOG_TOP - 6), (right, LOG_TOP - 6))

        self._draw_move_log()

        p.draw.line(screen, PANEL_LINE, (left, LOG_BOTTOM + 2), (right, LOG_BOTTOM + 2))
        screen.blit(self.panel_labels["New game as"], (left, SIDE_LABEL_Y))
        screen.blit(
            self.panel_labels["AI level (from its next move)"], (left, LEVEL_LABEL_Y)
        )
        mouse = p.mouse.get_pos()
        human_side = "white" if self.human_plays_white else "black"
        for name, rect in BUTTONS.items():
            if name in (human_side, self.difficulty):
                color = BUTTON_ACTIVE
            elif rect.collidepoint(mouse):
                color = BUTTON_HOVER
            else:
                color = BUTTON_COLOR
            p.draw.rect(screen, color, rect, border_radius=6)
            label = self.button_labels[name]
            screen.blit(label, label.get_rect(center=rect.center))
        for i, label in enumerate(self.help_labels):
            screen.blit(label, (left, HELP_Y + 14 * i))

    def _draw_move_log(self):
        """One numbered move pair per line; the newest move is highlighted."""
        screen, font = self.screen, self.move_log_font
        left = PANEL_LEFT + PANEL_PADDING
        columns = (left + 36, left + 46, left + 136)  # number (right edge), moves
        lines, first = self.visible_log_lines()
        # The newest move's index in the list the lines are made of.
        newest = len(self.san_log) - 1 + self.black_moved_first
        for i, (number, white, black) in enumerate(lines):
            y = LOG_TOP + i * LOG_LINE_HEIGHT
            label = font.render(number, True, MUTED_TEXT)
            screen.blit(label, (columns[0] - label.get_width(), y))
            for side, text in enumerate((white, black)):
                if not text:
                    continue
                label = font.render(text, True, TEXT_COLOR)
                x = columns[1 + side]
                if 2 * (first + i) + side == newest:
                    box = label.get_rect(topleft=(x, y)).inflate(10, 4)
                    p.draw.rect(screen, BUTTON_ACTIVE, box, border_radius=4)
                screen.blit(label, (x, y))

        total = len(self.log_lines())
        if total > LOG_CAPACITY:  # a scroll bar
            track_x = PANEL_LEFT + PANEL_WIDTH - PANEL_PADDING // 2
            track = LOG_CAPACITY * LOG_LINE_HEIGHT
            thumb = max(12, track * LOG_CAPACITY // total)
            thumb_y = LOG_TOP + (track - thumb) * first // (total - LOG_CAPACITY)
            p.draw.line(
                screen, PANEL_LINE, (track_x, LOG_TOP), (track_x, LOG_TOP + track), 3
            )
            p.draw.line(
                screen, MUTED_TEXT, (track_x, thumb_y), (track_x, thumb_y + thumb), 3
            )

    def _draw_promotion_picker(self):
        shade = p.Surface((BOARD_WIDTH, BOARD_HEIGHT), p.SRCALPHA)
        shade.fill((0, 0, 0, 110))
        self.screen.blit(shade, (BOARD_LEFT, 0))
        color = "w" if self.gs.white_to_move else "b"
        for rect, move in self._promotion_choices():
            p.draw.rect(
                self.screen, (235, 235, 235), rect.inflate(-4, -4), border_radius=8
            )
            self.screen.blit(IMAGES[color + move.promotion_piece], rect)

    def _draw_animation(self):
        move, started = self.animation
        progress = min(1.0, (time.perf_counter() - started) / animation_seconds(move))
        # the captured piece stays on its square until the moving piece arrives
        if move.piece_captured != "--":
            captured_square = (
                (move.start_row, move.end_col)
                if move.is_en_passant
                else (move.end_row, move.end_col)
            )
            self.screen.blit(
                IMAGES[move.piece_captured], square_rect(captured_square, self.flipped)
            )
        start = square_rect((move.start_row, move.start_col), self.flipped)
        end = square_rect((move.end_row, move.end_col), self.flipped)
        x = start.x + (end.x - start.x) * progress
        y = start.y + (end.y - start.y) * progress
        self.screen.blit(IMAGES[move.piece_moved], (x, y))


def main():
    """Open the game window and run it until it is closed."""
    App().run()


if __name__ == "__main__":
    main()
