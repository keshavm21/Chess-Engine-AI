"""
This is our main driver. It will be responsible for handling user input
and displaying the current GameState object.
"""
import sys
import time

sys.path.append(".")

import chessEngine
import SmartMoveFinder

from chessEngine import *
from SmartMoveFinder import *
import pygame as p
import os
from multiprocessing import Process, Queue

# our current path information:
current_path = os.path.dirname(__file__)  # Where your .py file is located
image_path = os.path.join(current_path, "images")  # The image folder path

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


"""
As loading the images can be a costly process, we need to
initialize a global dictionary for images just once in the main.
Also, we put the loading images code in its own function, so we could
adapt that code easily later on or add another piece sets !!
"""


def loadImages():
    pieces = ["wp", "wN", "wB", "wR", "wQ", "wK", "bp", "bN", "bB", "bR", "bQ", "bK"]
    for piece in pieces:
        img = os.path.join(image_path, piece + ".png")
        IMAGES[piece] = p.transform.scale(p.image.load(img), (SQ_SIZE, SQ_SIZE))


def evaluatePosition(gs):
    """
    Evaluate the current position
    Returns a score where positive is good for white, negative for black
    Range: -1000 to +1000 (checkmate values)
    """
    # Check for game over
    if gs.checkmate:
        return -1000 if gs.whiteToMove else 1000
    elif gs.stalemate:
        return 0
    
    score = 0
    
    # Piece values
    pieceScore = {"K": 0, "Q": 9, "R": 5, "B": 3, "N": 3, "p": 1}
    
    # Position scores
    knightScores = [
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 2, 2, 2, 2, 2, 2, 1],
        [1, 2, 3, 3, 3, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 3, 3, 3, 2, 1],
        [1, 2, 2, 2, 2, 2, 2, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    ]
    
    bishopScores = [
        [4, 3, 2, 1, 1, 2, 3, 4],
        [3, 4, 3, 2, 2, 3, 4, 3],
        [2, 3, 4, 3, 3, 4, 3, 2],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [2, 3, 4, 3, 3, 4, 3, 2],
        [3, 4, 3, 2, 2, 3, 4, 3],
        [4, 3, 2, 1, 1, 2, 3, 4],
    ]
    
    queenScores = [
        [1, 1, 1, 3, 1, 1, 1, 1],
        [1, 2, 3, 3, 3, 1, 1, 1],
        [1, 4, 3, 3, 3, 4, 2, 1],
        [1, 2, 3, 3, 3, 2, 2, 1],
        [1, 2, 3, 3, 3, 2, 2, 1],
        [1, 4, 3, 3, 3, 4, 2, 1],
        [1, 1, 2, 3, 3, 1, 1, 1],
        [1, 1, 1, 3, 1, 1, 1, 1],
    ]
    
    rockScores = [
        [4, 3, 4, 4, 4, 4, 3, 4],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [4, 4, 4, 4, 4, 4, 4, 4],
        [4, 3, 4, 4, 4, 4, 3, 4],
    ]
    
    whitePawnScores = [
        [8, 8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8, 8],
        [5, 6, 6, 7, 7, 6, 6, 5],
        [2, 3, 3, 5, 5, 3, 3, 2],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [1, 1, 1, 0, 0, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ]
    
    blackPawnScores = [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 1, 0, 0, 1, 1, 1],
        [1, 1, 2, 3, 3, 2, 1, 1],
        [1, 2, 3, 4, 4, 3, 2, 1],
        [2, 3, 3, 5, 5, 3, 3, 2],
        [5, 6, 6, 7, 7, 6, 6, 5],
        [8, 8, 8, 8, 8, 8, 8, 8],
        [8, 8, 8, 8, 8, 8, 8, 8],
    ]
    
    piecePositionScores = {
        "N": knightScores,
        "B": bishopScores,
        "Q": queenScores,
        "R": rockScores,
        "bp": blackPawnScores,
        "wp": whitePawnScores,
    }
    
    # Calculate material and positional score
    for row in range(len(gs.board)):
        for col in range(len(gs.board[row])):
            square = gs.board[row][col]
            if square != "--":
                piece = square[1]
                color = square[0]
                
                # Material score
                piece_value = pieceScore[piece]
                
                # Positional score
                pos_score = 0
                if piece != "K":
                    piece_key = piece if piece != "p" else square
                    pos_score = piecePositionScores[piece_key][row][col] * 0.1
                
                total = piece_value + pos_score
                
                if color == "w":
                    score += total
                else:
                    score -= total
    
    # Bonus for having the move
    if gs.whiteToMove:
        score += 0.1
    else:
        score -= 0.1
    
    return score


