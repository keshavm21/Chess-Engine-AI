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
