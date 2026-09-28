# Improvement Plan

The plan for turning Chess-Engine-AI into a clean, well-tested portfolio project with a decent engine.

| Document | What it covers |
|---|---|
| [01-current-state.md](01-current-state.md) | Where the project stands today: verified bugs, performance baseline, code quality, docs |
| [02-proposed-changes.md](02-proposed-changes.md) | What we want to change and why: goals, review of requested changes, change catalogue, open decisions |
| [03-implementation-plan.md](03-implementation-plan.md) | How and in what order: phases, verification gates, planned commits |

## Working agreement

- Development happens on the `improve-chess-engine` branch. Each completed phase is merged into `main`.
- Claude doesn't commit. It suggests commit messages, and the maintainer reviews and commits.
- Every phase ends with the game fully working and the phase gate in 03 passed.

## Status

| Phase | Title | Status |
|---|---|---|
| 0 | Planning | ✅ Done (pending review) |
| 1 | Safety net: tests, tooling, CI | ✅ Committed on `improve-chess-engine` (not yet merged into `main`) |
| 2 | Structure and naming cleanup | ✅ Committed on `improve-chess-engine` (not yet merged into `main`) |
| 3 | Correctness fixes | 🔶 Implemented, awaiting review and merge |
| 4 | Performance | ⬜ Not started |
| 5 | Search framework (iterative deepening, time limit) | ⬜ Not started |
| 6 | Quiescence search and new evaluation | ⬜ Not started |
| 7 | Hashing, draw rules, transposition table | ⬜ Not started |
| 8 | GUI/UX and runtime robustness | ⬜ Not started |
| 9 | Release polish (v1.0) | ⬜ Not started |

Update this table whenever a phase is merged into `main`.
