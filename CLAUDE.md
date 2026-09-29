# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project rules (workflow, git, testing, benchmarking, file-naming policy) live in `AGENTS.md` and apply in full. The detailed, phased plan is in `docs/improvement-plan/` (current state, proposed changes, implementation phases, status table). The high-level roadmap is outside the repo at `../chess_engine_repository_improvement_roadmap.txt`. Active work happens on the `improve-chess-engine` branch. Don't commit; suggest commit messages for the user to review.

## Commands

Supported Python: **3.10–3.13** (CI tests all four; pygame 2.6 has no 3.14 wheels). The local `venv/` is Python 3.12. Run everything from the repository root.

```bash
source venv/bin/activate              # or prefix commands with ./venv/bin/python
pip install -r requirements-dev.txt   # runtime (pygame) + dev tools (pytest, ruff)

python -m chess_ai                    # launch the GUI (human = White, AI = Black; Z = undo, R = reset)
python -m chess_ai.benchmark          # perft + fixed-depth and 1 s timed search (~10 s); --perft-only, --time-limit S, --json PATH; log results in docs/benchmarks.md
python -m chess_ai.tactics            # tactics suite solve rate at the default 2 s/move; --depth N for deterministic runs, --json PATH
python -m chess_ai.match A B --jobs 4  # self-play match between configurations in match.CONFIGS (default, depth-1, no-quiescence, no-tt, no-history); --time S, --depth N

pytest                                # full suite, ~55 s (this is what CI runs)
pytest -m "not slow"                  # skips deep perft, exhaustive tactics checks and depth-4 comparisons, ~6 s
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

Package `chess_ai/`: `engine.py` (rules), `search.py` (iterative-deepening negamax + quiescence), `evaluation.py` (scoring), `gui.py` (pygame), `benchmark.py`, `tactics.py` (verified puzzle suite), `match.py` (self-play matches), `__main__.py` (entry point). Piece sprites are in `chess_ai/assets/pieces/`.

### Board and move model (`engine.py`)
- `GameState.board` is an 8×8 list of 2-char strings: color (`w`/`b`) plus piece (`K Q R B N p`; pawns are lowercase). Empty squares are `"--"`. Row 0 is Black's back rank (rank 8), and row 7 is White's.
- `GameState.from_fen()` / `to_fen()` handle all six FEN fields (`halfmove_clock` and `fullmove_number` are tracked and restored by `undo_move`; the last two fields may be omitted when reading).
- `zobrist_key` is a 64-bit Zobrist hash of pieces, side to move, castling rights and en-passant file, updated incrementally in `make_move` (`_key_after`) and restored from `zobrist_log` on undo; `compute_zobrist_key()` recomputes it from scratch (tests compare the two). Keys come from a fixed-seed RNG, so they are identical in every run.
- Draw rules: `repetition_count()` (from `zobrist_log`, back to the last capture/pawn move, same side to move), `is_insufficient_material()` (K v K, K+minor v K, K+B v K+B on same-coloured squares) and `halfmove_clock >= 100`. `draw_by_rule()` returns the reason; `update_game_status()` stores it in `draw_reason` (checkmate takes precedence) and `undo_move` clears it.
- `Move` snapshots `piece_moved`/`piece_captured` from the board when it's constructed. Equality compares `move_id` (start/end squares) **and** `promotion_piece`.
- Promotions: `_add_pawn_move` emits one move per piece in `PROMOTION_PIECES` (Q, R, B, N, queen first). `Move(...)` defaults `promotion_piece` to `"Q"` (it's `None` for non-promotions), so a move built from two GUI clicks matches only the queen promotion. `coordinate_notation()` is UCI style (`e7e8n`), and `str(move)` adds `=N`.
- `get_move_priority` gives the promotion bonus to queen promotions only, and the quiescence search skips underpromotions.

### Legality, make/undo, and game-over flags
- `get_legal_moves(captures_only=False)` generates pseudo-legal moves and keeps those for which `_leaves_king_in_check(move)` is false. That helper only moves the piece on the board (plus the en-passant victim), asks `is_attacked_by()` about the king's square, and restores the squares; it deliberately skips the full `make_move`/`undo_move` bookkeeping. Castling moves are added afterwards by `_get_castle_moves` (not with `captures_only`, which the quiescence search uses).
- `is_attacked_by(r, c, by_white)` scans outward from the square using tables precomputed at import (`_KNIGHT_TARGETS`, `_KING_TARGETS`, `_STRAIGHT_LINES`, `_DIAGONAL_LINES`) and works for empty squares too. `is_square_attacked(r, c)` means "attacked by the side not to move". `tests/test_attacks.py` checks it against an independent piece-by-piece reference on random positions.
- Castling moves are added after the legality filter. `_get_castle_moves` checks castling rights and empty squares, but it never checks whether a rook is actually on the corner. Correct castling depends on `_update_castling_rights` revoking rights when a rook moves or is captured. The `rook_capture` perft case covers this.
- `undo_move` restores en passant and castling rights by popping `en_passant_log` and `castling_rights_log`. Any code that sets up a position by hand must reset those logs too; `from_fen` shows how.
- `get_legal_moves()` is a pure query and doesn't touch `checkmate` / `stalemate`. Those flags are set only by `update_game_status(legal_moves=None)`, which the GUI calls after every move; `undo_move` clears them. Never reintroduce side effects into move generation (finding R5).
- `test_perft.py` also snapshots the full state around every make/undo pair and checks it's restored exactly. Run it after touching `make_move`, `undo_move`, move generation, or castling/en passant logic.

### Search (`search.py`) and evaluation (`evaluation.py`)
- `Searcher(max_depth=None, time_limit=None, evaluator=None, quiescence=True, transposition_table=True, history_ordering=True).search(gs)` returns a `SearchResult` (move, score in centipawns from White's view, completed depth, nodes, cutoffs, elapsed, timed_out, qnodes, tt_hits). All search state lives on the `Searcher`; there are no module globals. `find_best_move(gs, legal_moves, return_queue=None, max_depth=None, time_limit=None)` is the thin wrapper the GUI runs in a child process (exceptions → `legal_moves[0]`). `evaluate_position(gs)` (a depth-0 search, i.e. quiescence; 0 for a draw by rule) drives the GUI's evaluation bar.
- Iterative deepening: depths 1, 2, 3, … up to `max_depth` (default `MAX_DEPTH` = 3 when there is no time limit, so tests and the benchmark are deterministic). The move of the last **completed** depth is played; depth 1 is never interrupted. The previous depth's best move is searched first. The search stops early on a forced mate, and once half the time budget is used (the next depth could not finish). On timeout `_negamax` raises `_SearchTimeoutError` at node entry, and `search()` restores the position by undoing moves back to the starting `move_log` length.
- `search_depth(gs, legal_moves, depth)` is one fixed-depth pass with an unbounded root window (±∞; a bounded window cut off faster mates, finding S1). `_negamax` scores from the side to move's view (`color` = ±1). It detects checkmate and stalemate from an empty `legal_moves` list, not from the flags. Mate scores count plies from the root: being mated `ply` plies away scores `-(CHECKMATE - ply)` (`CHECKMATE = 100_000`); `abs(score) >= MATE_THRESHOLD` means a forced mate.
- At depth 0 `_negamax` calls `_quiesce`: stand pat on the static evaluation, then captures and queen promotions in MVV-LVA order until quiet; when in check every evasion is searched (no stand pat), so mates are found. `_futile_capture` skips captures that cannot raise alpha even if the victim came for free (delta pruning, `DELTA_MARGIN`) and captures of a defended piece by a clearly more valuable one (`LOSING_CAPTURE_MARGIN`). The first quiescence ply reuses the parent's legal move list.
- Draws in the search (`_is_draw`): at every node except the root, the fifty-move rule, insufficient material or **any** repetition (count ≥ 2; the game rule needs 3) scores `DRAW` = 0, after the checkmate/stalemate check. The quiescence search returns 0 on insufficient material.
- Transposition table: `self.tt` maps `zobrist_key` → `(depth, score, bound, best_move)` with bounds `EXACT` / `LOWER_BOUND` / `UPPER_BOUND`. A stored result ends a node only at `ply > 0` when searched at least as deep and the bound decides the window; otherwise its move is searched first. Mate scores are stored relative to the node (`_score_to_tt` / `_score_from_tt`). Not used in quiescence; cleared when it reaches `TT_MAX_ENTRIES` (200 000).
- Difficulty presets: `DIFFICULTIES` (`easy` 0.5 s + depth cap 2, `medium` 2 s, `hard` 5 s) and `DEFAULT_DIFFICULTY`; calibrated in Phase 5 (see `docs/benchmarks.md`).
- Move ordering: the TT move first (at the root, the previous iteration's best move); then `get_move_priority` (MVV-LVA captures, promotions, checks, development, center; uses `ORDER_VALUES` in pawns) at the top two plies, where it does a make/undo per move to detect checks; deeper plies use `_quiet_order`: captures (MVV-LVA), then the two killer moves of that ply, then quiet moves by history score (`depth²` per piece and target square, reset per search). The quiescence search sorts captures with `_capture_order`.
- `evaluation.evaluate(gs)` returns integer centipawns from White's point of view and is a pure function of the board and side to move (no move generation, no caches). Terms: material, piece-square tables tapered between middlegame and endgame by `MAX_PHASE`, doubled/isolated/passed pawns, bishop pair, rooks on (half-)open files, a middlegame pawn shield, and `TEMPO`. The tables are generated from simple rules in the module (original, not copied from another engine). It must stay colour-symmetric: `tests/test_evaluation.py` checks `eval(mirror(pos)) == -eval(pos)`; `_divide` rounds toward zero for that reason.

### GUI (`gui.py`)
- The pygame loop runs the AI in a `multiprocessing.Process` and passes a `Queue` as `return_queue`. The search limits come from `gui.AI_DIFFICULTY` (the default preset until Phase 8 adds a selector). The `GameState` is pickled into the child process. Undo and reset terminate the running AI process.
- Undo goes through `take_back_move()`, which against the AI also takes back the AI's reply so the human is to move again. GUI logic that can be tested without a window lives in plain functions like this and is covered by `tests/test_gui.py` (pygame dummy video driver).
- The evaluation bar shows `search.evaluate_position(gs) / 100` (pawns): the engine's own evaluation with captures played out, recomputed after every move.
