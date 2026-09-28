# Benchmarks

A log of search-performance measurements, one entry per meaningful change. Numbers from different machines or Python versions can't be compared directly, so every entry states its environment.

The search is deterministic, so at a fixed depth the **node counts and chosen moves** should only change when search or evaluation behaviour changes on purpose. Time and nodes/second vary a little between runs.

---

## Baseline: before the improvement plan

| | |
|---|---|
| Date | 2026-09-28 |
| Commit | `ea7a5a1` |
| Command | `python benchmark.py` (now `python -m chess_ai.benchmark`) |
| Machine | Apple M1, macOS |
| Python | 3.9.6 |
| Search | Fixed depth 3 (`MAX_DEPTH`), minimax + alpha-beta, no quiescence search |

| Position | Time | Nodes | Nodes/s | Chosen move |
|---|---|---|---|---|
| Starting position | 5.34 s | 1 018 | 190 | b1c3 |
| Italian Game (after 1.e4 e5 2.Nf3 Nc6 3.Bc4) | 17.65 s | 2 015 | 114 | g8f6 *(printed as `g0f6`: rank-8 notation bug R2)* |
| Middlegame (rich tactical) | 32.77 s | 2 742 | 83 | e1c1 (O-O-O) |
| Kiwipete (stress position) | 64.48 s | 3 989 | 61 | e2a6 |
| **Total** | **120.24 s** | **9 764** | **81** | |

The profile behind these numbers is in [improvement-plan/01-current-state.md §5.2](improvement-plan/01-current-state.md#52-where-the-time-goes-cprofile-one-depth-3-search-from-the-start-position-56-s).

### Test suite timings (same machine)

| Command | Result | Time |
|---|---|---|
| `pytest` | 28 passed, 10 xfailed | ~34 s |
| `pytest -m "not slow"` | 25 passed, 10 xfailed, 3 deselected | ~6 s |

---

## Phase 2: Python 3.12 and package refactor

| | |
|---|---|
| Date | 2026-09-28 |
| Command | `python benchmark.py` before, `python -m chess_ai.benchmark` after |
| Machine | Apple M1, macOS |
| Python | **3.12.14** (the venv was upgraded from 3.9.6) |
| Search | Unchanged: fixed depth 3 |

Phase 2 is a pure refactor, so the node counts and chosen moves must be identical, and they are.

| Position | Nodes | Move | 3.9 baseline | 3.12 before refactor | 3.12 after refactor |
|---|---|---|---|---|---|
| Starting position | 1 018 | b1c3 | 5.34 s | 1.83 s | 1.84 s |
| Italian Game | 2 015 | g8f6 | 17.65 s | 6.93 s | 6.53 s |
| Middlegame | 2 742 | e1c1 | 32.77 s | 11.89 s | 11.83 s |
| Kiwipete | 3 989 | e2a6 | 64.48 s | 23.44 s | 22.00 s |
| **Total** | **9 764** | | **120.24 s** | **44.09 s** | **42.19 s** |

The Python upgrade alone made the search about **2.7× faster**. The refactor itself is neutral; the differences are within run-to-run noise. Test suite on 3.12: `pytest` ~12 s, `pytest -m "not slow"` ~2 s.

---

## Phase 3: correctness fixes

| | |
|---|---|
| Date | 2026-09-28 |
| Command | `python -m chess_ai.benchmark` (run after each fix) |
| Machine / Python | Apple M1, macOS / 3.12.14 |

Node counts and chosen moves are **unchanged** after every Phase 3 fix: 1 018 / 2 015 / 2 742 / 3 989 nodes, b1c3 / g8f6 / e1c1 / e2a6. The mate-window fix and underpromotion only matter when a mate or a promotion is within the search horizon, which is not the case in these positions. Timings stayed within noise (41–44 s total). The Italian Game move now prints correctly as `g8f6`.

Test suite: `pytest` ~32 s (the new promotion-heavy perft case, position 4 at depth 4, takes ~15 s), `pytest -m "not slow"` ~6 s.

---

## Phase 4: performance (same results, much faster)

| | |
|---|---|
| Date | 2026-09-28 |
| Command | `python -m chess_ai.benchmark` (extended in this phase with perft timing and `--json`) |
| Machine / Python | Apple M1, macOS / 3.12.14 |

Every row was measured with the same (extended) benchmark. Node counts and chosen moves are identical in every row: perft 197 281 / 97 862, search 1 018 / 2 015 / 2 742 / 3 989 nodes with b1c3 / g8f6 / e1c1 / e2a6.

| Step | Perft start d4 | Perft Kiwipete d3 | Search, 4 positions | Search nodes/s |
|---|---|---|---|---|
| Baseline (end of Phase 3) | 5.53 s | 3.38 s | 45.00 s | 216 |
| Direct attack detection (scan from the square) | 0.83 s | 0.41 s | 6.14 s | 1 589 |
| Legality check without a full make/undo | 0.66 s | 0.33 s | 5.48 s | 1 780 |
| Evaluation shares one move generation | 0.65 s | 0.32 s | 4.42 s | 2 208 |
| Precomputed attack tables | **0.50 s** | **0.22 s** | **3.58 s** | **2 727** |
| **Speed-up** | **11.1×** | **15.4×** | **12.6×** | |

Per search position after Phase 4: 0.21 s / 0.61 s / 1.01 s / 1.75 s (was 1.87 s / 6.45 s / 12.38 s / 24.31 s).

Since the original baseline (Python 3.9, 120.24 s for the four searches), the search is about **34× faster**: roughly 2.7× from the Python upgrade and 12.6× from Phase 4.

Test suite: `pytest` ~4 s (was ~32 s), `pytest -m "not slow"` ~2 s.

Where the time goes now (cProfile, middlegame search): mostly the evaluation, which generates legal moves for both sides to build its attack maps. Making that cheaper would change what the evaluation computes, so it belongs to the evaluation rewrite in Phase 6.
