"""The package refuses unsupported Python versions with a clear message."""

import importlib
import sys

import pytest

import chess_ai


def test_unsupported_python_version_gives_a_clear_message(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    with pytest.raises(SystemExit, match=r"needs Python 3\.10 or newer.*3\.9\.6"):
        importlib.reload(chess_ai)


def test_supported_python_version_imports_normally():
    importlib.reload(chess_ai)  # no SystemExit on the Python running the tests
