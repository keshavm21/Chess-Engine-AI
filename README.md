# Python Chess AI (Minimax + Alpha-Beta Pruning)

This is a fully functional **Chess Engine** written in Python using `pygame`. It features a custom AI opponent capable of looking ahead using the **Minimax algorithm** with **Alpha-Beta pruning** and advanced positional evaluation heuristics.

- **Engine:** Handles move generation, validation, castling, en passant, promotion (to a queen), and checkmate/stalemate detection.
- **AI:** Minimax search (depth 3) with Alpha-Beta pruning, move ordering, an evaluation cache, and opening principles.
- **UI:** Graphical interface with move logging, valid move highlighting, and a live evaluation bar.
- **Platforms:** Developed on macOS; the test suite runs on Linux (Ubuntu) in CI. Windows is untested.

## Files
- `chess_ai/gui.py` — The GUI (pygame event loop, drawing, running the AI)
- `chess_ai/engine.py` — The game state (board, rules, legal move generation, FEN)
- `chess_ai/search.py` — The AI search (Minimax with Alpha-Beta pruning, move ordering)
- `chess_ai/evaluation.py` — Position evaluation (material, piece-square tables, heuristics)
- `chess_ai/benchmark.py` — Search benchmark
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
- **Z:** Undo the last move (see Known Limitations)
- **R:** Reset the board to the starting position

## AI & Heuristics
The AI (`chess_ai/search.py` and `chess_ai/evaluation.py`) combines the following techniques.

### Algorithm
- **Minimax with Alpha-Beta Pruning** — efficient search tree pruning

### Piece-Square Tables
- Encourages knights to develop toward the center
- Incentivizes pawn advancement

### Opening Principles
- Penalizes early queen moves
- Rewards early development of minor pieces (Knights/Bishops)
- Rewards early castling

### Positional Evaluation
- **Bishop Pair:** bonus for retaining both bishops
- **Rook Structure:** rooks on open or semi-open files get rewarded
- **King Safety:** penalties for exposed kings; bonuses for pawn shields
- **Pawn Structure:** penalties for isolated or doubled pawns; bonuses for passed pawns

## Performance
- **Depth:** Default search depth is 3 half-moves (`MAX_DEPTH` in `chess_ai/search.py`)
- **Caching:** Evaluations of previously seen board positions are cached during a search

## Features
- Chess rules including special moves (castling, en passant, pawn promotion to a queen)
- Checkmate and stalemate detection
- Move validation and legal move generation
- Visual feedback for valid moves
- Move history with undo functionality
- AI opponent (search depth set by `MAX_DEPTH` in `chess_ai/search.py`)

## Running the Tests

```bash
pip install -r requirements-dev.txt
pytest                      # full test suite
python -m chess_ai.benchmark  # search benchmark (takes a minute or two)
```

## Known Limitations
- Pawns always promote to a queen (no underpromotion)
- No threefold repetition, fifty-move rule, or insufficient-material draw detection
- Undo takes back one half-move; against the AI, the AI then moves again, so press **Z** a second time while it is thinking to return to your own move
- AI computation time depends on the position and the machine (from a couple of seconds to over 20 seconds per move at depth 3 on an Apple M1)
- Depth beyond 3 may cause noticeable delays on slower systems

## License
This project is open source and available for educational purposes.