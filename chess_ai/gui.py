"""pygame front end: draws the game, handles input and runs the AI.

The AI searches in a separate process so the window stays responsive.
"""

import os
from multiprocessing import Process, Queue

import pygame as p

from chess_ai import search
from chess_ai.engine import GameState, Move

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
# for animation later on
MAX_FPS = 15
IMAGES = {}
BOARD_COLORS = (p.Color("white"), p.Color("gray"))  # light, dark squares


def load_images():
    """Load the piece sprites into IMAGES once at startup, scaled to one square."""
    pieces = ["wp", "wN", "wB", "wR", "wQ", "wK", "bp", "bN", "bB", "bR", "bQ", "bK"]
    for piece in pieces:
        img = os.path.join(IMAGE_PATH, piece + ".png")
        IMAGES[piece] = p.transform.scale(p.image.load(img), (SQ_SIZE, SQ_SIZE))


def evaluate_position(gs):
    """
    Evaluate the current position
    Returns a score where positive is good for white, negative for black
    Range: -1000 to +1000 (checkmate values)
    """
    # Check for game over
    if gs.checkmate:
        return -1000 if gs.white_to_move else 1000
    elif gs.stalemate:
        return 0

    score = 0

    # Piece values
    piece_values = {"K": 0, "Q": 9, "R": 5, "B": 3, "N": 3, "p": 1}

    # Position scores
    knight_scores = [
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 2, 2, 2, 2, 2, 2, 1],
        [1, 2, 3, 3, 3, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 3, 3, 3, 2, 1],
        [1, 2, 2, 2, 2, 2, 2, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    ]

    bishop_scores = [
        [4, 3, 2, 1, 1, 2, 3, 4],
        [3, 4, 3, 2, 2, 3, 4, 3],
        [2, 3, 4, 3, 3, 4, 3, 2],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [2, 3, 4, 3, 3, 4, 3, 2],
        [3, 4, 3, 2, 2, 3, 4, 3],
        [4, 3, 2, 1, 1, 2, 3, 4],
    ]

    queen_scores = [
        [1, 1, 1, 3, 1, 1, 1, 1],
        [1, 2, 3, 3, 3, 1, 1, 1],
        [1, 4, 3, 3, 3, 4, 2, 1],
        [1, 2, 3, 3, 3, 2, 2, 1],
        [1, 2, 3, 3, 3, 2, 2, 1],
        [1, 4, 3, 3, 3, 4, 2, 1],
        [1, 1, 2, 3, 3, 1, 1, 1],
        [1, 1, 1, 3, 1, 1, 1, 1],
    ]

    rook_scores = [
        [4, 3, 4, 4, 4, 4, 3, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 3, 4, 4, 4, 4, 3, 4],
    ]

    white_pawn_scores = [
        [8, 8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8, 8],
        [5, 6, 6, 7, 7, 6, 6, 5],
        [2, 3, 3, 5, 5, 3, 3, 2],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [1, 1, 1, 0, 0, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ]

    black_pawn_scores = [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 1, 0, 0, 1, 1, 1],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [2, 3, 3, 5, 5, 3, 3, 2],
        [5, 6, 6, 7, 7, 6, 6, 5],
        [8, 8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8, 8],
    ]

    piece_square_tables = {
        "N": knight_scores,
        "B": bishop_scores,
        "Q": queen_scores,
        "R": rook_scores,
        "bp": black_pawn_scores,
        "wp": white_pawn_scores,
    }

    # Calculate material and positional score
    for row in range(len(gs.board)):
        for col in range(len(gs.board[row])):
            square = gs.board[row][col]
            if square != "--":
                piece = square[1]
                color = square[0]

                # Material score
                piece_value = piece_values[piece]

                # Positional score
                pos_score = 0
                if piece != "K":
                    piece_key = piece if piece != "p" else square
                    pos_score = piece_square_tables[piece_key][row][col] * 0.1

                total = piece_value + pos_score

                if color == "w":
                    score += total
                else:
                    score -= total

    # Bonus for having the move
    if gs.white_to_move:
        score += 0.1
    else:
        score -= 0.1

    return score


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


