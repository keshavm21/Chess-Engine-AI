# 01 — Current State

A snapshot of the repository as it is today, before the improvement work starts.
Every finding in this document was checked against the code or by running it. Anything I only inferred from reading the code is labelled *(from reading the code)* or *(not yet verified)*.

> **Status:** Phase 3 fixed R1, R2, R5, R6, S1, G1 and G4 (marked ✅ below). Phase 4 found and fixed R7, and made move generation and search 11–15× faster (see [benchmarks](../benchmarks.md)). Phase 6 replaced the evaluation (E1–E8, G5) and added quiescence (S2). Phase 7 added the draw rules (R3, G8). A late-repetition bug in them (R8) was fixed right after. Phase 8 fixed the remaining GUI findings (G2, G3, G6, G7, G9, G10). **Every finding is now fixed; the plan is complete (v1.0.0).**
>
> **Note:** this is a snapshot from before Phase 2. File and function names here are the old ones (`chessEngine.py`, `getValidMoves`, …). Phase 2 moved the code into the `chess_ai/` package and renamed identifiers to PEP 8; the bugs listed here are otherwise unchanged until the phase that fixes them.

| | |
|---|---|
| Snapshot date | 2026-09-28 |
| Commit | `ea7a5a1` (`main` and `improve-chess-engine` point at the same commit) |
| Machine used for measurements | Apple M1, macOS, Python 3.9.6 (the project `venv/`), pygame 2.6.1 |

---

## 1. Summary

The project is a **working, playable** pygame chess app with a custom engine and an alpha-beta AI.

- **Move generation is correct**, apart from one missing rule (underpromotion). It passes perft on four standard positions, including the hard "position 3" en passant and pin cases.
- **The AI is very slow**: 61–190 nodes/second, and 5–64 seconds per move at depth 3. At depth 3 with no quiescence search it's also tactically shallow.
- **The evaluation is noisy.** Several heuristics are built on attack maps that don't measure what their names suggest.
- **The GUI is functional but basic.** It has a few real bugs (undo against the AI, rank-8 notation) and lacks common features (promotion choice, highlights, side and difficulty selection).
- **Naming and structure are inconsistent.** Module names use three different styles, and camelCase and snake_case are mixed.
- **Tests exist but are plain scripts.** There's no pytest, no CI and no linter. One test file is empty.
- **The README has wrong commands and describes features that don't exist.**

---

## 2. Repository layout

| Path | Role | Notes |
|---|---|---|
| `chessMain.py` | pygame GUI, input, AI process management, evaluation bar | Has its **own** separate evaluation function for the eval bar |
| `chessEngine.py` | `GameState`, `Move`, `CastleRights`: rules, move generation, make/undo | ~600 lines |
| `SmartMoveFinder.py` | Search (minimax + alpha-beta), evaluation, caches, move ordering | ~800 lines; mixes search and evaluation |
| `benchmark.py` | Fixed-depth search benchmark on 4 positions | Added in `27ae332` |
| `tests/test_perft.py` | Perft + make/undo state-restoration checks | Script with its own runner |
| `tests/test_search.py` | 3 search/eval regression tests | Script with its own runner |
| `tests/test_attack_cache.py` | **Empty file (0 bytes)** | The external roadmap marks "attack-cache regression tests" as done, but the file has no tests |
| `images/` | Piece sprites used by the GUI | |
| `assets/` | Screenshots (`Black_Wins.png`, `baord01.png` [sic], …) | Not referenced anywhere, including the README |
| `__init__.py` (repo root) | Empty | Makes the repo root a package, which isn't needed |
| `requirements.txt` | `pygame==2.1.0` | The venv actually has 2.6.1, and the README says `>=2.5.0` |
| `AGENTS.md`, `CLAUDE.md` | Instructions for AI coding agents | |

Git note: the commit message of `ea7a5a1` says "improve move ordering with killer moves and history heuristic", but that commit only added `AGENTS.md`. Neither heuristic exists in the code. Git history shouldn't be rewritten, so this is only noted here.

