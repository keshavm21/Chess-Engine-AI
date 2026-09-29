# 03 — Implementation Plan

This document orders the changes from [02-proposed-changes.md](02-proposed-changes.md) into **phases**. A phase is a group of changes that belong together and end with the game fully working. The end of each phase is a merge point from `improve-chess-engine` into `main`.

Change IDs (`A1`, `D4`, …) refer to 02. Finding IDs (`R2`, `S1`, `G1`, …) refer to [01-current-state.md](01-current-state.md).

---

## Workflow for every phase

1. Work on `improve-chess-engine`.
2. For each task: inspect the code → make the smallest change that does the job → run the relevant tests → check the diff.
3. Claude does **not** commit. After each logical step Claude reports what changed and what was verified, and suggests a commit message. You review and commit.
4. At the end of the phase, run the **phase gate** below, then merge into `main` (for example `git checkout main && git merge --no-ff improve-chess-engine`) and update the status table in [README.md](README.md).

### Phase gate (definition of done)

- [ ] Full test suite passes (from Phase 1: `pytest`, including slow tests)
- [ ] CI is green (from Phase 1)
- [ ] Benchmark run, and the result recorded in `docs/benchmarks.md` (from Phase 1) whenever search or performance changed
- [ ] GUI smoke test (below) done by hand
- [ ] Docs affected by the phase updated (`CLAUDE.md`, `AGENTS.md`, this plan's status table)

### GUI smoke test (manual, ~3 minutes)

1. Launch the app. The board, pieces and eval bar render.
2. Play `e2e4`. The AI replies (within the time budget once Phase 5 lands).
3. Click an illegal destination. Nothing moves, and the selection behaves sensibly.
4. Castle; capture en passant; promote a pawn.
5. Undo (Z) returns to *your* previous turn. Reset (R) works, including while the AI is thinking.
6. Reach checkmate (or load a mate position) and check that the message is centred and correct.
7. Close the window while the AI is thinking. The app exits promptly.

---

## Phase 0 — Planning ✅ *(this change)*

`CLAUDE.md` plus these planning documents. Nothing in the code changes.

---

## Phase 1 — Safety net: tests, tooling, CI

**Goal:** make every later change quick to verify. **No change to game behaviour.**

| Task | IDs |
|---|---|
| Add `pyproject.toml` (pytest config: `testpaths`, `pythonpath = ["."]`, `slow` marker; minimal ruff lint config) and `requirements-dev.txt` (pytest, ruff) | G1, G6 |
| Relax the pygame pin (`pygame>=2.5,<3`) and settle the supported Python version (decision #2 in 02) | H1, H2 |
| Convert `tests/test_perft.py` and `tests/test_search.py` to pytest, keeping **every** case and the make/undo state-restoration check. Deep perft is marked `slow`. Move the FEN helper into `tests/conftest.py` | G1 |
| Write the missing attack-cache regression tests (stale-cache keys, off-turn en passant must not corrupt state) | G2 |
| Add perft position 3 (passes today) and positions 4 and 5 as `xfail(strict=True)` (underpromotion) | G3 |
| Add `xfail(strict=True)` regression tests for known bugs: mate-in-1 missed (S1, using the two FENs in 01), rank-8 notation (R2), game-over flags set by off-turn queries (R5) | — |
| Create `docs/benchmarks.md` holding the baseline from 01 §5 | C5 |
| GitHub Actions workflow: `ruff check .` + the **full** `pytest` suite (~35 s, so the deep perft doesn't need skipping) on push/PR for Python 3.10–3.13 | G5 |
| `.gitignore`: `.pytest_cache/`, `.ruff_cache/`, `.venv/` | H7 |

**Verification:** `pytest` → everything passes except the documented `xfail`s. CI green. The app runs exactly as before.

**Outcome (2026-09-28):** 28 passed, 10 strict xfails (4 × R1, 3 × R2, 1 × R5, 2 × S1), ~34 s; also run from a clean virtualenv built only from the requirements files. The new attack-cache tests were checked against the pre-fix code from `cad80b8^`, and 3 of 4 fail there as intended. Supported Python: 3.10–3.13 (pygame 2.6.1 has Linux wheels for exactly these). **Open item:** the local `venv/` is still macOS system Python 3.9.6. Recreate it with Python 3.12 before Phase 2 (`brew install python@3.12 && rm -rf venv && python3.12 -m venv venv && venv/bin/pip install -r requirements-dev.txt`).

**Planned commits:**
```
build: add pytest/ruff config and dev requirements, relax pygame pin
test: move suites to pytest, add perft positions 3-5, pin known bugs as xfails
test: add attack-cache and notation regression tests
ci: run lint and full test suite on GitHub Actions
docs: record baseline benchmarks and update guides for pytest
```

---

## Phase 2 — Structure and naming cleanup

**Goal:** the final package layout and PEP 8 names. **Behaviour must be identical.** Perft counts, benchmark node counts and chosen moves must not change at all, which is what makes such a large diff safe.

| Step | Task | IDs |
|---|---|---|
| 2.1 | `git mv` the files into `chess_ai/` (`engine.py`, `gui.py`, `benchmark.py`, `__main__.py`), with **only** the import changes needed to run, so Git detects the renames | A1 |
| 2.2 | Split `SmartMoveFinder.py` into `search.py` and `evaluation.py` (moving code only, no edits) | A2 |
| 2.3 | Rename identifiers to snake_case and fix typos: engine first, then search/evaluation, then GUI. Settle the final name map (02 §3.A) before starting | A3 |
| 2.4 | Move the FEN parser into the engine and add a FEN writer. Tests and benchmark use it | A7 |
| 2.5 | Remove the root `__init__.py`, the `sys.path` hack, `import *` and unused imports. Turn the bare strings into real docstrings | A4 |
| 2.6 | Move the piece sprites to `chess_ai/assets/pieces/` and the screenshots to `docs/images/` | A5 |
| 2.7 | Run `ruff format` on the whole codebase **as its own commit**, and list it in `.git-blame-ignore-revs` | G6 |
| 2.8 | Quick README fix: correct commands and filenames, remove false claims (TT, "configurable difficulty"). Update `AGENTS.md` / `CLAUDE.md` for the new layout | H3, H6 |

**Verification:** perft identical. `python -m chess_ai.benchmark` shows **identical nodes and moves** for all 4 positions. `git show -M --stat` lists renames, not delete + add. GUI smoke test passes.

**Outcome (2026-09-28):** 47 passed (the original 28 plus 19 new FEN tests), and the same 10 strict xfails. The benchmark on Python 3.12 gives identical nodes (1 018 / 2 015 / 2 742 / 3 989) and moves (b1c3 / g0f6 / e1c1 / e2a6) before and after the refactor. Git records the moves as renames at 95–100 % similarity. The GUI was driven headlessly through `python -m chess_ai`: a human move, then an AI reply from the child process, then quit, exit code 0. Deviations from the steps above:
- Because Claude doesn't commit, the phase is **3 commits instead of 11**. The pure moves are staged in the index so they can be committed alone, which keeps rename detection. The rest is split by file: code, then docs.
- Assets moved in the first commit (pure renames). `ruff format` ran as part of the code commit, so `.git-blame-ignore-revs` was skipped.
- Added ruff rule sets `N` (PEP 8 naming) and `I` (import order), plus `ruff format --check` in CI, so the new conventions are enforced.
- Removed dead code: `evaluation.is_square_attacked` (never called), an unused local in `king_safety`, and a debug `__main__` block.

**Planned commits:**
```
refactor: move modules and assets into the chess_ai package
refactor: split search/evaluation, adopt PEP 8 names, add FEN support
docs: fix README commands and update guides for the chess_ai package
```

---

## Phase 3 — Correctness fixes

**Goal:** fix every confirmed bug in the rules, the search and the GUI. The `xfail` tests from Phase 1 flip to passing.

| Task | IDs |
|---|---|
| Fix the mate-score window: widen the root bounds beyond any mate score, and make sure mate-in-1 is always preferred | D1 / S1 |
| Fix the rank-8 mapping. Update the `"e0e7"` assertion in the search test to `"e8e7"`; the old value encoded the bug | B1 / R2 |
| Underpromotion in the engine (4 promotion moves, promotion piece on `Move`, included in equality). The GUI defaults to a queen until the picker arrives in Phase 8 | B2 / R1 |
| Make legal-move generation side-effect free and add an explicit game-status query. Update the search and GUI to use it | B3 / R5 |
| GUI: undo against the AI steps back a full move; centre the end-of-game text | F1 / G1, F8 / G4 |

**Verification:** perft positions 4 and 5 now pass (and position 5 is added at depth 3). All former `xfail`s pass. Benchmark rerun; node counts may change because of D1 and B2, so record the new baseline. GUI smoke test (the GUI still promotes to a queen until Phase 8).

**Outcome (2026-09-28):** 90 passed, 0 xfails. All 10 former strict xfails now pass, and 33 new tests were added (Black mate-in-one cases, promotion, game status, GUI undo and centring). Perft positions 4 and 5 match up to depth 4 (422 333) and depth 3 (62 379). The benchmark node counts and chosen moves are **unchanged** in all four positions (the fixes only matter when a mate or promotion is in reach). GUI driven headlessly through two undo scenarios: the old code reproduced G1 (the AI replayed after Z), the fixed code returns to the start position. Notes:
- Underpromotion needed two guards so evaluation and ordering stay as they were: the tactical term counts a capture-promotion once (as the queen promotion), and only queen promotions get the ordering bonus.
- Bonus fix in the GUI: the eval bar is now computed after the game status, so a checkmate shows as "M" immediately.
- R6 (status decided before castling moves were added) is resolved as a side effect: `update_game_status()` looks at the complete legal move list.
- Commits: one per fix plus docs (6). Because Claude doesn't commit, each verified step was saved as a git tree object and committed from those.

**Planned commits:**
```
fix: widen root search window so faster mates are never cut off
fix: map row 0 to rank 8 in move notation
feat: generate underpromotion moves
refactor: separate legal move generation from game status detection
fix: undo a full move pair against the AI and centre the end-game message
docs: record Phase 3 results and update guides
```

---

## Phase 4 — Performance (same results, much faster)

**Goal:** remove the main bottleneck (01 §5.2) **without changing any search result**.

| Task | IDs |
|---|---|
| Profile first and record it (cProfile, start position + Kiwipete) | — |
| Direct `is_square_attacked()` using ray, knight, pawn and king scans | C1 |
| Use it for the legality filter, `in_check()` and castling | C2 |
| Re-profile. Then, only if the numbers justify it: cheaper move ordering and `__slots__` on `Move` | C3, C4 |
| Extend the benchmark: perft timing, nodes/s, optional JSON output | C5 |

**Verification:** perft identical. Benchmark nodes and moves **identical** to the end of Phase 3. Before/after timing table added to `docs/benchmarks.md`. Expect a several-fold speed-up; the actual factor gets measured, not assumed.

**Outcome (2026-09-28):** perft **11–15× faster**, search **12.6× faster** (45.0 s → 3.6 s for the four benchmark positions), with identical node counts and moves. Test suite ~4 s (was ~32 s). Checked against the pre-Phase-4 engine: legal move lists identical and in the same order on 20 002 random positions except for one R7 case, and `evaluate()` bit-for-bit identical on 3 031 positions. Notes:
- The benchmark was extended **first**, so before and after were measured with the same tool.
- New bug R7 (castling through a pawn-attacked square) was found while defining "same results"; the direct attack scan fixes it.
- Profile-guided follow-ups that paid off: sharing the side to move's legal moves between two evaluation terms (−19 % search time) and precomputed attack tables (−19 % search, −23–31 % perft). `__slots__` on `Move` and cheaper move ordering were **not** done: the profile showed them at ~5 % and ~1 %.

**Planned commits:**
```
feat: report perft speed and nodes per second in benchmark
perf: detect attacked squares by scanning from the target square
perf: check move legality without a full make/undo
perf: share legal move generation between evaluation terms
perf: precompute attack tables for knight, king and sliding pieces
docs: record Phase 4 performance results
```

---

## Phase 5 — Search framework

**Goal:** a clean, testable search API with **time-limited iterative deepening**. The engine now answers in a predictable time.

| Task | IDs |
|---|---|
| Replace the globals with a `Searcher` object that returns a `SearchResult` (move, score, depth, nodes, time) | A6 |
| Convert to negamax. At fixed depth it must give identical scores, moves and nodes to Phase 4 | D2 |
| Iterative deepening with a time limit: abort safely, use the last **completed** depth's move, order the root from the previous best move | D3 |
| Engine-side difficulty presets (time budgets). The GUI uses the default preset | D8 |
| Search statistics (depth reached, nodes/s, cutoffs) in the benchmark | C5 |
| Tactics suite (mate-in-1/2, win-material, avoid-blunder), reported as a solve rate; no threshold yet | G4 |

**Verification:** at fixed depth the results match Phase 4. A test checks that the time limit is respected and a legal move is always returned. Tactics solve rate recorded as the baseline for Phase 6. GUI smoke test.

**Outcome (2026-09-28):** 160 tests pass (60 new). Both refactors (the `Searcher` class, then negamax) are bit-identical to the old search: moves, scores and node counts on 76 reference searches. Iterative deepening gives the same score and move as a single search on all 20 depth-3 reference positions, for +1 % nodes. The time limit is honoured to within 0.04 s. An interrupted search restores the position exactly, and depth 1 always completes. Presets measured and set: easy 0.5 s (max depth 2), medium 2 s (default, used by the GUI), hard 5 s. Tactics baseline: 17/22 at depth 3, **19/22 (86 %) at 2 s**. The failures are two mate-in-3 puzzles and the poisoned-pawn traps (the horizon effect). GUI driven headlessly with the time-limited AI: moves, AI reply and both undo scenarios behave correctly. Notes:
- The search stops once half the time budget is used, because the next depth could not finish and unfinished depths are discarded. It also stops as soon as a forced mate is found.
- The tactics answers are not hand-written. An exhaustive solver computed them (a forced-mate search, or a material-only full-width search to 4 plies plus captures), and `tests/test_tactics.py` re-derives them, so a wrong answer cannot creep in.

**Commits:**
```
refactor: encapsulate search state in a Searcher class
refactor: convert alpha-beta search to negamax
feat: add iterative deepening with a time limit
feat: add difficulty presets based on search time
feat: report search depth and cutoffs in benchmark
test: add tactics suite with verified answers and solve-rate reporting
docs: record Phase 5 results and update guides
```

---

## Phase 6 — Tactical strength: quiescence and new evaluation

**Goal:** the big jump in playing strength. Everything is measured against Phase 5.

| Task | IDs |
|---|---|
| Self-play match script (`python -m chess_ai.match`) comparing two configurations from a set of opening positions, alternating colours | G7 |
| Quiescence search (captures and promotions, stand-pat, MVV-LVA ordering) | D4 |
| New evaluation in integer centipawns: material, tapered piece-square tables, pawn structure, bishop pair, rook files, pawn-shield king safety, tempo. Keep the old evaluation behind a flag until the match confirms the new one is better, then delete it | E1, A8 |
| Remove `tactical_score`, hanging-piece term, check bonus and legal-move attack maps; shrink the opening heuristics | E2, E3 |
| Resolve where the piece-square tables come from: attribute them or replace them | E6 |
| Evaluation tests (colour symmetry, sanity checks) | E5 |
| GUI eval bar shows the engine's evaluation/score; delete `evaluatePosition` from the GUI | E4 |
| Tactics suite threshold (≥ 90 %) becomes a `slow` test | G4 |

**Verification:** tests pass. Tactics solve rate meets the target. The self-play match against the Phase 5 configuration at equal time is clearly positive. Play-test a few full games by hand.

**Outcome (2026-09-29):**
- **Tests:** 222 pass.
- **Match:** the Phase 6 engine beat the Phase 5 engine **+17 =3 −0** at equal time (0.3 s/move, 20 games). With vs without quiescence: +19 =1 −0.
- **Tactics:** **22/22 at 2 s per move**, up from 19/22. The poisoned-pawn traps (the horizon effect) are solved even at depth 3.
- **Depth:** the default 2 s now reaches depth 4 in most middlegame positions (target met).
- **Evaluation speed:** 13× faster (21 µs vs 274 µs per call).

Notes:
- **Order changed:** the new evaluation came **before** quiescence. Quiescence multiplies evaluation calls, and the old evaluation (which generated legal moves) was far too slow for that.
- **Legacy evaluation:** the old evaluation stayed available as `legacy_evaluation.py` (the match tool's "phase5" configuration) until the match result was in. It was then deleted together with its attack-cache tests (`tests/test_attack_cache.py`); the code those tests covered no longer exists.
- **Piece-square tables:** they are now generated from simple, documented rules, which resolves E6/E8 (the Sunfish-derived tables are gone).
- **Mate scores:** they now count plies from the root (`CHECKMATE - ply`, `CHECKMATE = 100 000` centipawns). The same mate therefore scores the same at every iteration and inside quiescence, as the Phase 7 transposition table needs.
- **Quiescence cost:** in capture-heavy positions (Kiwipete), quiescence initially exploded: 98 % of nodes, with chains of up to 32 plies. Delta pruning plus skipping clearly losing captures cut Kiwipete's depth-3 search 4× with no change on the tactics suite. Captures are also searched first (MVV-LVA) at every ply.
- **Tactics threshold test:** it asserts that **every** puzzle is solved at the depth it needs in principle (2n − 1 plies for mate in n, 3 plies plus quiescence otherwise), not ≥ 90 % at a time limit. That's stricter, and it doesn't depend on CI machine speed. The time-limited solve rate is recorded in `docs/benchmarks.md`.
- **Flaky Phase 5 test fixed:** the interrupted-search test derived its time limit from a timing measurement, and it failed in 4 of 12 runs under CPU load. It now uses a fake clock, so it's deterministic (0 of 12 under the same load), and a mutation check confirms it still catches a missing position restore.

**Commits:**
```
test: make the interrupted-search test independent of machine load
feat: add self-play match tool for comparing engine configurations
feat: rewrite evaluation in centipawns with rule-based tapered tables
feat: add quiescence search with delta and losing-capture pruning
refactor: remove the legacy evaluation after it lost the comparison match
feat: drive the GUI evaluation bar from the engine evaluation
test: require every tactics puzzle to be solved at its required depth
docs: record Phase 6 results and update guides
```

---

## Phase 7 — Hashing, draw rules, transposition table

**Goal:** full draw rules, and a proper transposition table (TT) for speed and strength.

| Task | IDs |
|---|---|
| Incrementally updated Zobrist key, with tests: the key is restored after make/undo, and the same position reached by different move orders gives the same key | B5 |
| Draw rules: insufficient material, fifty-move rule (halfmove clock in state and FEN), threefold repetition. The GUI shows draw results | B4 |
| Repetition-aware search | D7 |
| Transposition table (depth, score, bound, best move; mate scores adjusted by ply) replacing `eval_cache`; TT move searched first | D5 |
| Killer moves / history heuristic. Keep only if the benchmark shows a gain | D6 |
| *(Could)* small opening book | D9 |

**Verification:** perft unchanged. Hash and draw tests pass. Fixed-depth benchmark shows fewer nodes, with TT hit rate reported. Self-play match against Phase 6 is not worse.

**Outcome (2026-09-29):**
- **Tests:** 290 pass.
- **Zobrist key:** it equals a from-scratch recomputation after every move and undo on 150 random games, and the perft undo check now covers it too.
- **Draw rules:** the engine has threefold repetition, the fifty-move rule (halfmove clock, now in FEN) and insufficient material; the GUI announces draws.
- **Draw-aware search:** tests show the losing side steers into a repetition, the winning side avoids one, and the engine won't trade into K+N v K. Each of these tests fails with the corresponding detection switched off.
- **Transposition table:** 27 % / 45 % fewer nodes at depth 3 / 4, with identical results on the benchmark positions, and exact mate distances with ply-adjusted scores.
- **Killer/history ordering:** −19 % time at depth 4.
- **Search speed and depth:** depth 3 is 22 % faster overall, and 19 of 20 positions reach depth 4+ at the default 2 s.
- **Tactics:** still 22/22.
- **Matches:** TT +10 =4 −6. Killer/history 19/40, no measurable change (kept for its benchmark gain, as the plan's criterion says). Against the Phase 6 configuration: **+11 =3 −6 (62 %)**, so the gate is met.

Notes:
- The evaluation cache was already removed in Phase 6, so the TT simply adds; it isn't used in the quiescence search.
- The search scores **any** repeated position as a draw (standard engine practice), while the game rule needs three occurrences.
- **FEN now has all six fields.** Tests that compared 4-field strings were updated, and the match tool uses the engine's draw rules instead of its own.
- The optional opening book (D9) was not done.
- **Follow-up fix (R8):** a game played on the Phase 6 code (the Phase 7 commits had landed on `main` only) never declared a repetition. That led to a real Phase 7 gap: the position key counted an en-passant square nobody could use, so a repetition whose first occurrence followed a two-square pawn move was counted one time too few. Fixed, with engine tests and an end-to-end game-window test (`play_scripted_game` in `tests/test_gui.py`), both confirmed to fail on the old code.

**Commits:**
```
feat: maintain an incremental Zobrist position key
feat: detect draws by threefold repetition, fifty-move rule and insufficient material
feat: score repetitions and other draws inside the search
feat: add a transposition table with ply-adjusted mate scores
feat: order quiet moves with killer moves and the history heuristic
docs: record Phase 7 results and update guides
```

---

## Phase 8 — GUI/UX and runtime robustness

**Goal:** an interface that looks and behaves like a finished product.

| Task | IDs |
|---|---|
| Refactor the main loop into a small `App` class with explicit states (human turn / AI thinking / animating / game over) in place of today's loose flags | F12 |
| Safe AI process lifecycle: terminate on quit, reset or undo; the child imports no GUI code; no console noise | F9 / G9, G10 |
| Promotion picker | F2 |
| Highlight the last move and a king in check; board coordinates | F3, F4 |
| New-game options: play as White or Black (board flip), difficulty | F5 |
| Status line (turn, AI thinking, depth and score) | F6 |
| SAN move log with scrolling | B6, F7 |
| *(Could)* drag-and-drop, on-screen shortcut help | F10, F11 |

**Verification:** SAN and notation unit tests (engine level). Full GUI smoke test, playing as both colours and at every difficulty.

**Outcome (2026-09-29):**
- **Tests:** 376 pass (82 new). The GUI is tested on pygame's dummy driver by feeding events to the `App`, with a fake AI process that runs the real search target.
- **SAN (B6):** `GameState.san()` reproduces the published score of a complete game (Morphy's Opera Game), gives every legal move a distinct SAN in 150 random positions, and leaves the position unchanged. Mutation checks: no disambiguation, pins ignored, missing `+`/`#` and unrestored flags are each caught.
- **App state machine (F12):** the refactor passed the unchanged end-to-end repetition tests before any feature was added. Animation became a state instead of a blocking loop, so quit, undo and new game work mid-animation.
- **AI lifecycle (F9, G9, G10):** quitting while the AI thinks now takes **0.07 s** instead of **1.95 s** (measured with a headless driver; up to the whole 5 s "hard" budget before). The search process is a daemon, and it is terminated and joined on quit, undo and new game. No "AI thinking…" prints and no pygame banner. A per-process probe showed the child imports neither pygame nor the GUI.
- **Smoke test:** driven headlessly with the real AI process, as White and as Black at each level: easy reached depth 2 at once, medium depth 4 in 2.0 s, hard depth 5 in 5.0 s; the board flips for Black and the AI opens.
- **Also done:** the *(Could)* items, drag and drop (F10) and help lines in the panel (F11).

Notes:
- **AI protocol:** the child process now runs `search.search_to_queue`, which returns the whole `SearchResult` (for the status line), or `None` if the search raised. `find_best_move` lost its `return_queue` parameter (only the GUI used it). If the process ends without an answer, the GUI plays a random legal move; before, `queue.get()` could wait forever.
- **Board palette:** the white/grey board became wood tones, to go with the new marks (last-move and selection tints, dots and rings for targets, a red glow for check). The result text got a dark band behind it, because the old grey text was hard to read over the pieces.
- **Harness:** `play_scripted_game` now plays either colour, clicks the real "Black" button, and waits for a game-ending move's animation to finish.

**Commits:**
```
feat: write moves in standard algebraic notation
refactor: restructure the GUI main loop into an App state machine
fix: stop the AI process cleanly on quit, undo and new game
feat: add a promotion piece picker
feat: highlight the last move and a king in check, draw board coordinates
feat: add new-game options for side and AI level
feat: show the AI's search in a status line
feat: show the moves in SAN in a scrolling move log
feat: move pieces by drag and drop, add help to the side panel
feat: show the game result on a banner over the board
docs: record Phase 8 results and update guides
```

---

## Phase 9 — Release polish (v1.0)

**Goal:** a portfolio-ready repository.

| Task | IDs |
|---|---|
| Final cleanup pass: dead code, stale comments, unused assets | — |
| `LICENSE` file (decision #4 in 02) | H5 |
| Final README: overview, GIF or screenshots, architecture diagram, how the search and evaluation work, benchmark table with environment, testing, known limitations | H4 |
| *(Could)* UCI mode | G9 |
| Mark this plan as complete, then tag `v1.0.0` on `main` | — |

**Planned commits:**
```
chore: remove dead code and unused assets
docs: add LICENSE
docs: rewrite README for v1.0
docs: mark improvement plan as complete
```

---

## How this relates to the external roadmap

`../chess_engine_repository_improvement_roadmap.txt` is still the high-level vision, and every item in it is covered here. This plan changes the **order** for these reasons:

| Change | Reason |
|---|---|
| Naming and structure moved from roadmap Phase 6 to **Phase 2** | Avoids renaming new code later; a pure rename is provably behaviour-preserving; it's easier to review on its own |
| pytest and CI moved from roadmap Phase 7 to **Phase 1** | Every later phase relies on quick, trustworthy verification |
| Rule bugs and underpromotion (roadmap Phase 4) moved **before** the search work | Correctness first; the mate-window bug is a search-correctness bug |
| Performance (§5 of 01) placed **before** quiescence and the TT | Quiescence multiplies evaluation calls; with today's evaluation (~4 ms per call) it wouldn't be practical |
| Evaluation rewrite paired with quiescence (Phase 6) | The current tactical evaluation terms exist to make up for the missing quiescence search; they should be replaced together |

If you approve this order, update `AGENTS.md` so it points to `docs/improvement-plan/` as the detailed plan.