def main():
    """Run the game loop: handle input, run the AI, and draw the game."""
    p.init()
    p.display.set_caption("Chess with Evaluation")
    screen = p.display.set_mode(
        (EVAL_BAR_WIDTH + BOARD_WIDTH + MOVE_LOG_PANEL_WIDTH, BOARD_HEIGHT)
    )
    clock = p.time.Clock()
    screen.fill(p.Color("white"))
    move_log_font = p.font.SysFont("Arial", 20, False, False)
    gs = GameState()
    legal_moves = gs.get_legal_moves()
    # move_made: a flag variable that keep tracks if a valid move has been made
    # so we can generate another new set of valid moves
    move_made = False
    animate = False  # a flag to know when to use the animation function
    # we now load the images once before the (while true) loop
    load_images()
    running = True
    selected_square = ()  # simply to keep track of the last click for the user
    # player_clicks: is a list to keep track of player clicks
    # to act like a vector to move the piece from one square to another
    player_clicks = []
    game_over = False
    # if a human is playing, then this will be true
    # and if an AI is playing it'll be false
    white_is_human = True  # for white side
    black_is_human = False  # for black side - AI
    ai_thinking = False
    move_finder_process = None
    move_undone = False
    current_evaluation = 0.0  # Track current position evaluation

    while running:
        human_turn = (gs.white_to_move and white_is_human) or (
            not gs.white_to_move and black_is_human
        )
        for e in p.event.get():
            # handling the exit condition
            if e.type == p.QUIT:
                running = False
            # handle the user mouse input, simply the idea of click and go
            elif e.type == p.MOUSEBUTTONDOWN:
                if not game_over:
                    location = p.mouse.get_pos()  # like its (x, y) location
                    col = (
                        location[0] - EVAL_BAR_WIDTH
                    ) // SQ_SIZE  # ADJUSTED for eval bar
                    row = location[1] // SQ_SIZE
                    # the user clicks the same square twice or clicked on the move log or eval bar
                    if selected_square == (row, col) or col >= 8 or col < 0:
                        selected_square = ()  # so unselect that square
                        player_clicks = []  # reset that also
                    else:
                        selected_square = (row, col)
                        player_clicks.append(
                            selected_square
                        )  # append for both 1st and 2nd clicks
                    if (
                        len(player_clicks) == 2 and human_turn
                    ):  # after the second click, we need to move
                        # A promotion built from two clicks defaults to a queen,
                        # so it matches exactly one of the four promotion moves.
                        move = Move(player_clicks[0], player_clicks[1], gs.board)
                        for legal_move in legal_moves:
                            if move == legal_move:
                                gs.make_move(legal_move)
                                move_made = True
                                animate = True
                                selected_square = ()  # reset for the next turn
                                player_clicks = []  # reset for the next turn
                                break
                        if not move_made:
                            player_clicks = [selected_square]
            # handling the key presses like ctrl+z, etc..
            elif e.type == p.KEYDOWN:
                if e.key == p.K_z:  # undo: back to the human's previous turn
                    take_back_move(gs, white_is_human, black_is_human)
                    selected_square = ()
                    player_clicks = []
                    move_made = True
                    animate = False
                    game_over = False
                    if ai_thinking:
                        move_finder_process.terminate()
                        ai_thinking = False
                    move_undone = True
                if e.key == p.K_r:  # reset the board when r is pressed
                    gs = GameState()
                    legal_moves = gs.get_legal_moves()
                    selected_square = ()
                    player_clicks = []
                    move_made = False
                    animate = False
                    game_over = False
                    running = True
                    if ai_thinking:
                        move_finder_process.terminate()
                        ai_thinking = False
                    move_undone = False
                    current_evaluation = 0.0

        # handle the AI move finder
        if (
            not game_over
            and not human_turn
            and not move_undone
            and not move_made
            and not animate
        ):
            if not ai_thinking:
                ai_thinking = True
                print("AI thinking...")
                return_queue = Queue()  # is used to pass data between threads
                move_finder_process = Process(
                    target=search.find_best_move,
                    args=(gs, legal_moves, return_queue),
                )
                move_finder_process.start()

            # Check if the process has finished
            if not move_finder_process.is_alive():
                print("AI done thinking")
                ai_move = return_queue.get()
                if ai_move is None:
                    ai_move = search.find_random_move(legal_moves)
                gs.make_move(ai_move)
                move_made = True
                animate = True
                ai_thinking = False

        # generate the new set of valid moves when a user makes a valid move
        if move_made:
            if animate:
                animate_move(gs.move_log[-1], screen, gs.board, clock)
            legal_moves = gs.get_legal_moves()
            gs.update_game_status(legal_moves)
            # Evaluate after the status update so a checkmate shows as "M".
            current_evaluation = evaluate_position(gs)
            move_made = False
            animate = False
            move_undone = False

        draw_game_state(
            screen, gs, legal_moves, selected_square, move_log_font, current_evaluation
        )

        # check if the game ends either by stalemate or by a checkmate
        if gs.checkmate or gs.stalemate:
            game_over = True
            text = (
                "Stalemate"
                if gs.stalemate
                else "Black wins by checkmate"
                if gs.white_to_move
                else "White wins by checkmate"
            )
            draw_end_game_text(screen, text)

        clock.tick(MAX_FPS)
        p.display.flip()


