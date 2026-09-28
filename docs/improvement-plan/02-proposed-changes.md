# 02 — Proposed Changes

What we want to change and why. The order of the work is in [03-implementation-plan.md](03-implementation-plan.md). Each ID below (e.g. `B3`) refers back to a finding in [01-current-state.md](01-current-state.md).

**Priority:** **Must** = needed for the portfolio goal · **Should** = clearly worth it · **Could** = nice to have, only if time allows.
**Origin:** **You** = requested by you · **Rec** = my recommendation.

---

## 1. The goal, made concrete

> A clean, working interface with a decent engine and readable code that holds up as a portfolio project. It isn't meant to be a top engine.

To make "decent" and "clean" something we can check, here are the targets for the finished project:

**Engine strength and behaviour**
1. Always finds a mate-in-1, and finds every mate-in-2 in the tactics test suite.
2. Doesn't lose material to simple 1–2 move tactics: solves at least 90 % of a small curated suite of tactics positions (forks, pins, hanging pieces, "don't take the poisoned pawn").
3. Replies within a configured time budget (default about 2–3 s per move) and never overruns it by more than a small margin.
4. Clearly beats today's engine in a self-play match at equal time.
5. Reaches depth 4 or more in typical middlegame positions at the default time. The exact number will be calibrated after the performance work (Phase 4).

**Code and project**
1. A consistent PEP 8 layout: snake_case modules and functions, UPPER_CASE constants, CapWords classes.
2. One authoritative source for each concept: one evaluation, one FEN parser, one set of piece values.
3. `pytest` runs everything, CI is green on every push, and a linter/formatter is enforced.
4. The README is accurate: every command works on a fresh clone, and no feature is claimed that doesn't exist.

---

## 2. Review of your requested changes

| Your request | Verdict | Notes |
|---|---|---|
| Fix bugs | ✅ **Agree** | Several real bugs were confirmed (see 01): slower mate chosen over mate-in-1, rank-8 notation, undo against the AI, "every attacked piece is hanging" in the evaluation, missing underpromotion. |
| Make the AI faster | ✅ **Agree, with a caveat** | About 85 % of search time is spent in check detection that generates every opponent move. Fixing that one mechanism is the big win. **Don't** go after micro-optimisations, and **don't** rewrite the board as bitboards or NumPy arrays: in pure Python neither beats a well-written list-based board, and either would be a rewrite of code that is already correct. Speed only matters because it buys search depth. Pair it with quiescence search and a better evaluation, or the engine gets faster without getting stronger. |
| Improve the chess UI | ✅ **Agree** | Stay with pygame. Fix the real bugs (undo, promotion, notation, end-text position) and add the expected basics (last-move and check highlights, coordinates, side and difficulty choice, draw messages). A web UI would be a rewrite, so it's out of scope for now (see §4). |
| Make file naming consistent | ✅ **Agree, and go further** | Rename the files *and* the functions and attributes (camelCase → snake_case), and fix the typos (`getRockMove`, `updateCastlRights`, `baord01.png`). I recommend doing this **early** (Phase 2), which is the one place I differ from the external roadmap; it puts naming near the end. The reasons: (a) every later change would otherwise be written in the old style and renamed afterwards; (b) a pure rename can be proven correct, because perft counts and benchmark node counts and chosen moves must stay *identical*; (c) it's much easier to review as its own isolated diff than mixed into feature work. |
| README had wrong setup commands | ✅ **Agree, in two steps** | Fix the factual errors (filenames, commands, false feature claims) in the same phase as the renames, since the commands change there. Do the full portfolio-quality README (screenshots, architecture, benchmarks) **last**, when things have settled. Your `AGENTS.md` also asks for this. |
| Willing to change a lot of code | ⚠️ **Agree, but not a from-scratch rewrite** | The rules engine is proven correct by perft and should be refactored, not replaced. The **evaluation** is the part worth rewriting almost entirely. The **search** should be rebuilt step by step, with tests at each step. |
| Work on `improve-chess-engine` and merge into `main` as features land | ✅ **Agree** | Merge at the **end of each phase** in [03](03-implementation-plan.md). Each phase leaves the game fully working, which makes it a safe merge point. |
| You commit, I suggest messages | ✅ **Agree** | Each phase in 03 lists the planned commits with suggested messages. |

---

## 3. Change catalogue

### A. Structure and naming