---

## 3. Chess rules (`chessEngine.py`)

### 3.1 How it works
- The board is an 8×8 list of 2-character strings (`"wK"`, `"bp"`, `"--"` for empty). Row 0 is rank 8.
- Legal moves come from **generate pseudo-legal → make → "am I in check?" → undo**.
- `squareUnderAttack()` works by **generating every opponent move** and checking whether any of them lands on the square. It's correct but very expensive; see §5.
- Castling rights and en passant squares are restored on undo from history lists (`castleRightLog`, `enpassantPossibleLog`).
- `getValidMoves()` also sets `gs.checkmate` / `gs.stalemate` as a side effect, and the search depends on that.

### 3.2 Verified correct (perft)

| Position | Depths | Result |
|---|---|---|
| Start position | 1–4 | ✅ matches published counts (in test suite) |
| Kiwipete | 1–3 | ✅ matches (in test suite) |
| Custom rook-capture castling case | 1–3 | ✅ matches (in test suite) |
| CPW position 3 (`8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -`) | 1–4 | ✅ matches: 14 / 191 / 2 812 / 43 238. **Checked during this review; not yet in the test suite.** |
| CPW position 4 | 2 | ❌ 228 vs 264: exactly the 36 missing underpromotion moves |
| CPW position 5 | 1 | ❌ 41 vs 44: exactly the 3 missing underpromotions of `d7xc8` |

The test suite also checks, after every make/undo pair, that the full game state is restored exactly.

### 3.3 Rule gaps and bugs

| # | Issue | Evidence |
|---|---|---|
| R1 ✅ *fixed in Phase 3* | **No underpromotion.** Promotion always creates a queen (`makeMove`), and the GUI has no piece picker. | Perft positions 4 and 5 above |
| R2 ✅ *fixed in Phase 3* | **Rank 8 is printed as "0".** `Move.ranksToRows` maps `"0"`→row 0 instead of `"8"`, so e7–e8 prints as `e7e0`, a knight to f8 shows as `Nf0` in the move log, and the benchmark prints moves like `g0f6`. `tests/test_search.py` currently asserts on the buggy string `"e0e7"`. | Checked directly |
| R3 ✅ *fixed in Phase 7* | **No draw rules**: no threefold repetition, no fifty-move rule, no insufficient material. For example, K vs K never ends. | Code |
| R4 ✅ *fixed in Phase 2* | **No FEN support in the engine.** The same FEN loader is copied into `test_perft.py`, `test_search.py` and `benchmark.py`. | Code |
| R5 ✅ *fixed in Phase 3* | `getValidMoves()` **mutates game-over flags**, and `get_all_attacks()` in the search module calls it for the side *not* to move. That call can set `gs.stalemate = True` in a position where the side to move isn't stalemated. It happens to be harmless today only because `tactical_score()` runs last in the evaluation and recomputes the flags for the correct side. Reordering or removing evaluation terms would expose it. | Checked directly with `7k/5Q2/6K1/8/8/8/8/8 w` |
| R6 ✅ *fixed in Phase 3* | Checkmate/stalemate are decided *before* castling moves are added in `getValidMoves()`. This is harmless: castling is never the only legal move, because the king could always step onto the square it passes through. The ordering is fragile, though. | From reading the code |
| R7 ✅ *found and fixed in Phase 4* | **Castling through a square attacked only by a pawn was allowed.** Attacks were detected by generating the opponent's moves, and a pawn only generates a diagonal move onto an *occupied* square, so e.g. a black pawn on e2 did not "attack" the empty f1/d1 and White could still castle. | Reproduced for both colours; also found once in 20 000 random positions. Not visible in perft, because the standard positions never reach it |
| R8 ✅ *found and fixed after Phase 7* | **A repetition could be declared late.** The position key included the en-passant square after every two-square pawn move, even when no pawn could capture en passant. By the rules (FIDE 9.2.3) that position is the same as its later occurrences, so it was counted one time too few. | Reproduced in the game window with a scripted game; `tests/test_gui.py` and `tests/test_draws.py` now cover it |

