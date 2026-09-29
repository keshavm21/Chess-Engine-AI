"""pygame front end: draws the game, handles input and runs the AI.

The window is an App that is in exactly one state at a time:

- HUMAN_TURN: the player picks a move (a piece, then a square it can reach),
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

# AI strength: one of search.DIFFICULTIES (a selector comes with Phase 8).
AI_DIFFICULTY = search.DEFAULT_DIFFICULTY

# Piece sprites live next to this module.
IMAGE_PATH = os.path.join(os.path.dirname(__file__), "assets", "pieces")

# 400 is another good option and it depends on how good the
# images you have in terms of quality and resolution and 512 is a power of 2
BOARD_WIDTH = BOARD_HEIGHT = 512
EVAL_BAR_WIDTH = 40  # Width of evaluation bar
MOVE_LOG_PANEL_WIDTH = 270
MOVE_LOG_PANEL_HEIGHT = BOARD_HEIGHT
# the chess board is 8x8 :)
DIMENSION = 8
SQ_SIZE = BOARD_HEIGHT // DIMENSION
BOARD_LEFT = EVAL_BAR_WIDTH  # the board is drawn right of the evaluation bar
PANEL_LEFT = BOARD_LEFT + BOARD_WIDTH
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


def square_at(pos):
    """The board square (row, col) under the screen position `pos`, or None."""
    x, y = pos[0] - BOARD_LEFT, pos[1]
    if not (0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT):
        return None
    return y // SQ_SIZE, x // SQ_SIZE


def square_rect(square):
    """The screen rectangle of the board square (row, col)."""
    row, col = square
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


def game_over_text(gs):
    """The result of a finished game, e.g. "White wins by checkmate"."""
    if gs.checkmate:
        winner = "Black" if gs.white_to_move else "White"
        return f"{winner} wins by checkmate"
    if gs.stalemate:
        return "Stalemate"
    return f"Draw by {gs.draw_reason}"


def draw_evaluation_bar(screen, evaluation):
    """
    Draw the evaluation bar on the left side of the board
    Similar to chess.com/lichess style
    """
    bar_rect = p.Rect(0, 0, EVAL_BAR_WIDTH, BOARD_HEIGHT)

    # Background (black side)
    p.draw.rect(screen, p.Color(50, 50, 50), bar_rect)

    # Normalize evaluation to 0-1 range for display
    # We'll use a sigmoid-like function to prevent extreme values
    max_eval = 10.0  # Maximum evaluation to show as "winning"

    if evaluation >= 1000:  # Checkmate for white
        white_percentage = 1.0
    elif evaluation <= -1000:  # Checkmate for black
        white_percentage = 0.0
    else:
        # Convert centipawn advantage to percentage
        # Using a modified sigmoid function
        normalized = evaluation / max_eval
        # Clamp between -5 and 5 for smooth transition
        clamped = max(-5, min(5, normalized))
        # Sigmoid function: maps to 0-1 range
        white_percentage = 1 / (1 + pow(10, -clamped))

    # Calculate white's bar height (white is at bottom)
    white_height = int(BOARD_HEIGHT * white_percentage)
    black_height = BOARD_HEIGHT - white_height

    # Draw black's portion (top)
    if black_height > 0:
        black_rect = p.Rect(0, 0, EVAL_BAR_WIDTH, black_height)
        p.draw.rect(screen, p.Color(50, 50, 50), black_rect)

    # Draw white's portion (bottom)
    if white_height > 0:
        white_rect = p.Rect(0, black_height, EVAL_BAR_WIDTH, white_height)
        p.draw.rect(screen, p.Color(245, 245, 245), white_rect)

    # Draw border
    p.draw.rect(screen, p.Color(100, 100, 100), bar_rect, 2)

    # Draw evaluation text
    font = p.font.SysFont("Arial", 14, True, False)

    if evaluation >= 1000:
        eval_text = "M"  # Checkmate for white
        text_color = p.Color("white")
        text_y = black_height - 20
    elif evaluation <= -1000:
        eval_text = "M"  # Checkmate for black
        text_color = p.Color("black")
        text_y = black_height + 5
    else:
        # Show evaluation in pawns
        eval_value = abs(evaluation)
        eval_text = f"{eval_value:.1f}"

        # Position text on the larger side
        if white_percentage > 0.5:
            text_color = p.Color("black")
            text_y = black_height + 5
        else:
            text_color = p.Color("white")
            text_y = max(5, black_height - 20)

    text_surface = font.render(eval_text, True, text_color)
    text_rect = text_surface.get_rect(center=(EVAL_BAR_WIDTH // 2, text_y))

    # Draw text background for better visibility
    bg_rect = text_rect.inflate(4, 2)
    bg_color = (
        p.Color("white") if text_color == p.Color("black") else p.Color(50, 50, 50)
    )
    p.draw.rect(screen, bg_color, bg_rect)
    p.draw.rect(screen, p.Color(100, 100, 100), bg_rect, 1)

    screen.blit(text_surface, text_rect)


def draw_end_game_text(screen, text):
    font = p.font.SysFont("Helvetica", 32, True, False)
    text_object = font.render(text, 0, p.Color("Gray"))
    board_centre = (EVAL_BAR_WIDTH + BOARD_WIDTH // 2, BOARD_HEIGHT // 2)
    text_location = text_object.get_rect(center=board_centre)
    screen.blit(text_object, text_location)
    text_object = font.render(text, 0, p.Color("Black"))
    screen.blit(text_object, text_location.move(2, 2))


def draw_move_log(screen, gs, font):
    move_log_rect = p.Rect(PANEL_LEFT, 0, MOVE_LOG_PANEL_WIDTH, MOVE_LOG_PANEL_HEIGHT)
    p.draw.rect(screen, p.Color("black"), move_log_rect)
    move_log = gs.move_log
    move_texts = []
    for i in range(0, len(move_log), 2):
        move_string = str(i // 2 + 1) + ". " + str(move_log[i]) + " "
        if i + 1 < len(move_log):
            move_string += str(move_log[i + 1])
        move_texts.append(move_string)
    padding = 5
    text_y = padding
    line_spacing = 5
    moves_per_row = 3
    for i in range(0, len(move_texts), moves_per_row):
        text = ""
        for j in range(moves_per_row):
            if i + j < len(move_texts):
                text += move_texts[i + j] + "  "
        text_object = font.render(text, True, p.Color("white"))
        text_location = move_log_rect.move(padding, text_y)
        screen.blit(text_object, text_location)
        text_y += text_object.get_height() + line_spacing


class App:
    """The game window: the game, the AI's search process and the display."""

    def __init__(self):
        p.init()
        p.display.set_caption("Chess with Evaluation")
        self.screen = p.display.set_mode(
            (PANEL_LEFT + MOVE_LOG_PANEL_WIDTH, BOARD_HEIGHT)
        )
        self.clock = p.time.Clock()
        self.move_log_font = p.font.SysFont("Arial", 20, False, False)
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
        # Who plays which side: a human or the AI.
        self.white_is_human = True
        self.black_is_human = False
        self.animate = True  # slide moves into place
        self.running = True
        self._ai_process = None
        self._ai_queue = None
        self.new_game()

    # ---------- Game flow ----------

    def new_game(self, fen=None):
        """Start again from the initial position, or from `fen` if given."""
        self._stop_ai()
        self.gs = GameState.from_fen(fen) if fen else GameState()
        self._clear_input()
        self._position_changed()

    def undo(self):
        """Take back the last move; against the AI, back to the human's turn."""
        self._stop_ai()
        take_back_move(self.gs, self.white_is_human, self.black_is_human)
        self._clear_input()
        self._position_changed()

    def _clear_input(self):
        """Forget a half-entered move."""
        self.selected = None  # the square of the piece the human picked
        self.promotion_moves = []  # the moves the promotion picker offers

    def _human_to_move(self):
        return self.white_is_human if self.gs.white_to_move else self.black_is_human

    def _position_changed(self):
        """Refresh what depends on the position and decide what happens next:
        the game is over, the human moves, or the AI starts thinking."""
        self.animation = None
        self.legal_moves = self.gs.get_legal_moves()
        self.gs.update_game_status(self.legal_moves)
        # The engine's own evaluation (captures played out), in pawns.
        self.evaluation = search.evaluate_position(self.gs, self.legal_moves) / 100
        if self.gs.checkmate or self.gs.stalemate or self.gs.draw_reason:
            self.state = GAME_OVER
        elif self._human_to_move():
            self.state = HUMAN_TURN
        else:
            self._start_ai()

    def _play(self, move):
        """Play a legal move for the side to move, then let it slide into place."""
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
        level = search.DIFFICULTIES[AI_DIFFICULTY]
        self._ai_queue = Queue()
        self._ai_process = Process(
            target=search.find_best_move,
            args=(self.gs, self.legal_moves, self._ai_queue),
            kwargs={"max_depth": level.max_depth, "time_limit": level.time_limit},
            daemon=True,  # never outlives the window
        )
        self._ai_process.start()
        self.state = AI_THINKING

    def _poll_ai(self):
        """Play the AI's move once its search process has finished."""
        if self._ai_process.is_alive():
            return
        try:
            move = self._ai_queue.get(timeout=AI_ANSWER_TIMEOUT)
        except queue.Empty:
            move = None  # the process died without answering
        self._stop_ai()
        if move not in self.legal_moves:  # never leave the game stuck
            move = search.find_random_move(self.legal_moves)
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
                self.clock.tick(ANIMATION_FPS if self.state == ANIMATING else FPS)
        finally:
            self.close()

    def close(self):
        """Stop the AI and close the window."""
        self._stop_ai()
        p.quit()

    def handle_event(self, event):
        if event.type == p.QUIT:
            self.running = False
        elif event.type == p.MOUSEBUTTONDOWN and event.button == 1:
            self._on_press(event.pos)
        elif event.type == p.KEYDOWN:
            if event.key == p.K_z:  # undo: back to the human's previous turn
                self.undo()
            elif event.key == p.K_r:  # reset the board
                self.new_game()
            elif event.key == p.K_ESCAPE:
                self._cancel_move()

    def _cancel_move(self):
        """Drop the picked piece, or close the promotion picker."""
        self._clear_input()
        if self.state == PROMOTING:
            self.state = HUMAN_TURN

    def _on_press(self, pos):
        """Click a piece, then a square it can move to."""
        if self.state == PROMOTING:
            self._choose_promotion(pos)
            return
        if self.state != HUMAN_TURN:
            return
        square = square_at(pos)
        if square is None or square == self.selected:
            self.selected = None  # a click off the board or on the picked piece
            return
        if self.selected is not None:
            moves = self._moves_between(self.selected, square)
            if len(moves) == 1:
                self._play(moves[0])
                return
            if moves:  # a promotion: the player chooses the piece first
                moves.sort(
                    key=lambda move: PROMOTION_PIECES.index(move.promotion_piece)
                )
                self.promotion_moves = moves
                self.state = PROMOTING
                return
        r, c = square
        own_color = "w" if self.gs.white_to_move else "b"
        self.selected = square if self.gs.board[r][c][0] == own_color else None

    def _promotion_choices(self):
        """(screen rectangle, move) for each piece the picker offers: a column
        that starts on the promotion square and runs toward the middle of the
        board, queen first."""
        target = self.promotion_moves[0]
        first = square_rect((target.end_row, target.end_col))
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
        draw_evaluation_bar(self.screen, self.evaluation)
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
        draw_move_log(self.screen, self.gs, self.move_log_font)
        if self.state == GAME_OVER:
            draw_end_game_text(self.screen, game_over_text(self.gs))

    def _draw_board(self):
        for r in range(DIMENSION):
            for c in range(DIMENSION):
                p.draw.rect(self.screen, BOARD_COLORS[(r + c) % 2], square_rect((r, c)))

    def _draw_marks(self, marks, kinds):
        for kind, square in marks:
            if kind in kinds:
                self.screen.blit(self.marks[kind], square_rect(square))

    def _draw_coordinates(self):
        """Rank numbers down the left edge of the board and file letters
        along its bottom edge, whichever squares are shown there."""
        for i in range(DIMENSION):
            left_edge = square_at((BOARD_LEFT, i * SQ_SIZE))
            bottom_edge = square_at((BOARD_LEFT + i * SQ_SIZE, BOARD_HEIGHT - 1))
            for (row, col), is_rank in ((left_edge, True), (bottom_edge, False)):
                text = str(8 - row) if is_rank else "abcdefgh"[col]
                label = self.coordinate_labels[(text, (row + col) % 2 == 0)]
                rect = square_rect((row, col))
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
        for r, row in enumerate(self.gs.board):
            for c, piece in enumerate(row):
                if piece != "--" and (r, c) != hidden:
                    self.screen.blit(IMAGES[piece], square_rect((r, c)))

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
            self.screen.blit(IMAGES[move.piece_captured], square_rect(captured_square))
        start = square_rect((move.start_row, move.start_col))
        end = square_rect((move.end_row, move.end_col))
        x = start.x + (end.x - start.x) * progress
        y = start.y + (end.y - start.y) * progress
        self.screen.blit(IMAGES[move.piece_moved], (x, y))


def main():
    """Open the game window and run it until it is closed."""
    App().run()


if __name__ == "__main__":
    main()
