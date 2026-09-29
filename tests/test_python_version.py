"""The package refuses unsupported Python versions with a clear message."""

import importlib
import sys

import pytest

import chess_ai


def test_unsupported_python_version_gives_a_clear_message(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    with pytest.raises(SystemExit, match=r"needs Python 3\.10 or newer.*3\.9\.6"):
        importlib.reload(chess_ai)


def test_an_old_virtual_environment_is_told_to_be_recreated(monkeypatch):
    """The README's first attempt on macOS: `python3` is the built-in 3.9, so
    the new virtual environment itself is too old."""
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    monkeypatch.setattr(sys, "prefix", "/project/venv")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    with pytest.raises(SystemExit, match=r"Recreate it with Python 3\.10-3\.13"):
        importlib.reload(chess_ai)


def test_outside_a_virtual_environment_the_project_one_is_suggested(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    with pytest.raises(SystemExit, match=r"source venv/bin/activate"):
        importlib.reload(chess_ai)


def test_supported_python_version_imports_normally():
    importlib.reload(chess_ai)  # no SystemExit on the Python running the tests