---

## 4. Search (`SmartMoveFinder.py`)

### 4.1 How it works
- Plain **fixed-depth minimax with alpha-beta**, `MAX_DEPTH = 3` plies, with separate branches for White (maximising) and Black (minimising).
- **State lives in globals**: `nextMove`, `nodesExplored`, `eval_cache`. The best move is only recorded when `depth == MAX_DEPTH`.
- **Move ordering** (captures by victim/attacker value, promotions, checks, development, centre) only runs at the top two plies. Every candidate is played with make/undo just to test whether it gives check.
- A position with a single legal move returns immediately.
- **No** iterative deepening, time control, quiescence search, transposition table, killer or history heuristics, or repetition detection.

### 4.2 Search bugs

| # | Issue | Evidence |
|---|---|---|
| S1 ✅ *fixed in Phase 3* | **The engine can pick a slower mate over mate-in-1.** The root window is `[-CHECKMATE, +CHECKMATE]`, but mate scores are `CHECKMATE + depth_remaining`, which is ≥ 1000. A mate-in-2 scores exactly 1000, so the root takes an immediate beta cutoff and stops looking. If move ordering puts that move first, the real mate-in-1 is never examined. | Reproduced: in 12 random K+Q+R vs K positions with a mate-in-1, the engine chose a different move twice. Examples: `3k4/5R2/8/2K5/4Q3/8/8/8 w - -` (plays Qd5+ instead of Qa8#) and `8/8/1R2Q3/8/8/8/8/k1K5 w - -` (plays Qe5+ instead of Ra6#/Rb1#) |
| S2 ✅ *fixed in Phase 6* | **Horizon effect.** With no quiescence search, the last ply can "win" material that the next ply loses right back. The evaluation's `tactical_score` tries to patch this, but badly (see E1/E2). | From reading the code |
| S3 ✅ *fixed in Phase 5 (time-limited search)* | **Search time depends on position complexity** (5–64 s), so the GUI can freeze in the "thinking" state for over a minute. | Benchmark (§5) |

---

## 5. Performance

### 5.1 Baseline benchmark (`python benchmark.py`, depth 3)

| Position | Time | Nodes | Nodes/s | Chosen move |
|---|---|---|---|---|
| Starting position | 5.34 s | 1 018 | 190 | b1c3 |
| Italian Game | 17.65 s | 2 015 | 114 | g0f6 *(= g8f6, see R2)* |
| Middlegame | 32.77 s | 2 742 | 83 | e1c1 (O-O-O) |
| Kiwipete | 64.48 s | 3 989 | 61 | e2a6 |
| **Total** | **120.2 s** | **9 764** | **81** | |

Full perft suite: **~25 s** (`--fast` subset: ~1 s). Search tests: ~3 s.

### 5.2 Where the time goes (cProfile, one depth-3 search from the start position, 5.6 s)

| What | Calls | Share of time |
|---|---|---|
| Search nodes | 1 018 | — |
| `getValidMoves()` | 3 147 | 97 % (cumulative) |
| `inCheck()` → `squareUnderAttack()` | 75 216 | **~85 %** |
| Full pseudo-legal move generations | 78 363 | — |
| `Move` objects constructed | **1 898 843** | 34 % (self time) |
| `scoreBoard()` (evaluation) | 931 | 69 % (cumulative) |

**Root cause:** each "is this square attacked?" query builds every opponent move as a `Move` object, and it's asked for every candidate move. On top of that, the evaluation calls `getValidMoves()` about three times per leaf (twice for attack maps, once for `tactical_score`). Around 1 000 search nodes end up constructing nearly 2 million `Move` objects.

---

## 6. Evaluation (`scoreBoard`)

Score in pawns from White's point of view (Q = 10, R = 5, B/N = 3, P = 1). Mate = ±(1000 + depth remaining).

The terms are: material + piece-square tables, bishop pair, rooks on open files, opening principles, mobility, king safety, a bonus for giving check, pawn structure (doubled, isolated, passed), and a "tactical" term.

| # | Issue | Evidence |
|---|---|---|
| E1 ✅ *removed in Phase 6* | **Attack maps are built from *legal moves*, not attacks.** They include pawn *pushes*, leave out pawn diagonal control of empty squares, and leave out squares holding your own pieces. **As a result, no piece is ever counted as defended**, so every attacked piece is penalised as "hanging". | Checked directly: in `3rk3/8/8/8/3N4/2P5/8/4K3 w`, the knight on d4 (defended by c3) counts as undefended, and the push square c4 counts as "attacked" |
| E2 ✅ *removed in Phase 6* | `tactical_score` adds 0.25 × victim value for **every** capture available to the side to move. That counts the same target several times and favours whichever side is on move. | From reading the code |
| E3 ✅ *fixed in Phase 6* | The king piece-square table exists but is **never used**: the evaluation skips kings. | From reading the code |
| E4 ✅ *removed in Phase 6* | `count_developed_pieces` counts a **captured** knight or bishop as "developed", which rewards losing it. | Checked directly |
| E5 ✅ *removed in Phase 6* | Opening bonuses are **very large** relative to material: up to 2.5 + 0.8 pawns for an early queen move, and 1.5 + 0.6 for castling. They can outweigh real positional factors. | From reading the code |
| E6 ✅ *fixed in Phase 6* | `eval_cache` key = board + side to move only (no castling or en passant). It evicts with an O(n) scan once it holds 1 000 entries. In the GUI, each AI move runs in a fresh process, so the cache always starts empty. | From reading the code |
| E7 ✅ *fixed in Phase 6* | **The GUI's eval bar uses a different evaluator** (`chessMain.evaluatePosition`, Q = 9, different tables), so the bar doesn't show what the engine thinks. | From reading the code |
| E8 ✅ *replaced in Phase 6* | The piece-square tables for N, B, R, Q and K **appear to be copied from the Sunfish engine**, which is GPL-3.0 licensed; the pawn table is modified. There's no attribution anywhere in the repo. This matters for the choice of license (see decisions in [02](02-proposed-changes.md#5-decisions-needed-from-you)). | Values match Sunfish's published tables row for row, compared from memory; confirm against the Sunfish source |

---

## 7. GUI (`chessMain.py`)

**Works:** click-to-move, legal-move highlighting, move animation, move log panel, eval bar, checkmate/stalemate text, Z = undo, R = reset. The AI runs in a separate process, so the window stays responsive.

| # | Issue | Evidence |
|---|---|---|
| G1 ✅ *fixed in Phase 3* | **Undo against the AI doesn't really work.** Pressing Z undoes only the AI's move. The `moveUndone` guard is reset in the same frame, so the AI immediately moves again. To get back to your own move you have to press Z a second time *while the AI is thinking*. | From reading the code |
| G2 ✅ *fixed in Phase 8 (engine since Phase 3)* | Promotion always produces a queen, with no picker (see R1). | Code |
| G3 ✅ *fixed in Phase 8 (rank 8 and promotion suffix in Phase 3)* | Move log shows rank 8 as `0` (R2), has no `+`/`#`, no promotion suffix and no disambiguation. It doesn't scroll, so long games run off the panel. | Code |
| G4 ✅ *fixed in Phase 3* | End-of-game text is shifted 40 px right of centre (`EVAL_BAR_WIDTH` is added twice in `drawEndGameText`). | From reading the code |
| G5 ✅ *fixed in Phase 6* | Eval bar uses a separate evaluator (E7). | Code |
| G6 ✅ *fixed in Phase 8* | No highlighting of the last move or of a king in check, and no board coordinates. | Code |
| G7 ✅ *fixed in Phase 8* | You can't choose your side (always White), a difficulty, or a time limit, and there's no board flip. | Code |
| G8 ✅ *fixed in Phase 7* | No draw detection (R3), so the game never ends in dead-drawn positions. | Code |
| G9 ✅ *reproduced and fixed in Phase 8* | Closing the window while the AI is thinking keeps the app alive until the search finishes. Not reproduced in Phase 2 (exit within 0.3 s), but with Phase 5's time-limited search it was real: the program lived on (window frozen) for the rest of the search, 1.95 s in a measured case and up to the 5 s "hard" budget, because the non-daemon child was joined at exit. | Checked 2026-09-28 and 2026-09-29 (macOS, Python 3.12) |
| G10 ✅ *fixed in Phase 8* | Every AI move re-imports `chessMain` in the child process, which prints the pygame banner and "AI thinking…" / "AI done thinking" to the console. Since Phase 2 (`python -m chess_ai`) the child no longer imports the GUI (checked with a per-process import probe); the prints and the banner were removed in Phase 8. | Seen during runs / code |

---

## 8. Code quality and naming

| Area | Current state |
|---|---|
| Module names | Three styles: `chessMain.py` (camelCase), `chessEngine.py` (camelCase), `SmartMoveFinder.py` (PascalCase), `benchmark.py` (lowercase) |
| Functions/methods | camelCase (`makeMove`, `getValidMoves`, `scoreBoard`, `findBestMoveMinMax`) mixed with snake_case (`get_move_priority`, `opening_phase_score`, `get_all_attacks`) |
| Constants | `CHECKMATE`, `MAX_DEPTH` in UPPER_CASE, but `pieceScore`, `knightScores`, … in camelCase |
| Typos baked into names | `getRockMove` / `rockScores` (rook), `updateCastlRights`, `assets/baord01.png` |
| Imports | `from chessEngine import *`, `from SmartMoveFinder import *`, a `sys.path.append(".")` hack, unused imports (`time` in both modules) |
| Docstrings | Mostly bare string literals placed *before* methods, so they aren't real docstrings |
| Duplication | FEN loader ×3; two separate evaluation functions and piece-value tables |
| Globals | Search state (`nextMove`, `nodesExplored`, `eval_cache`) is module-global |
| Structure | `SmartMoveFinder.py` mixes search, evaluation, caching and move ordering in one ~800-line file |

---

## 9. Tests, tooling, CI

- Tests are standalone scripts (`python tests/test_perft.py [--fast]`, `python tests/test_search.py`). There's **no pytest**, so individual tests can't be selected easily, and there's no shared fixture code.
- **No CI**, no linter or formatter, and no `pyproject.toml`.
- **Not covered by tests:** evaluation, notation, promotion, draw rules, the GUI, the benchmark, and attack-cache behaviour (the file exists but is empty).

---

## 10. Documentation and setup

README problems:

| Claim / instruction | Reality |
|---|---|
| `python ChessMain.py`; files listed as `ChessMain.py`, `ChessEngine.py` | Files are `chessMain.py`, `chessEngine.py`. It works on macOS (case-insensitive file system) but **fails on Linux** |
| "requirements.txt should contain `pygame>=2.5.0`" | It contains `pygame==2.1.0` |
| "Transposition table caching" | There's no transposition table, only a small evaluation cache |
| "AI opponent with configurable difficulty" | Only by editing `MAX_DEPTH` in the source |
| "Z: undo … works for both player and AI" | See G1 |
| "Runs on Windows, macOS, and Linux" | Only macOS has actually been exercised |
| No mention of tests, the benchmark, or a license file | — |

Environment: the venv is Python **3.9.6**, which reached end of life in October 2025. `pygame==2.1.0` predates pygame's pre-built wheels for Python 3.11+, so on a current Python, `pip install -r requirements.txt` may try to build pygame from source.
