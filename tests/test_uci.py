"""Tests for the UCI mode (chess_ai.uci)."""

import io
import pathlib
import queue
import subprocess
import sys
import threading
import time

import pytest

from chess_ai import search, uci
from chess_ai.engine import GameState
from chess_ai.evaluation import CHECKMATE

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MATE_IN_ONE = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"  # Ra8#
STALEMATE = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"


class TestPosition:
    def test_startpos(self):
        assert uci.parse_position(["startpos"]).to_fen() == START

    def test_startpos_with_moves(self):
        gs = uci.parse_position("startpos moves e2e4 e7e5 g1f3".split())
        assert gs.to_fen() == (
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
        )

    def test_fen_with_castling_and_a_promotion(self):
        args = "fen r3k2r/8/8/8/8/8/1p6/R3K2R w KQkq - 0 1 moves e1g1 e8c8 a1a2 b2b1q"
        gs = uci.parse_position(args.split())
        assert gs.to_fen() == "2kr3r/8/8/8/8/8/R7/1q3RK1 w - - 0 3"

    @pytest.mark.parametrize(
        "args",
        [
            "startpos moves e2e5",  # illegal move
            "startpos moves e7e5",  # not White's pawn
            "fen 8/8/8/8/8/8/8/8 w - - 0 1",  # no kings
            "startfen",
            "",
        ],
    )
    def test_bad_positions_are_refused(self, args):
        with pytest.raises(ValueError):
            uci.parse_position(args.split())


class TestSearchLimits:
    """(max_depth, time limit, infinite) for "go" commands."""

    DEEP = search.MAX_SEARCH_DEPTH

    @pytest.mark.parametrize(
        ("args", "white_to_move", "expected"),
        [
            ("depth 4", True, (4, None, False)),
            ("movetime 1000", True, (DEEP, 0.95, False)),
            ("depth 3 movetime 500", True, (3, 0.45, False)),
            ("infinite", True, (DEEP, None, True)),
            # An even share of the clock (30 moves to go), minus the overhead.
            ("wtime 60000 btime 30000", True, (DEEP, 1.95, False)),
            ("wtime 60000 btime 30000", False, (DEEP, 0.95, False)),
            ("wtime 60000 btime 60000 winc 2000 binc 1000", True, (DEEP, 3.45, False)),
            ("wtime 60000 btime 60000 movestogo 10", False, (DEEP, 5.95, False)),
            # Never more than half the clock, even for the last move.
            ("wtime 10000 btime 10000 movestogo 1", True, (DEEP, 4.95, False)),
            # Almost no time left: still a (very short) search.
            ("wtime 30 btime 30", True, (DEEP, 0.01, False)),
        ],
    )
    def test_limits(self, args, white_to_move, expected):
        max_depth, time_limit, infinite = uci.search_limits(args.split(), white_to_move)
        assert (max_depth, infinite) == (expected[0], expected[2])
        assert time_limit == pytest.approx(expected[1])

    def test_odd_numbers_do_not_crash_the_engine(self):
        assert uci.search_limits("movetime 250.0".split(), True)[1] == (
            pytest.approx(0.2)
        )
        default = search.DIFFICULTIES[search.DEFAULT_DIFFICULTY].time_limit
        assert uci.search_limits("wtime abc".split(), True) == (
            self.DEEP,
            default,
            False,
        )

    def test_without_limits_the_default_difficulty_is_used(self):
        default = search.DIFFICULTIES[search.DEFAULT_DIFFICULTY].time_limit
        assert uci.search_limits([], True) == (self.DEEP, default, False)


@pytest.mark.parametrize(
    ("score", "white_to_move", "text"),
    [
        (35, True, "cp 35"),
        (35, False, "cp -35"),  # scores are from the side to move's view
        (CHECKMATE - 1, True, "mate 1"),
        (CHECKMATE - 3, True, "mate 2"),
        (-(CHECKMATE - 2), True, "mate -1"),  # White is mated after 2 plies
        (CHECKMATE - 2, False, "mate -1"),  # Black to move is mated
        (-(CHECKMATE - 1), False, "mate 1"),  # Black mates at once
    ],
)
def test_uci_score(score, white_to_move, text):
    assert uci.uci_score(score, white_to_move) == text


class Session:
    """A UCIEngine whose answers are collected in a list of lines."""

    def __init__(self):
        self.output = io.StringIO()
        self.engine = uci.UCIEngine(self.output)

    def send(self, *commands):
        for command in commands:
            assert self.engine.handle(command)

    def lines(self):
        return self.output.getvalue().splitlines()

    def bestmove(self):
        self.engine.wait()
        answers = [line for line in self.lines() if line.startswith("bestmove")]
        assert len(answers) == 1, self.lines()
        return answers[0].split()[1]


