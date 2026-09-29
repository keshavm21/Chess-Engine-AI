"""UCI mode: lets chess GUIs and tools run the engine.

Start it with ``python -m chess_ai.uci``. It speaks the Universal Chess
Interface on standard input and output, so GUIs such as Arena or Cute Chess
can use the engine. Supported commands: ``uci``, ``isready``, ``ucinewgame``,
``position`` (``startpos`` or ``fen``, then ``moves``), ``go`` (``wtime``,
``btime``, ``winc``, ``binc``, ``movestogo``, ``movetime``, ``depth`` or
``infinite``), ``stop`` and ``quit``. Other commands are ignored, as the
protocol asks.

The search runs in a background thread, so ``isready`` and ``stop`` are
answered while the engine thinks.
"""

import sys
import threading
import traceback

from chess_ai import __version__, search
from chess_ai.engine import GameState
from chess_ai.evaluation import CHECKMATE

ENGINE_NAME = f"Chess-Engine-AI {__version__}"
ENGINE_AUTHOR = "Keshav Mishra"
# Seconds kept back from each move's time for the GUI and the operating system.
MOVE_OVERHEAD = 0.05
# Without "movestogo", the clock is shared out as if this many moves were left.
MOVES_TO_GO = 30
_GO_VALUES = ("wtime", "btime", "winc", "binc", "movestogo", "movetime", "depth")


def find_move(gs, text):
    """The legal move written as `text` in UCI notation ("e2e4", "e7e8q")."""
    for move in gs.get_legal_moves():
        if move.coordinate_notation() == text:
            return move
    raise ValueError(f"illegal move {text!r} in {gs.to_fen()}")


def parse_position(args):
    """The GameState that the arguments of a "position" command describe:
    ``startpos`` or ``fen <FEN>``, optionally followed by ``moves <move> ...``.

    Raises ValueError for a malformed command or FEN, or an illegal move.
    """
    split = args.index("moves") if "moves" in args else len(args)
    setup, moves = args[:split], args[split + 1 :]
    if setup == ["startpos"]:
        gs = GameState()
    elif len(setup) > 1 and setup[0] == "fen":
        gs = GameState.from_fen(" ".join(setup[1:]))
    else:
        raise ValueError(f"cannot read the position {' '.join(args)!r}")
    for text in moves:
        gs.make_move(find_move(gs, text))
    return gs


def search_limits(args, white_to_move):
    """(max_depth, time limit in seconds or None, infinite) for the arguments
    of a "go" command. Without any limit the default difficulty's time is used.
    """
    values, tokens = {}, iter(args)
    for token in tokens:
        if token in _GO_VALUES:
            try:
                values[token] = int(float(next(tokens, "")))
            except ValueError:
                pass  # an unreadable number: that limit is ignored
    max_depth = values.get("depth", search.MAX_SEARCH_DEPTH)
    if "infinite" in args:
        return search.MAX_SEARCH_DEPTH, None, True
    if "movetime" in values:
        return max_depth, max(values["movetime"] / 1000 - MOVE_OVERHEAD, 0.01), False
    clock = values.get("wtime" if white_to_move else "btime")
    if clock is not None:
        increment = values.get("winc" if white_to_move else "binc", 0)
        moves_to_go = max(values.get("movestogo", MOVES_TO_GO), 1)
        # An even share of the clock plus most of the increment, but never
        # more than half of the time that is left.
        share = min(clock / moves_to_go + 0.75 * increment, clock / 2)
        return max_depth, max(share / 1000 - MOVE_OVERHEAD, 0.01), False
    if "depth" in values:
        return max_depth, None, False
    default = search.DIFFICULTIES[search.DEFAULT_DIFFICULTY]
    return max_depth, default.time_limit, False


def uci_score(score, white_to_move):
    """A search score (centipawns, White's point of view) as UCI wants it,
    from the side to move's point of view: "cp 35", or "mate 2" / "mate -1"
    when the side to move mates / is mated in that many moves."""
    own = score if white_to_move else -score
    if abs(own) >= search.MATE_THRESHOLD:
        moves = (CHECKMATE - abs(own) + 1) // 2  # plies to the mate, in moves
        return f"mate {moves if own > 0 else -moves}"
    return f"cp {own}"


def info_line(result, white_to_move):
    """The "info" line for a finished search."""
    parts = ["info", "depth", str(result.depth)]
    if result.score is not None:
        parts += ["score", uci_score(result.score, white_to_move)]
    parts += ["nodes", str(result.nodes), "nps", str(result.nodes_per_second)]
    parts += ["time", str(int(result.elapsed * 1000))]
    if result.move is not None:
        parts += ["pv", result.move.coordinate_notation()]
    return " ".join(parts)


class UCIEngine:
    """The engine's side of a UCI conversation: handle() carries out one
    command, and the answers are written to `output`."""

    def __init__(self, output=None):
        self.output = output if output is not None else sys.stdout
        self.gs = GameState()
        self._lock = threading.Lock()  # the search thread writes too
        self._thread = None  # the running search, if any
        self._stop = None  # its threading.Event
        self._infinite = False

    def send(self, line):
        with self._lock:
            self.output.write(line + "\n")
            self.output.flush()

    def handle(self, line):
        """Carry out one command line. Returns False after "quit"."""
        words = line.split()
        if not words:
            return True
        command, args = words[0], words[1:]
        if command == "uci":
            self.send(f"id name {ENGINE_NAME}")
            self.send(f"id author {ENGINE_AUTHOR}")
            self.send("uciok")
        elif command == "isready":
            self.send("readyok")
        elif command == "ucinewgame":
            self.stop()
            self.gs = GameState()
        elif command == "position":
            self.stop()
            try:
                self.gs = parse_position(args)
            except ValueError as error:
                self.send(f"info string {error}")
        elif command == "go":
            self.go(args)
        elif command == "stop":
            self.stop()
        elif command == "quit":
            self.stop()
            return False
        return True

    def go(self, args):
        """Search the current position in a background thread, which answers
        with "info" and "bestmove" lines."""
        self.stop()  # one search at a time
        max_depth, time_limit, infinite = search_limits(args, self.gs.white_to_move)
        gs, stop = self.gs, threading.Event()
        legal_moves = gs.get_legal_moves()

        def think():
            try:
                searcher = search.Searcher(max_depth, time_limit)
                result = searcher.search(gs, legal_moves, stop_event=stop)
                move = result.move
                if result.depth > 0:
                    self.send(info_line(result, gs.white_to_move))
            except Exception:  # never leave the GUI waiting for a move
                traceback.print_exc()
                move = legal_moves[0] if legal_moves else None
            if infinite:
                stop.wait()  # after "go infinite", answer only when stopped
            self.send(f"bestmove {move.coordinate_notation() if move else '0000'}")

        self._stop, self._infinite = stop, infinite
        self._thread = threading.Thread(target=think, daemon=True)
        self._thread.start()

    def stop(self):
        """End the running search early; return once it has sent "bestmove"."""
        if self._thread is not None:
            self._stop.set()
            self._thread.join()
            self._thread = None

    def wait(self):
        """Let the running search finish (an infinite one is stopped) and
        return once it has sent "bestmove"."""
        if self._infinite:
            self.stop()
        elif self._thread is not None:
            self._thread.join()
            self._thread = None


def main(input_stream=None, output=None):
    """Talk UCI on standard input and output until "quit" or the end of the
    input (at the end, a running search may finish first)."""
    engine = UCIEngine(output)
    input_stream = input_stream if input_stream is not None else sys.stdin
    while True:
        line = input_stream.readline()
        if not line:
            engine.wait()
            break
        if not engine.handle(line):
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
