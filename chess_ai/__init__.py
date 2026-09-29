"""Chess-Engine-AI: a chess engine with an alpha-beta AI and a pygame GUI."""

import sys

# Fail early with a clear message instead of an obscure error deep in the code
# (e.g. a TypeError from `int | None` annotations on Python 3.9).
if sys.version_info < (3, 10):
    if sys.prefix != sys.base_prefix:  # a virtual environment made with old Python
        advice = (
            "This virtual environment was made with that Python. Recreate it "
            "with Python 3.10-3.13, for example:\n"
            "    deactivate && rm -rf venv && python3.12 -m venv venv\n"
            "    source venv/bin/activate && pip install -r requirements.txt\n"
            "(On macOS, `python3` may be the built-in 3.9; install a newer one "
            "with `brew install python@3.12` or from python.org.)"
        )
    else:
        advice = (
            "Use the project's virtual environment: run `deactivate` if needed, "
            "then `source venv/bin/activate` (or run `./venv/bin/python -m chess_ai`)."
        )
    raise SystemExit(
        "Chess-Engine-AI needs Python 3.10 or newer, but this is Python "
        f"{'.'.join(map(str, sys.version_info[:3]))} ({sys.executable}).\n" + advice
    )

__version__ = "1.0.0"
