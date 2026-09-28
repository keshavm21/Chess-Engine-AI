"""Smoke tests for the benchmark tool (kept small so they run in seconds)."""

import json

from chess_ai import benchmark
from chess_ai.engine import GameState

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


def test_perft_counts():
    assert benchmark.perft(GameState.from_fen(START), 1) == 20
    assert benchmark.perft(GameState.from_fen(START), 3) == 8902


def test_main_writes_json_and_reports_success(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "PERFT_POSITIONS", [("start", START, 2, 400)])
    # A position with a single legal move, so the search returns immediately.
    monkeypatch.setattr(
        benchmark, "SEARCH_POSITIONS", [("one move", "7k/8/6K1/8/8/8/8/6R1 b - -")]
    )
    out = tmp_path / "bench.json"

    assert benchmark.main(["--json", str(out)]) == 0

    report = json.loads(out.read_text())
    assert report["perft"][0]["nodes"] == 400 and report["perft"][0]["correct"]
    assert report["search"][0]["move"] == "h8g8"  # Kg8 is the only legal move
    assert report["timed_search"][0]["move"] == "h8g8"


def test_search_statistics_are_reported(monkeypatch):
    monkeypatch.setattr(benchmark, "SEARCH_POSITIONS", [("start", START)])
    [row] = benchmark.run_search(max_depth=2)
    assert row["depth"] == 2 and row["nodes"] > 0 and row["cutoffs"] > 0
    [row] = benchmark.run_search(time_limit=0.2)
    assert row["depth"] >= 1 and row["time_s"] < 0.2 + 0.35


def test_main_fails_on_a_wrong_perft_count(monkeypatch):
    monkeypatch.setattr(benchmark, "PERFT_POSITIONS", [("start", START, 1, 21)])
    assert benchmark.main(["--perft-only"]) == 1