def drawEvaluationBar(screen, evaluation):
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
    bg_color = p.Color("white") if text_color == p.Color("black") else p.Color(50, 50, 50)
    p.draw.rect(screen, bg_color, bg_rect)
    p.draw.rect(screen, p.Color(100, 100, 100), bg_rect, 1)
    
    screen.blit(text_surface, text_rect)


""" The following is the driver of our code which will handle user inputs and updating the graphics """


def main():
    p.init()
    p.display.set_caption("Chess with Evaluation")
    screen = p.display.set_mode((EVAL_BAR_WIDTH + BOARD_WIDTH + MOVE_LOG_PANEL_WIDTH, BOARD_HEIGHT))
    clock = p.time.Clock()
    screen.fill(p.Color("white"))
    moveLogFont = p.font.SysFont("Arial", 20, False, False)
    gs = GameState()
    validMoves = gs.getValidMoves()
    # moveMade: a flag variable that keep tracks if a valid move has been made
    # so we can generate another new set of valid moves
    moveMade = False
    animate = False  # a flag to know when to use the animation function
    # we now load the images once before the (while true) loop
    loadImages()
    running = True
    sqSelected = ()  # simply to keep track of the last click for the user
    # playerClicks: is a list to keep track of player clicks
    # to act like a vector to move the piece from one square to another
    playerClicks = []
    gameOver = False
    # if a human is playing, then this will be true
    # and if an AI is playing it'll be false
    playerOne = True  # for white side
    playerTwo = False  # for black side - AI
    AIThinking = False
    moveFinderProcess = None
    moveUndone = False
    currentEvaluation = 0.0  # Track current position evaluation
    
    while running:
        humanTurn = (gs.whiteToMove and playerOne) or (not gs.whiteToMove and playerTwo)
        for e in p.event.get():
            # handling the exit condition
            if e.type == p.QUIT:
                running = False
            # handle the user mouse input, simply the idea of click and go
            elif e.type == p.MOUSEBUTTONDOWN:
                if not gameOver:
                    location = p.mouse.get_pos()  # like its (x, y) location
                    col = (location[0] - EVAL_BAR_WIDTH) // SQ_SIZE  # ADJUSTED for eval bar
                    row = location[1] // SQ_SIZE
                    # the user clicks the same square twice or clicked on the move log or eval bar
                    if sqSelected == (row, col) or col >= 8 or col < 0:
                        sqSelected = ()  # so unselect that square
                        playerClicks = []  # reset that also
                    else:
                        sqSelected = (row, col)
                        playerClicks.append(
                            sqSelected
                        )  # append for both 1st and 2nd clicks
                    if (
                        len(playerClicks) == 2 and humanTurn
                    ):  # after the second click, we need to move
                        move = Move(playerClicks[0], playerClicks[1], gs.board)
                        for i in range(len(validMoves)):
                            if move == validMoves[i]:
                                gs.makeMove(validMoves[i])
                                moveMade = True
                                animate = True
                                sqSelected = ()  # reset for the next turn
                                playerClicks = []  # reset for the next turn
                        if not moveMade:
                            playerClicks = [sqSelected]
            # handling the key presses like ctrl+z, etc..
            elif e.type == p.KEYDOWN:
                if e.key == p.K_z:  # call undo when z is pressed
                    gs.undoMove()
                    sqSelected = ()
                    playerClicks = []
                    moveMade = True
                    animate = False
                    gameOver = False
                    if AIThinking:
                        moveFinderProcess.terminate()
                        AIThinking = False
                    moveUndone = True
                if e.key == p.K_r:  # reset the board when r is pressed
                    gs = GameState()
                    validMoves = gs.getValidMoves()
                    sqSelected = ()
                    playerClicks = []
                    moveMade = False
                    animate = False
                    gameOver = False
                    running = True
                    if AIThinking:
                        moveFinderProcess.terminate()
                        AIThinking = False
                    moveUndone = False
                    currentEvaluation = 0.0
        
        # handle the AI move finder
        if not gameOver and not humanTurn and not moveUndone and not moveMade and not animate:
            if not AIThinking:
                AIThinking = True
                print("AI thinking...")
                returnQueue = Queue()  # is used to pass data between threads
                moveFinderProcess = Process(
                    target=SmartMoveFinder.findBestMoveMinMax,
                    args=(gs, validMoves, returnQueue),
                )
                moveFinderProcess.start()
            
            # Check if the process has finished
            if not moveFinderProcess.is_alive():
                print("AI done thinking")
                AIMove = returnQueue.get()
                if AIMove is None:
                    AIMove = SmartMoveFinder.findRandomMoves(validMoves)
                gs.makeMove(AIMove)
                moveMade = True
                animate = True
                AIThinking = False
        
        # generate the new set of valid moves when a user makes a valid move
        if moveMade:
            # CRITICAL FIX: Update evaluation IMMEDIATELY after move is made
            currentEvaluation = evaluatePosition(gs)
            
            if animate:
                animateMove(gs.moveLog[-1], screen, gs.board, clock)
            validMoves = gs.getValidMoves()
            moveMade = False
            animate = False
            moveUndone = False
        
        drawGameState(screen, gs, validMoves, sqSelected, moveLogFont, currentEvaluation)
        
        # check if the game ends either by stalemate or by a checkmate
        if gs.checkmate or gs.stalemate:
            gameOver = True
            text = (
                "Stalemate"
                if gs.stalemate
                else "Black wins by checkmate"
                if gs.whiteToMove
                else "White wins by checkmate"
            )
            drawEndGameText(screen, text)
        
        clock.tick(MAX_FPS)
        p.display.flip()