def draw_game_state(
    screen, gs, legal_moves, selected_square, move_log_font, evaluation
):
    """Draw the evaluation bar, board, highlights, pieces and move log."""
    # Draw evaluation bar first (leftmost)
    draw_evaluation_bar(screen, evaluation)

    # Draw board and pieces (shifted right by EVAL_BAR_WIDTH)
    draw_board(screen)  # draw the squares on the board
    highlight_squares(screen, gs, legal_moves, selected_square)
    draw_pieces(screen, gs.board)  # draw the pieces on the top of the board

    # Draw move log (rightmost)
    draw_move_log(screen, gs, move_log_font)


def draw_board(screen):
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = BOARD_COLORS[(r + c) % 2]
            # Shift board right by EVAL_BAR_WIDTH
            p.draw.rect(
                screen,
                color,
                p.Rect(EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE),
            )


def highlight_squares(screen, gs, legal_moves, selected_square):
    """Highlight the selected square and the legal destinations of its piece."""
    if selected_square != ():
        r, c = selected_square
        # make sure that each user can use highlighting ability for its own pieces
        if gs.board[r][c][0] == ("w" if gs.white_to_move else "b"):
            # 1. highlight the selected square
            s = p.Surface((SQ_SIZE, SQ_SIZE))
            s.set_alpha(
                100
            )  # zero value is full transparent and 255 means no transparency
            s.fill(p.Color("blue"))
            screen.blit(s, (EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE))
            # 2. highlight moves from that selected square
            s.fill(p.Color("yellow"))
            for move in legal_moves:
                if (
                    move.start_row == r and move.start_col == c
                ):  # then those are the valid moves for that particular piece
                    screen.blit(
                        s,
                        (
                            EVAL_BAR_WIDTH + move.end_col * SQ_SIZE,
                            move.end_row * SQ_SIZE,
                        ),
                    )


def draw_pieces(screen, board):
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            piece = board[r][c]
            if piece != "--":  # it's really a piece and not an empty square
                screen.blit(
                    IMAGES[piece],
                    p.Rect(EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE),
                )


def animate_move(move, screen, board, clock):
    """Animate `move` sliding from its start square to its end square."""
    d_row = move.end_row - move.start_row
    d_col = move.end_col - move.start_col
    frames_per_square = 10  # frames to move one square
    frame_count = (abs(d_row) + abs(d_col)) * frames_per_square
    for frame in range(frame_count + 1):
        r, c = (
            move.start_row + d_row * frame / frame_count,
            move.start_col + d_col * frame / frame_count,
        )
        draw_board(screen)
        draw_pieces(screen, board)
        # erase the move from its ending square
        color = BOARD_COLORS[(move.end_row + move.end_col) % 2]
        end_square = p.Rect(
            EVAL_BAR_WIDTH + move.end_col * SQ_SIZE,
            move.end_row * SQ_SIZE,
            SQ_SIZE,
            SQ_SIZE,
        )
        p.draw.rect(screen, color, end_square)
        # draw the captured piece back onto the top of the rect
        if move.piece_captured != "--":
            if move.is_en_passant:
                en_passant_row = (
                    (move.end_row + 1)
                    if move.piece_captured[0] == "b"
                    else (move.end_row - 1)
                )
                end_square = p.Rect(
                    EVAL_BAR_WIDTH + move.end_col * SQ_SIZE,
                    en_passant_row * SQ_SIZE,
                    SQ_SIZE,
                    SQ_SIZE,
                )
            screen.blit(IMAGES[move.piece_captured], end_square)
        # draw the moving piece
        screen.blit(
            IMAGES[move.piece_moved],
            p.Rect(EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE),
        )
        p.display.flip()
        clock.tick(120)


def draw_end_game_text(screen, text):
    font = p.font.SysFont("Helvetica", 32, True, False)
    text_object = font.render(text, 0, p.Color("Gray"))
    board_centre = (EVAL_BAR_WIDTH + BOARD_WIDTH // 2, BOARD_HEIGHT // 2)
    text_location = text_object.get_rect(center=board_centre)
    screen.blit(text_object, text_location)
    text_object = font.render(text, 0, p.Color("Black"))
    screen.blit(text_object, text_location.move(2, 2))


def draw_move_log(screen, gs, font):
    move_log_rect = p.Rect(
        EVAL_BAR_WIDTH + BOARD_WIDTH, 0, MOVE_LOG_PANEL_WIDTH, MOVE_LOG_PANEL_HEIGHT
    )
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


if __name__ == "__main__":
    main()