| ID | Change | Priority | Origin |
|---|---|---|---|
| A1 | Move the code into a `chess_ai/` package with snake_case modules (layout below). Launch with `python -m chess_ai`. | Must | You + Rec |
| A2 | Split `SmartMoveFinder.py` into `search.py` (search, move ordering, transposition table) and `evaluation.py` (static evaluation, piece-square tables). | Must | Rec |
| A3 | Rename identifiers to PEP 8 (examples below) and fix typos in names. | Must | You |
| A4 | Remove the root `__init__.py`, the `sys.path.append(".")` hack, `import *`, and unused imports. Turn the bare strings above methods into real docstrings. | Must | Rec |
| A5 | Move piece sprites into the package (`chess_ai/assets/pieces/`) and README screenshots into `docs/images/` (renaming `baord01.png`). | Should | Rec |
| A6 | Replace module-level search globals (`nextMove`, `nodesExplored`, `eval_cache`) with a `Searcher` object / `SearchResult` return value. | Must | Rec |
| A7 | One FEN parser (and a FEN writer) in the engine, replacing the three copies. | Must | Rec |
| A8 | Integer centipawn scores instead of float pawns. This is standard practice, avoids float comparison problems, and is needed for a clean transposition table. | Should | Rec |

Target layout:

```
Chess-Engine-AI/
├── chess_ai/
│   ├── __init__.py
│   ├── __main__.py        # `python -m chess_ai` → launches the GUI
│   ├── engine.py          # GameState, Move, CastlingRights, FEN, rules, Zobrist key
│   ├── search.py          # iterative deepening, alpha-beta, quiescence, TT, move ordering
│   ├── evaluation.py      # static evaluation + piece-square tables
│   ├── gui.py             # pygame front end
│   ├── benchmark.py       # `python -m chess_ai.benchmark`
│   └── assets/pieces/*.png
├── tests/                 # pytest
├── docs/
│   ├── improvement-plan/
│   └── images/            # README screenshots
├── .github/workflows/tests.yml
├── pyproject.toml         # pytest + ruff configuration
├── requirements.txt       # runtime: pygame
├── requirements-dev.txt   # dev: pytest, ruff
├── README.md  LICENSE  AGENTS.md  CLAUDE.md
```

Examples of the identifier rename. The final list gets settled at the start of Phase 2.

| Today | Proposed |
|---|---|
| `chessEngine.py` / `chessMain.py` / `SmartMoveFinder.py` | `chess_ai/engine.py` / `chess_ai/gui.py` / `chess_ai/search.py` + `chess_ai/evaluation.py` |
| `makeMove`, `undoMove`, `getValidMoves` | `make_move`, `undo_move`, `get_legal_moves` |
| `getAllPossibleMoves`, `getRockMove`, `getPawnMove` | `get_pseudo_legal_moves`, `_rook_moves`, `_pawn_moves` |
| `inCheck`, `squareUnderAttack`, `updateCastlRights` | `in_check`, `is_square_attacked`, `_update_castling_rights` |
| `whiteToMove`, `moveLog`, `enpassantPossible`, `currentCastlingRights` | `white_to_move`, `move_log`, `en_passant_square`, `castling_rights` |
| `Move.startRow`, `pieceMoved`, `isEnpassantMove`, `moveID`, `getChessNotation()` | `start_row`, `piece_moved`, `is_en_passant`, `move_id`, `to_uci()` |
| `CastleRights` | `CastlingRights` |
| `findBestMoveMinMax`, `scoreBoard`, `pieceScore`, `knightScores` | `find_best_move`, `evaluate`, `PIECE_VALUES`, `KNIGHT_TABLE` |

### B. Chess rules correctness

| ID | Change | Priority | Origin |
|---|---|---|---|
| B1 | Fix the rank-8 notation bug (R2). Update the `"e0e7"` assertion in `test_search.py`, because the test currently checks the buggy output. | Must | You (bugs) |
| B2 | Underpromotion: generate Q/R/B/N promotions, store the promotion piece on the `Move`, and include it in move equality. Add a GUI picker (F2). Perft positions 4 and 5 must then pass. | Must | Rec |
| B3 | Separate legal-move generation from game-status detection. `get_legal_moves()` should have no side effects, with a separate status query for checkmate/stalemate/draw (fixes R5). | Must | Rec |
| B4 | Draw rules: insufficient material, fifty-move rule (halfmove clock), threefold repetition (position-key history). | Should | Rec |
| B5 | Incrementally updated Zobrist position key covering pieces, side to move, castling rights and en passant. It's used for repetition detection (B4) and the transposition table (D4). | Should | Rec |
| B6 | Proper move-log notation (SAN): `+`, `#`, `=Q`, disambiguation, `O-O`. | Should | You (UI) |

