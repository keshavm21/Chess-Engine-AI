# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project rules (workflow, git, testing, benchmarking, file-naming policy) live in `AGENTS.md` and apply in full. The detailed, phased plan is in `docs/improvement-plan/` (current state, proposed changes, implementation phases, status table). The high-level roadmap is outside the repo at `../chess_engine_repository_improvement_roadmap.txt`. Active work happens on the `improve-chess-engine` branch. Don't commit; suggest commit messages for the user to review.

## Commands

Supported Python: **3.10–3.13** (CI tests all four; pygame 2.6 has no 3.14 wheels). The local `venv/` is Python 3.12. Run everything from the repository root.

```bash
source venv/bin/activate              # or prefix commands with ./venv/bin/python
pip install -r requirements-dev.txt   # runtime (pygame) + dev tools (pytest, ruff)

python -m chess_ai                    # launch the GUI (human = White, AI = Black; Z = undo, R = reset)
python -m chess_ai.benchmark          # search benchmark on 4 positions (~45 s at depth 3); log results in docs/benchmarks.md

pytest                                # full suite, ~32 s (this is what CI runs)
pytest -m "not slow"                  # skips deep perft, ~6 s
pytest tests/test_search.py::test_single_legal_move_is_still_immediate   # a single test
pytest "tests/test_perft.py::test_perft[kiwipete-d2]"                   # a single parametrized case
ruff check .                          # lint, including PEP 8 naming (N) and import order (I)
ruff format .                         # formatter; CI runs `ruff format --check .`
```

### Test-suite conventions
- pytest config lives in `pyproject.toml` (`pythonpath = ["."]`, a `slow` marker, `xfail_strict = true`). Shared helpers are fixtures in `tests/conftest.py`: `load_fen(fen)` → `GameState` (it is `GameState.from_fen`), `legal_move(gs, "e2e4")` → `Move`, `state_snapshot(gs)`.
- **Pin newly found bugs as strict `xfail` tests** citing a finding ID in `docs/improvement-plan/01-current-state.md`. When the fix lands the test XPASSes and fails the run, so remove the `xfail` mark as part of the fix. (Phase 3 fixed every bug pinned this way so far; none are left.)
- These `xfail`s use `raises=AssertionError`. Setup and state-restoration failures use `pytest.fail()` so they can never pass as an expected failure. Keep that distinction in new tests.
- A pure refactor must leave the benchmark's node counts and chosen moves identical; the search is deterministic.

## Architecture

Package `chess_ai/`: `engine.py` (rules), `search.py` (alpha-beta), `evaluation.py` (scoring), `gui.py` (pygame), `benchmark.py`, `__main__.py` (entry point). Piece sprites are in `chess_ai/assets/pieces/`.