@pytest.fixture
def session():
    s = Session()
    yield s
    s.engine.stop()


def test_handshake(session):
    session.send("uci", "isready")
    assert session.lines() == [
        f"id name Chess-Engine-AI {uci.__version__}",
        "id author Keshav Mishra",
        "uciok",
        "readyok",
    ]


def test_go_answers_with_a_legal_move_and_search_information(session):
    session.send("ucinewgame", "position startpos moves e2e4", "go depth 2")
    move = session.bestmove()
    black_moves = uci.parse_position("startpos moves e2e4".split()).get_legal_moves()
    assert move in {m.coordinate_notation() for m in black_moves}
    info = session.lines()[-2].split()
    assert info[:3] == ["info", "depth", "2"]
    assert info[info.index("score") + 1] == "cp"
    assert info[-2:] == ["pv", move]


def test_a_mate_in_one_is_found_and_reported(session):
    session.send(f"position fen {MATE_IN_ONE}", "go depth 3")
    assert session.bestmove() == "a1a8"
    assert "score mate 1" in session.lines()[-2]


def test_without_legal_moves_the_answer_is_a_null_move(session):
    session.send(f"position fen {STALEMATE}", "go depth 2")
    assert session.bestmove() == "0000"


def test_go_infinite_answers_only_after_stop(session):
    session.send("position startpos", "go infinite")
    time.sleep(0.3)
    session.send("isready")  # answered while the engine thinks
    assert session.lines() == ["readyok"]
    started = time.perf_counter()
    session.send("stop")
    assert time.perf_counter() - started < 1.0
    assert session.bestmove() in {
        m.coordinate_notation() for m in GameState().get_legal_moves()
    }


def test_go_infinite_waits_for_stop_even_after_finding_a_mate(session):
    session.send(f"position fen {MATE_IN_ONE}", "go infinite")
    time.sleep(0.3)  # the search itself stops at the mate ...
    assert not any(line.startswith("bestmove") for line in session.lines())
    session.send("stop")  # ... but the answer comes only now
    assert session.bestmove() == "a1a8"


def test_stop_without_a_search_does_nothing(session):
    session.send("stop")
    assert session.lines() == []


def test_a_bad_position_is_reported_and_ignored(session):
    session.send("position startpos moves e2e4", "position startpos moves e2e5")
    assert session.lines()[-1].startswith("info string illegal move 'e2e5'")
    assert session.engine.gs.to_fen().startswith("rnbqkbnr/pppppppp/8/8/4P3/")


def test_a_malformed_go_still_answers_with_a_move(session):
    session.send("position startpos", "go depth x movetime 200")
    assert session.bestmove() in {
        m.coordinate_notation() for m in GameState().get_legal_moves()
    }


def test_unknown_commands_are_ignored(session):
    session.send("debug on", "setoption name Hash value 16", "xyzzy")
    assert session.lines() == []


def test_quit_stops_a_running_search(session):
    session.send("position startpos", "go infinite")
    assert session.engine.handle("quit") is False
    assert session.lines()[-1].startswith("bestmove")


def test_main_reads_commands_until_quit():
    commands = io.StringIO(
        "uci\nisready\nposition startpos\ngo depth 1\nquit\ngo depth 1\n"
    )
    output = io.StringIO()
    assert uci.main(commands, output) == 0
    lines = output.getvalue().splitlines()
    assert "uciok" in lines and "readyok" in lines
    assert sum(line.startswith("bestmove") for line in lines) == 1  # none after quit


def test_at_the_end_of_the_input_a_running_search_may_finish():
    output = io.StringIO()
    uci.main(io.StringIO("position startpos\ngo depth 2\n"), output)
    assert output.getvalue().splitlines()[0].startswith("info depth 2 ")


def test_the_uci_process_talks_over_pipes():
    """The real program, as a GUI runs it: answers must not be stuck in an
    output buffer, and "quit" must end the process."""
    repository = pathlib.Path(__file__).resolve().parent.parent
    process = subprocess.Popen(
        [sys.executable, "-m", "chess_ai.uci"],
        cwd=repository,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    lines = queue.Queue()
    threading.Thread(
        target=lambda: [lines.put(line.strip()) for line in process.stdout],
        daemon=True,
    ).start()

    def tell(command):
        process.stdin.write(command + "\n")
        process.stdin.flush()

    def ask(command, answer):
        tell(command)
        while True:
            line = lines.get(timeout=20)
            if line.startswith(answer):
                return line

    try:
        ask("uci", "uciok")
        ask("isready", "readyok")
        tell("position startpos moves e2e4 e7e5")  # no answer expected
        move = ask("go movetime 300", "bestmove").split()[1]
        gs = uci.parse_position("startpos moves e2e4 e7e5".split())
        assert move in {m.coordinate_notation() for m in gs.get_legal_moves()}
        tell("quit")
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
