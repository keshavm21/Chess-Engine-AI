"""Chess-Engine-AI: a chess engine with an alpha-beta AI and a pygame GUI."""

import sys

# Fail early with a clear message instead of an obscure error deep in the code
# (e.g. a TypeError from `int | None` annotations on Python 3.9).
if sys.version_info < (3, 10):
    raise SystemExit(
        "Chess-Engine-AI needs Python 3.10 or newer, but this is Python "
        f"{'.'.join(map(str, sys.version_info[:3]))} ({sys.executable}).\n"
        "Use the project's virtual environment: run `deactivate` if needed, "
        "then `source venv/bin/activate` (or run `./venv/bin/python -m chess_ai`)."
    )

__version__ = "1.0.0"
