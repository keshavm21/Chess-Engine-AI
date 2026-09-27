# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project rules (workflow, git, testing, benchmarking, file-naming policy) live in `AGENTS.md` and apply in full. The detailed, phased plan is in `docs/improvement-plan/` (current state, proposed changes, implementation phases, status table). The high-level roadmap is outside the repo at `../chess_engine_repository_improvement_roadmap.txt`. Active work happens on the `improve-chess-engine` branch. Don't commit; suggest commit messages for the user to review.

## Commands

Supported Python: **3.10–3.13** (CI tests all four; pygame 2.6 has no 3.14 wheels). The local `venv/` is still the macOS system Python 3.9.6 until it's recreated, so keep code 3.9-compatible until then.

```bash
source venv/bin/activate              # or prefix commands with ./venv/bin/python
pip install -r requirements-dev.txt   # runtime (pygame) + dev tools (pytest, ruff)

python chessMain.py                   # launch the GUI (human = White, AI = Black; Z = undo, R = reset)
python benchmark.py                   # search benchmark on 4 positions (~2 min at depth 3); log results in docs/benchmarks.md

pytest                                # full suite, ~35s (this is what CI runs)
pytest -m "not slow"                  # skips deep perft, ~6s
pytest tests/test_search.py::test_single_legal_move_is_still_immediate   # a single test
pytest "tests/test_perft.py::test_perft[kiwipete-d2]"                   # a single parametrized case
ruff check .                          # lint (CI runs this too)
ruff format tests                     # tests are format-clean; the app modules get formatted in Phase 2
```

The README says `ChessMain.py` / `ChessEngine.py`, but the real filenames are lowercase `chessMain.py` / `chessEngine.py`. macOS hides the difference; Linux doesn't.

### Test-suite conventions
- pytest config lives in `pyproject.toml` (`pythonpath = ["."]`, a `slow` marker, `xfail_strict = true`). Shared helpers are fixtures in `tests/conftest.py`: `load_fen(fen)` → `GameState`, `legal_move(gs, "e2e4")` → `Move`, `state_snapshot(gs)`.
- **Known bugs are pinned as strict `xfail` tests**, each citing its finding ID in `docs/improvement-plan/01-current-state.md` (R1 underpromotion, R2 rank-8 notation, R5 game-over flags, S1 mate window). When a fix lands, the test XPASSes and fails the run, so **remove the `xfail` mark as part of the fix**.
- These `xfail`s use `raises=AssertionError`. Setup and state-restoration failures use `pytest.fail()` so they can never pass as an expected failure. Keep that distinction in new tests.
- `pyproject.toml` has ruff per-file ignores for the legacy modules (wildcard and unused imports). Delete them when those modules are cleaned up in Phase 2.

## Architecture

### Board and move model (`chessEngine.py`)
- `GameState.board` is an 8×8 list of 2-char strings: color (`w`/`b`) plus piece (`K Q R B N p`; pawns are lowercase). Empty squares are `"--"`. Row 0 is Black's back rank (rank 8), and row 7 is White's.
- `Move` snapshots `pieceMoved`/`pieceCaptured` from the board when it's constructed. Equality compares only `moveID` (start/end squares).
- Bug R2: `Move.ranksToRows` maps `"0"` (not `"8"`) to row 0, so `getChessNotation()` prints rank 8 as `0` (e.g. `e0e7`). `tests/test_search.py` asserts on this string, and `tests/test_notation.py` pins the bug as an `xfail`. Test helpers convert square names with `conftest.square()` so they don't depend on it.
- Promotion always auto-queens inside `makeMove`, and no underpromotion moves are generated. That's why perft positions 4 and 5 are strict `xfail`s.

### Legality, make/undo, and game-over flags
- `getValidMoves()` generates pseudo-legal moves and then filters them by calling `makeMove` → `inCheck` → `undoMove` on each one. `squareUnderAttack` works by generating every opponent move, so attack checks are expensive.
- Castling moves are added after the legality filter. `getCastleMoves` checks castling rights and empty squares, but it never checks whether a rook is actually on the corner. Correct castling depends on `updateCastlRights` revoking rights when a rook moves or is captured. The `rook_capture` perft case covers this.
- `undoMove` restores en passant and castling rights by popping `enpassantPossibleLog` and `castleRightLog`. Any code that sets up a position by hand must reset those logs too; the FEN loaders show how.
- `getValidMoves()` has a side effect that search depends on: it sets `gs.checkmate` / `gs.stalemate`. `undoMove` clears both. The search's terminal-node check only works because it calls `getValidMoves()` right after each `makeMove`.
- The engine has no FEN parser yet (planned for Phase 2). Tests use `position_from_fen` in `tests/conftest.py`, and `benchmark.py` has its own copy.
- `test_perft.py` also snapshots the full state around every make/undo pair and asserts it's restored exactly. Run it after touching `makeMove`, `undoMove`, move generation, or castling/en passant logic.

### Search and evaluation (`SmartMoveFinder.py`)
- The entry point is `findBestMoveMinMax(gs, validMoves, returnQueue=None)`. It returns a single legal move immediately and otherwise runs `findMoveMinMaxAlphaBeta` at `MAX_DEPTH` (3). Exceptions are printed, and the function falls back to `validMoves[0]`.
- State lives in module-level globals. `nextMove` is only recorded when `depth == MAX_DEPTH`, so the root must be called with `MAX_DEPTH`. `nodesExplored` is reset on each search and read by `benchmark.py`.
- Move ordering (`get_move_priority`: MVV-LVA captures, promotions, checks, development, center) is applied only at the top two plies, and it does a make/undo per move to detect checks. Killer moves and a history heuristic aren't implemented, even though the latest commit message mentions them.
- `scoreBoard(gs, depth)` scores in pawn units (Q = 10), always from White's point of view. Mate scores are `±(CHECKMATE + depth)` (`CHECKMATE = 1000`) so the search prefers faster mates. Non-mate scores are clamped to ±`CHECKMATE`. The evaluation sums material and PSTs, bishop pair, rook files, opening principles, mobility, king safety, check bonus, pawn structure, and a tactical term.
- There are two caches:
  - `eval_cache` is module-level, persists across searches, and uses LFU eviction at 1000 entries. Its key is **board + side to move only**; castling rights and the en passant square aren't part of it.
  - `gs._attack_cache` is attached dynamically to the `GameState`. Its key comes from `_position_key` (board, side, en passant, castling), and it's cleared at the start of each `findBestMoveMinMax`. `get_all_attacks` builds it from *legal* moves (`getValidMoves`) after temporarily flipping `whiteToMove`, and it suppresses en passant for the side not on move so make/undo isn't corrupted.

### GUI (`chessMain.py`)
- The pygame loop runs the AI in a `multiprocessing.Process` and passes a `Queue` as `returnQueue`. The `GameState` is pickled into the child process, so globals the child sets (`nodesExplored`, `eval_cache`) never reach the GUI process. Undo and reset terminate the running AI process.
- The evaluation bar uses `chessMain.evaluatePosition()`, which is a separate, simpler evaluator (Q = 9, its own PSTs). It is **not** `SmartMoveFinder.scoreBoard`, so the bar doesn't reflect what the engine thinks.