""" responsible for the all the graphics needed for a current game state """


def drawGameState(screen, gs, validMoves, sqSelected, moveLogFont, evaluation):
    # Draw evaluation bar first (leftmost)
    drawEvaluationBar(screen, evaluation)
    
    # Draw board and pieces (shifted right by EVAL_BAR_WIDTH)
    drawBoard(screen)  # draw the squares on the board
    highlightSquares(screen, gs, validMoves, sqSelected)
    drawPieces(screen, gs.board)  # draw the pieces on the top of the board
    
    # Draw move log (rightmost)
    drawMoveLog(screen, gs, moveLogFont)


def drawBoard(screen):
    global colors
    colors = [p.Color("white"), p.Color("gray")]
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = colors[(r + c) % 2]
            # Shift board right by EVAL_BAR_WIDTH
            p.draw.rect(
                screen, color, 
                p.Rect(EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE)
            )


""" highlight the square selected and valid moves for the piece selected """


def highlightSquares(screen, gs, validMoves, sqSelected):
    if sqSelected != ():
        r, c = sqSelected
        # make sure that each user can use highlighting ability for its own pieces
        if gs.board[r][c][0] == ("w" if gs.whiteToMove else "b"):
            # 1. highlight the selected square
            s = p.Surface((SQ_SIZE, SQ_SIZE))
            s.set_alpha(
                100
            )  # zero value is full transparent and 255 means no transparency
            s.fill(p.Color("blue"))
            screen.blit(s, (EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE))
            # 2. highlight moves from that selected square
            s.fill(p.Color("yellow"))
            for move in validMoves:
                if (
                    move.startRow == r and move.startCol == c
                ):  # then those are the valid moves for that particular piece
                    screen.blit(s, (EVAL_BAR_WIDTH + move.endCol * SQ_SIZE, move.endRow * SQ_SIZE))


