# Benchmarks

A log of search-performance measurements, one entry per meaningful change. Numbers from different machines or Python versions can't be compared directly, so every entry states its environment.

The search is deterministic, so at a fixed depth the **node counts and chosen moves** should only change when search or evaluation behaviour changes on purpose. Time and nodes/second vary a little between runs.

---

## Baseline: before the improvement plan

| | |
|---|---|
| Date | 2026-09-28 |
| Commit | `ea7a5a1` |
| Command | `python benchmark.py` |
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
