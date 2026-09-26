# Chess Engine AI — Agent Instructions

## Project

This is an existing Python chess engine.

The goal is to incrementally improve its correctness, playing strength,
performance, architecture, testing, and repository quality.

Do not rewrite the project from scratch.

The development roadmap is stored outside the repository as:
`../chess_engine_repository_improvement_roadmap.txt`

Treat that roadmap as the high-level development plan, but always inspect
the actual repository before deciding what remains to be done.


## General Development Rules

- Prefer incremental changes over rewrites.
- Correctness comes before performance.
- Inspect the existing implementation before modifying it.
- Understand why existing code works before replacing it.
- Do not introduce new dependencies unless there is a clear technical reason.
- Do not implement future roadmap tasks unless explicitly requested.
- Work on one meaningful task at a time.
- Preserve existing working behavior unless the current task requires changing it.
- Do not remove functionality merely to simplify the code.


## Chess Correctness

- Treat chess-rule correctness as a high priority.
- Do not weaken or remove existing tests.
- When fixing a chess-rule bug, add or update a regression test when appropriate.
- Preserve correct make/undo behavior.
- Be especially careful with:
  - castling rights
  - en passant
  - promotion
  - check/checkmate
  - pins
  - attack maps
  - board state restoration
  - move generation


## Search

The search implementation currently uses Minimax with Alpha-Beta pruning.

When modifying search:

- Preserve correct Minimax semantics.
- Preserve correct Alpha-Beta bounds.
- Do not trade correctness for a small performance improvement.
- Benchmark meaningful search changes.
- Be careful with transposition/caching logic.
- Ensure cached data is valid for the complete relevant position state.
- Do not introduce speculative search optimizations without testing them.


## Evaluation

Keep evaluation logic understandable and maintainable.

Do not blindly add large numbers of heuristics.

When changing evaluation:

1. inspect the existing evaluation,
2. make the smallest justified change,
3. run tests,
4. benchmark where appropriate,
5. play-test the engine.


## Architecture

Maintain the separation of responsibilities:

- `chessMain.py`
  - GUI
  - rendering
  - user interaction
  - game interaction

- `chessEngine.py`
  - board state
  - chess rules
  - move generation
  - make/undo
  - game state

- `SmartMoveFinder.py`
  - search
  - evaluation
  - search-related caching/data structures

Do not mix GUI responsibilities into the chess engine or search code
without a strong reason.


## Testing

After every meaningful behavior change:

- run the relevant tests,
- inspect failures rather than bypassing them,
- add regression tests for newly discovered bugs.

Never:

- delete a failing test just to make the suite pass,
- weaken a test without a technical justification,
- skip verification because the change appears simple.

Before considering a substantial task complete, run the full test suite.


## Performance

When optimizing:

- establish a baseline first,
- measure before and after,
- report meaningful performance changes,
- do not assume that fewer lines of code means faster code.

For search changes, consider measuring:

- search depth
- nodes searched
- runtime
- nodes/second
- Alpha-Beta cutoffs
- transposition-table hits where applicable


## File Naming

Do not rename files unless the task explicitly calls for naming cleanup.

The project currently contains names such as:

- `chessMain.py`
- `chessEngine.py`
- `SmartMoveFinder.py`

A later cleanup may standardize these to Python naming conventions.

When renaming files:

- update imports,
- update tests,
- update documentation,
- verify Git recognizes the changes correctly,
- run the full test suite.


## Dependencies

Do not add a dependency unless it is actually needed.

When changing dependencies:

- update `requirements.txt`,
- verify installation,
- verify the application runs,
- verify tests still pass.


## README

Do not make major README changes during implementation.

The README should be finalized after the implementation is stable.

Never document planned functionality as if it already exists.

All README commands and filenames must match the actual repository.


## Git

Do not commit changes unless explicitly asked.

Do not push changes unless explicitly asked.

Do not:

- rewrite Git history,
- force-push,
- reset away user changes,
- delete branches,
- discard uncommitted work

unless explicitly instructed.

Before making changes, inspect the working tree and avoid overwriting
unrelated user modifications.


## Workflow

For a new task:

1. Inspect the relevant code.
2. Inspect relevant tests.
3. Determine the current behavior.
4. Explain the proposed approach.
5. Make the smallest reasonable implementation.
6. Run relevant tests.
7. Run broader tests when appropriate.
8. Inspect the final diff.
9. Report what changed and what was verified.

Do not silently expand a task into unrelated roadmap items.


## Important

The roadmap is a plan, not permission to implement everything at once.

If multiple improvements are possible, identify the next appropriate task
and wait for approval before implementing additional unrelated changes.