### C. Performance (same results, less time)

| ID | Change | Priority | Origin |
|---|---|---|---|
| C1 | Direct `is_square_attacked(sq, by_color)`: scan outward from the target square along rays, plus knight, pawn and king offsets, instead of generating every opponent move. | Must | You (faster) |
| C2 | Use C1 for the legality filter (make → is my king attacked? → undo) and for castling checks. | Must | You (faster) |
| C3 | Move ordering without a make/undo per move. | Should | Rec |
| C4 | Cheaper `Move` objects (`__slots__`, fewer computed fields), guided by the profiler. | Could | Rec |
| C5 | Extend the benchmark: perft speed, nodes/s, depth reached in a fixed time, cutoffs, TT hits, and optional JSON output so before/after runs can be compared. | Should | Rec |

**Acceptance for C1–C4:** perft counts unchanged, benchmark node counts and chosen moves **identical**, time much lower.

### D. Search strength

| ID | Change | Priority | Origin |
|---|---|---|---|
| D1 | **Fix the mate-score window** (S1): root bounds must be wider than any mate score. Add a regression test using the two positions found in 01. | Must | Rec |
| D2 | Convert to negamax with a side-relative evaluation. It's the same algorithm as minimax, but half the code, and it makes D3/D4 simpler. It can be verified by identical scores and node counts at fixed depth. | Should | Rec |
| D3 | **Iterative deepening with a time limit.** Return the best move of the last *completed* depth, and order the root from the previous iteration's best move. | Must | Rec |
| D4 | **Quiescence search** (captures and promotions, stand-pat, MVV-LVA ordering). This is the single biggest strength gain available. | Must | Rec |
| D5 | **Transposition table** keyed by Zobrist (depth, score, bound type, best move), with mate scores adjusted by ply. It replaces `eval_cache`. | Should | Rec |
| D6 | Killer moves and a history heuristic. Keep them only if the benchmark shows fewer nodes. | Could | Rec |
| D7 | Repetition-aware search: treat repeated positions as draws inside the tree. | Should | Rec |
| D8 | Difficulty levels defined by time budget (and optionally max depth). | Must | You (UI) |
| D9 | Tiny built-in opening book (a few dozen common lines) for variety and sensible openings. | Could | Rec |

### E. Evaluation (rewrite, keeping it small and understandable)

| ID | Change | Priority | Origin |
|---|---|---|---|
| E1 | New `evaluation.py`: material + piece-square tables (tapered between middlegame and endgame so the king centralises late), pawn structure (doubled, isolated, passed), bishop pair, rooks on open files, pawn-shield king safety, small tempo bonus. | Must | Rec |
| E2 | **Remove** `tactical_score`, the hanging-piece term, the check bonus and the legal-move "attack maps" (E1/E2 in 01). Quiescence search handles tactics properly. | Must | Rec |
| E3 | Shrink or remove the hand-written opening bonuses (E4/E5). Good piece-square tables already encourage development and castling. | Should | Rec |
| E4 | Use one evaluation everywhere: the GUI eval bar shows the engine's evaluation or search score (fixes E7/G5). | Must | Rec |
| E5 | Evaluation tests: colour-symmetry (`eval(pos) == -eval(mirror(pos))`), and sanity checks such as "an extra queen scores higher". | Must | Rec |
| E6 | Resolve where the piece-square tables come from (E8): attribute Sunfish, or replace them with tables whose license is clear. | Must | Rec |

### F. GUI and UX