def drawPieces(screen, board):
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            piece = board[r][c]
            if piece != "--":  # it's really a piece and not an empty square
                screen.blit(
                    IMAGES[piece], 
                    p.Rect(EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE)
                )


""" the animation function """


def animateMove(move, screen, board, clock):
    global colors
    dR = move.endRow - move.startRow
    dC = move.endCol - move.startCol
    framesPerSquare = 10  # frames to move one square
    frameCount = (abs(dR) + abs(dC)) * framesPerSquare
    for frame in range(frameCount + 1):
        r, c = (
            move.startRow + dR * frame / frameCount,
            move.startCol + dC * frame / frameCount,
        )
        drawBoard(screen)
        drawPieces(screen, board)
        # erase the move from its ending square
        color = colors[(move.endRow + move.endCol) % 2]
        endSquare = p.Rect(
            EVAL_BAR_WIDTH + move.endCol * SQ_SIZE, move.endRow * SQ_SIZE, SQ_SIZE, SQ_SIZE
        )
        p.draw.rect(screen, color, endSquare)
        # draw the captured piece back onto the top of the rect
        if move.pieceCaptured != "--":
            if move.isEnpassantMove:
                enpassantRow = (
                    (move.endRow + 1)
                    if move.pieceCaptured[0] == "b"
                    else (move.endRow - 1)
                )
                endSquare = p.Rect(
                    EVAL_BAR_WIDTH + move.endCol * SQ_SIZE, enpassantRow * SQ_SIZE, SQ_SIZE, SQ_SIZE
                )
            screen.blit(IMAGES[move.pieceCaptured], endSquare)
        # draw the moving piece
        screen.blit(
            IMAGES[move.pieceMoved], 
            p.Rect(EVAL_BAR_WIDTH + c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE)
        )
        p.display.flip()
        clock.tick(120)


def drawEndGameText(screen, text):
    font = p.font.SysFont("Helvetica", 32, True, False)
    textObject = font.render(text, 0, p.Color("Gray"))
    textLocation = p.Rect(EVAL_BAR_WIDTH, 0, BOARD_WIDTH, BOARD_HEIGHT).move(
        EVAL_BAR_WIDTH + BOARD_WIDTH / 2 - textObject.get_width() / 2,
        BOARD_HEIGHT / 2 - textObject.get_height() / 2,
    )
    screen.blit(textObject, textLocation)
    textObject = font.render(text, 0, p.Color("Black"))
    screen.blit(textObject, textLocation.move(2, 2))


def drawMoveLog(screen, gs, font):
    moveLogRect = p.Rect(
        EVAL_BAR_WIDTH + BOARD_WIDTH, 0, 
        MOVE_LOG_PANEL_WIDTH, MOVE_LOG_PANEL_HEIGHT
    )
    p.draw.rect(screen, p.Color("black"), moveLogRect)
    moveLog = gs.moveLog
    moveTexts = []
    for i in range(0, len(moveLog), 2):
        moveString = str(i // 2 + 1) + ". " + str(moveLog[i]) + " "
        if i + 1 < len(moveLog):
            moveString += str(moveLog[i + 1])
        moveTexts.append(moveString)
    padding = 5
    textY = padding
    lineSpacing = 5
    movesPerRow = 3
    for i in range(0, len(moveTexts), movesPerRow):
        text = ""
        for j in range(movesPerRow):
            if i + j < len(moveTexts):
                text += moveTexts[i + j] + "  "
        textObject = font.render(text, True, p.Color("white"))
        textLocation = moveLogRect.move(padding, textY)
        screen.blit(textObject, textLocation)
        textY += textObject.get_height() + lineSpacing


if __name__ == "__main__":
    main()

