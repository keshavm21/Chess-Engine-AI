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

**Planned commits:**
```
refactor: move modules into chess_ai package
refactor: split SmartMoveFinder into search and evaluation modules
refactor: rename engine API to PEP 8 names
refactor: rename search and evaluation API to PEP 8 names
refactor: rename GUI functions and variables to PEP 8 names
refactor: add FEN parsing to the engine and use it in tests and benchmark
refactor: remove wildcard imports, path hacks and unused code
chore: reorganise image assets
style: format codebase with ruff
docs: fix README setup commands and remove inaccurate claims
docs: update agent guides for the new package layout
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

**Planned commits:**
```
fix: widen search window so faster mates are never cut off
fix: map row 0 to rank 8 in move notation
feat: generate underpromotion moves
refactor: separate legal move generation from game status detection
fix: undo a full move pair when playing against the AI
fix: centre the end-of-game message on the board
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

**Planned commits:**
```
perf: detect attacked squares by scanning from the target square
perf: use direct attack detection for legality and castling checks
perf: <profile-guided follow-up, if any>
feat: report perft speed and nodes per second in benchmark
docs: record performance results after attack-detection rewrite
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

**Planned commits:**
```
refactor: encapsulate search state in a Searcher class
refactor: convert alpha-beta search to negamax
feat: add iterative deepening with a time limit
feat: add difficulty presets based on search time
feat: report search statistics in benchmark
test: add tactics suite with solve-rate reporting
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

**Planned commits:**
```
feat: add self-play match script for comparing engine configurations
feat: add quiescence search over captures and promotions
feat: rewrite evaluation in centipawns with tapered piece-square tables
refactor: remove legacy tactical and hanging-piece evaluation terms
test: add evaluation symmetry and sanity tests
feat: drive the GUI evaluation bar from the engine evaluation
test: enforce tactics suite solve-rate threshold
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

**Planned commits:**
```
feat: maintain an incremental Zobrist position key
feat: detect draws by insufficient material, fifty-move rule and repetition
feat: score repetitions as draws inside the search
feat: add transposition table and remove the evaluation cache
feat: add killer-move and history move ordering
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

**Planned commits:**
```
refactor: restructure GUI main loop into an App state machine
fix: terminate the AI process cleanly on quit, reset and undo
feat: add promotion piece picker
feat: highlight last move and king in check, draw board coordinates
feat: add new-game options for side and difficulty
feat: add status line with search information
feat: show SAN move log with scrolling
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