| ID | Change | Priority | Origin |
|---|---|---|---|
| F1 | Undo against the AI steps back a full move (your move + the AI's reply) (G1). | Must | You |
| F2 | Promotion picker (Q/R/B/N). | Must | You |
| F3 | Highlight the last move and a king in check. | Should | You |
| F4 | Board coordinates (a–h, 1–8). | Should | You |
| F5 | New-game options: play as White or Black (the board flips), difficulty level. | Should | You |
| F6 | Status line: whose turn, "AI thinking…", depth reached and score of the last search. | Should | You |
| F7 | SAN move log with scrolling (B6). | Should | You |
| F8 | Centre the end-of-game text (G4). Show messages for all results, including draws. | Must | You |
| F9 | Safe AI process lifecycle: terminate on quit, reset or undo; don't re-import the GUI in the child; remove console noise (G9/G10). | Must | Rec |
| F10 | Drag-and-drop moves in addition to click-click. | Could | You |
| F11 | Keyboard shortcuts shown on screen (Z undo, R reset, F flip). | Could | You |
| F12 | Restructure the GUI main loop into a small `App` class with explicit states instead of loose flags (`moveMade`, `moveUndone`, `AIThinking`, …). The G1 undo bug came from that tangle of flags. | Should | Rec |

### G. Tests and tooling

| ID | Change | Priority | Origin |
|---|---|---|---|
| G1 | Switch to pytest (a dev-only dependency): convert the scripts, add a `slow` marker for deep perft, and shared fixtures. | Must | Rec |
| G2 | Write the missing attack-cache regression tests (the empty `test_attack_cache.py`). Once the cache is removed in Phase 6, turn them into tests of the replacement. | Must | Rec |
| G3 | Expand perft: add position 3 now, and positions 4 and 5 as expected failures (`xfail`) that start passing once underpromotion lands. | Must | Rec |
| G4 | Tactics suite (mate-in-1/2, win-material, avoid-blunder positions) used as a strength regression test. | Must | Rec |
| G5 | GitHub Actions CI: fast tests on each push and PR, across supported Python versions. | Must | Rec |
| G6 | `ruff` for linting and formatting (a dev-only dependency), configured in `pyproject.toml`. | Should | Rec |
| G7 | Self-play match script (`python -m chess_ai.match`) to compare two engine configurations. | Should | Rec |
| G8 | Differential test against `python-chess` (a dev-only dependency) that compares legal move sets over random games. It's the strongest possible guard for B2–B4. | Could | Rec |
| G9 | Minimal UCI mode (`python -m chess_ai.uci`) so the engine can play in standard chess GUIs, or against Stockfish at low levels to estimate its strength. | Could | Rec |

### H. Setup and documentation

| ID | Change | Priority | Origin |
|---|---|---|---|
| H1 | Fix `requirements.txt` (`pygame>=2.5,<3`) and add `requirements-dev.txt`. | Must | You |
| H2 | Pick and state a supported Python version (recommended: 3.10+) and test it in CI. | Must | Rec |
| H3 | Quick README fix of the factual errors (filenames, commands, false claims), in Phase 2. | Must | You |
| H4 | Final README: overview, GIF or screenshots, architecture diagram, search and evaluation explanation, benchmark table with environment, testing, known limitations. | Must | You |
| H5 | Add a `LICENSE` file. The README says "open source", but there's no license, which legally means "all rights reserved". | Must | Rec |
| H6 | Keep `AGENTS.md`, `CLAUDE.md` and this plan in step with the new structure. | Must | Rec |
| H7 | `.gitignore`: add `.pytest_cache/`, `.ruff_cache/`, `.venv/`. | Should | Rec |

---

## 4. Out of scope (for now)

| Idea | Why not |
|---|---|
| Bitboard or NumPy board rewrite | Big rewrite of correct code, and little or no speed gain in pure Python |
| C/Cython/Rust extension, or PyPy as the target | Makes setup harder for anyone cloning the portfolio project; pygame support on PyPy is shaky |
| Neural-network or learned evaluation | Against the "understandable evaluation" goal, and far more effort than "decent" needs |
| Web UI / online play | A second front end is a separate project; it could be a follow-up after v1.0 |
| Endgame tablebases, pondering, multi-threaded search | Poor value for a portfolio engine |

---

## 5. Decisions needed from you

| # | Decision | My recommendation |
|---|---|---|
| 1 | Package layout (`chess_ai/` package) vs. flat snake_case files at the root (the external roadmap's version) | **Package**: cleaner imports, `python -m chess_ai`, no path hacks |
| 2 | Minimum Python version | **3.10+**. 3.9 is end-of-life, and the macOS system Python 3.9 is the only reason to keep it |
| 3 | Dev dependencies | **pytest + ruff** now; **python-chess** optional (dev-only, G8) |
| 4 | License | **MIT** recommended. Since Phase 6 the piece-square tables are original, so nothing ties the project to GPL-3.0 any more |
| 5 | Default AI time per move and difficulty levels | ✅ **Decided in Phase 5** from measurements: easy 0.5 s (depth cap 2), medium 2 s (default), hard 5 s |
| 6 | Keep the opening heuristics? | ✅ **Removed in Phase 6**; the piece-square tables and king tables do the work |