### Board and move model (`engine.py`)
- `GameState.board` is an 8×8 list of 2-char strings: color (`w`/`b`) plus piece (`K Q R B N p`; pawns are lowercase). Empty squares are `"--"`. Row 0 is Black's back rank (rank 8), and row 7 is White's.
- `GameState.from_fen()` / `to_fen()` handle the four FEN fields the engine tracks. There's no halfmove clock or move number yet.
- `Move` snapshots `piece_moved`/`piece_captured` from the board when it's constructed. Equality compares `move_id` (start/end squares) **and** `promotion_piece`.
- Promotions: `_add_pawn_move` emits one move per piece in `PROMOTION_PIECES` (Q, R, B, N, queen first). `Move(...)` defaults `promotion_piece` to `"Q"` (it's `None` for non-promotions), so a move built from two GUI clicks matches only the queen promotion. `coordinate_notation()` is UCI style (`e7e8n`), and `str(move)` adds `=N`.
- To keep evaluation and ordering as they were, `tactical_score` counts a capture-promotion only once (as the queen promotion), and `get_move_priority` gives the promotion bonus to queen promotions only.

### Legality, make/undo, and game-over flags
- `get_legal_moves()` generates pseudo-legal moves and then filters them by calling `make_move` → `in_check` → `undo_move` on each one. `is_square_attacked` works by generating every opponent move, so attack checks are expensive; this is the main performance bottleneck (Phase 4).
- Castling moves are added after the legality filter. `_get_castle_moves` checks castling rights and empty squares, but it never checks whether a rook is actually on the corner. Correct castling depends on `_update_castling_rights` revoking rights when a rook moves or is captured. The `rook_capture` perft case covers this.
- `undo_move` restores en passant and castling rights by popping `en_passant_log` and `castling_rights_log`. Any code that sets up a position by hand must reset those logs too; `from_fen` shows how.
- `get_legal_moves()` is a pure query and doesn't touch `checkmate` / `stalemate`. Those flags are set only by `update_game_status(legal_moves=None)`, which the GUI calls after every move; `undo_move` clears them. Never reintroduce side effects into move generation: the evaluation generates moves for the side *not* to move (finding R5).
- `test_perft.py` also snapshots the full state around every make/undo pair and checks it's restored exactly. Run it after touching `make_move`, `undo_move`, move generation, or castling/en passant logic.

### Search (`search.py`) and evaluation (`evaluation.py`)
- The entry point is `search.find_best_move(gs, legal_moves, return_queue=None)`. It returns a single legal move immediately and otherwise runs `minimax_alpha_beta` at `MAX_DEPTH` (3) with an unbounded root window (±∞; a ±`CHECKMATE` window cut off faster mates, finding S1). Exceptions are printed, and the function falls back to `legal_moves[0]`.
- `minimax_alpha_beta` detects checkmate and stalemate from an empty `legal_moves` list (`mate_score()` / `STALEMATE`), not from the flags.
- Search state lives in module-level globals. `next_move` is only recorded when `depth == MAX_DEPTH`, so the root must be called with `MAX_DEPTH`. `nodes_explored` is reset on each search and read by the benchmark.
- Move ordering (`get_move_priority`: MVV-LVA captures, promotions, checks, development, center) is applied only at the top two plies, and it does a make/undo per move to detect checks. Killer moves and a history heuristic aren't implemented, even though an old commit message mentions them.
- `evaluation.evaluate(gs, depth)` scores in pawn units (Q = 10), always from White's point of view. Mate scores are `±(CHECKMATE + depth)` (`CHECKMATE = 1000`, from `mate_score()`) so the search prefers faster mates. Non-mate scores are clamped to ±`CHECKMATE`. The evaluation sums material and PSTs, bishop pair, rook files, opening principles, mobility, king safety, check bonus, pawn structure, and a tactical term.
- There are two caches, both in `evaluation.py`:
  - `eval_cache` is module-level, persists across searches, and uses LFU eviction at 1000 entries. Its key is **board + side to move only**; castling rights and the en passant square aren't part of it.
  - `gs._attack_cache` is attached dynamically to the `GameState`. Its key comes from `_position_key` (board, side, en passant, castling), and `search.find_best_move` clears it through `clear_attack_cache()` before each search. `get_all_attacks` builds it from *legal* moves (`get_legal_moves`) after temporarily flipping `white_to_move`, and it suppresses en passant for the side not on move so make/undo isn't corrupted.

### GUI (`gui.py`)
- The pygame loop runs the AI in a `multiprocessing.Process` and passes a `Queue` as `return_queue`. The `GameState` is pickled into the child process, so globals the child sets (`nodes_explored`, `eval_cache`) never reach the GUI process. Undo and reset terminate the running AI process.
- Undo goes through `take_back_move()`, which against the AI also takes back the AI's reply so the human is to move again. GUI logic that can be tested without a window lives in plain functions like this and is covered by `tests/test_gui.py` (pygame dummy video driver).
- The evaluation bar uses `gui.evaluate_position()`, which is a separate, simpler evaluator (Q = 9, its own PSTs). It is **not** `evaluation.evaluate`, so the bar doesn't reflect what the engine thinks.
