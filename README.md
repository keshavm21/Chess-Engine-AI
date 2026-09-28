# Python Chess AI (Minimax + Alpha-Beta Pruning)

This is a fully functional **Chess Engine** written in Python using `pygame`. It features a custom AI opponent that looks ahead using the **Minimax algorithm** with **Alpha-Beta pruning**, a quiescence search for tactics, and a positional evaluation.

- **Engine:** Handles move generation, validation, castling, en passant, promotion (including underpromotion), and checkmate/stalemate detection.
- **AI:** Minimax search (as negamax) with Alpha-Beta pruning, iterative deepening under a time limit (about 2 seconds per move by default), a quiescence search, move ordering, and a tapered positional evaluation.
- **UI:** Graphical interface with move logging, valid move highlighting, and a live evaluation bar showing the engine's own evaluation.
- **Platforms:** Developed on macOS; the test suite runs on Linux (Ubuntu) in CI. Windows is untested.

## Files
- `chess_ai/gui.py` — The GUI (pygame event loop, drawing, running the AI)
- `chess_ai/engine.py` — The game state (board, rules, legal move generation, FEN)
- `chess_ai/search.py` — The AI search (Minimax/negamax with Alpha-Beta pruning, iterative deepening, time limit, move ordering)
- `chess_ai/evaluation.py` — Position evaluation (material, piece-square tables, heuristics)
- `chess_ai/benchmark.py` — Performance benchmark (move generation and search)
- `chess_ai/tactics.py` — Tactics suite (puzzles with verified answers) to measure playing strength
- `chess_ai/match.py` — Self-play matches between two engine configurations
- `chess_ai/assets/pieces/` — Piece images (`wp.png`, `bK.png`, etc.)
- `tests/` — Test suite (pytest)
- `requirements.txt` / `requirements-dev.txt` — Runtime dependencies (pygame) / development tools (pytest, ruff)

## Installation & Setup

It is recommended to use a **virtual environment**.

### 1. Prerequisite
Ensure you have **Python 3.10 – 3.13** installed (pygame does not provide pre-built packages for 3.14 yet).

### 2. Create a Virtual Environment
This isolates the project dependencies from your system.

**Windows**
```powershell
# Open terminal in project folder
python -m venv venv
.\venv\Scripts\activate
```

**macOS / Ubuntu (Linux)**
```bash
# Open terminal in project folder
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Once the virtual environment is active (you should see `(venv)` in your terminal), install `pygame` using the provided requirements file:
```bash
pip install -r requirements.txt
```

## How to Run

To start the game, run this from the project folder:
```bash
python -m chess_ai
```

A window will open showing the chess board. You play as White (bottom), and the AI plays as Black (top).

## Controls
- **Mouse Left Click:** Select a piece / Make a move
- **Z:** Undo your last move (against the AI, this also takes back the AI's reply)
- **R:** Reset the board to the starting position

## AI & Heuristics
The AI (`chess_ai/search.py` and `chess_ai/evaluation.py`) combines the following techniques.

### Algorithm
- **Minimax with Alpha-Beta Pruning** — efficient search tree pruning, implemented as negamax
- **Iterative Deepening** — searches 1, 2, 3, … moves deep until the time limit and plays the best move of the deepest completed search
- **Quiescence Search** — at the end of the search, captures are played out until the position is quiet, so the engine does not misjudge positions in the middle of an exchange

### Evaluation (in centipawns)
- **Material** and **piece-square tables** (built from simple rules, e.g. knights prefer the centre), blended between middlegame and endgame tables as material comes off the board
- **Pawn Structure:** penalties for isolated or doubled pawns; bonuses for passed pawns that grow as they advance
- **Bishop Pair:** bonus for retaining both bishops
- **Rook Structure:** rooks on open or semi-open files get rewarded
- **King Safety:** a pawn shield in front of the king in the middlegame; the king centralises in the endgame

## Performance
- **Time per move:** difficulty presets in `chess_ai/search.py` (easy 0.5 s, medium 2 s, hard 5 s); the GUI uses medium, which typically reaches 3–5 half-moves deep

## Features
- Chess rules including special moves (castling, en passant, pawn promotion to any piece)
- Checkmate and stalemate detection
- Move validation and legal move generation
- Visual feedback for valid moves
- Move history with undo functionality
- AI opponent with a time limit per move (difficulty presets in `chess_ai/search.py`; the GUI uses medium)

## Running the Tests

```bash
pip install -r requirements-dev.txt
pytest                      # full test suite
python -m chess_ai.benchmark  # performance benchmark (a few seconds)
python -m chess_ai.tactics    # tactics suite solve rate (about a minute)
python -m chess_ai.match default no-quiescence --jobs 4   # self-play match between two engine configurations
```

## Known Limitations
- In the GUI, pawns always promote to a queen (the engine and AI support all promotion pieces)
- No threefold repetition, fifty-move rule, or insufficient-material draw detection
- The AI usually uses its full time (about 2 seconds per move); it answers sooner when it finds a forced mate or has only one legal move. How deep it gets depends on the position and the machine
- Depth beyond 3 may cause noticeable delays on slower systems

## License
This project is open source and available for educational purposes.