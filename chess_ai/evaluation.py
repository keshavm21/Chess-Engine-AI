"""Static evaluation in centipawns (100 = one pawn), from White's point of view.

The score is the sum of a few well-known terms, each simple enough to explain:

- material,
- piece-square tables: where each piece stands well, blended ("tapered")
  between a middlegame and an endgame table by how much material is left,
- pawn structure: doubled, isolated and passed pawns,
- the bishop pair, and rooks on open or half-open files,
- a pawn shield in front of the king (middlegame only),
- a small bonus for the side to move.

Tactics are deliberately left out: the search's quiescence search plays out
captures before a position is evaluated. The evaluation is a pure function of
the board and the side to move.
"""

CHECKMATE = 100_000
STALEMATE = 0

PIECE_VALUES = {"p": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}

# Game phase: 24 with all pieces on the board, 0 with only kings and pawns.
PHASE_WEIGHTS = {"N": 1, "B": 1, "R": 2, "Q": 4}
MAX_PHASE = 24

BISHOP_PAIR = 30
ROOK_OPEN_FILE = 20  # no pawns on the file
ROOK_HALF_OPEN_FILE = 10  # no own pawns on the file
DOUBLED_PAWN = -15  # per extra pawn on a file
ISOLATED_PAWN = -15  # no own pawns on the neighbouring files
# Passed pawn bonus by rank, seen from the pawn's own side (index 0 = rank 1).
PASSED_PAWN = (0, 5, 10, 20, 35, 60, 100, 0)
SHIELD_PAWN = (10, 5)  # own pawn one / two ranks in front of the king
TEMPO = 10


# ---------- Piece-square tables ----------
# Built from simple rules (not copied from another engine), so every value can
# be explained. Tables are from White's point of view with row 0 = rank 8, as on
# GameState.board; Black uses the vertically mirrored square.


def _center_distance(r, c):
    """Distance to the centre in half-squares: 2 for d4/e4/d5/e5, 14 in a corner."""
    return abs(2 * r - 7) + abs(2 * c - 7)


def _knight(r, c):
    # Knights want the centre and are poor on the rim; a small penalty on the
    # back rank encourages development.
    return 30 - 6 * _center_distance(r, c) - (10 if r == 7 else 0)


def _bishop(r, c):
    return 15 - 3 * _center_distance(r, c) - (10 if r == 7 else 0)


def _rook(r, c):
    # The 7th rank attacks pawns and hems in the king; d1/e1 are good
    # central squares after castling.
    if r == 1:
        return 20
    return 5 if r == 7 and c in (3, 4) else 0


def _queen(r, c):
    return 5 - _center_distance(r, c)  # mild preference for the centre


def _pawn_middlegame(r, c):
    rank = 8 - r
    value = {3: 5, 4: 10, 5: 20, 6: 30, 7: 50}.get(rank, 0)
    if c in (3, 4):  # d- and e-pawns
        if rank in (4, 5):
            value += 15  # central pawns control the centre
        elif rank == 2:
            value -= 10  # an unmoved centre pawn blocks the pieces
    return value


def _pawn_endgame(r, c):
    return {3: 10, 4: 20, 5: 35, 6: 55, 7: 80}.get(8 - r, 0)


def _king_middlegame(r, c):
    # Before the endgame the king belongs behind its pawns, ideally castled.
    if r == 7:
        return (20, 30, 10, 0, 0, 10, 30, 20)[c]
    if r == 6:
        return (10, 10, -5, -10, -10, -5, 10, 10)[c]
    return -20 - 10 * (5 - r)  # further forward is ever more dangerous


def _king_endgame(r, c):
    return 20 - 5 * _center_distance(r, c)  # in the endgame the king centralises


def _table(rule):
    return [[rule(r, c) for c in range(8)] for r in range(8)]


MIDDLEGAME_TABLES = {
    "p": _table(_pawn_middlegame),
    "N": _table(_knight),
    "B": _table(_bishop),
    "R": _table(_rook),
    "Q": _table(_queen),
    "K": _table(_king_middlegame),
}
ENDGAME_TABLES = {
    **MIDDLEGAME_TABLES,
    "p": _table(_pawn_endgame),
    "K": _table(_king_endgame),
}


# ---------- Evaluation ----------


def _divide(total, divisor):
    """Integer division rounding toward zero, so that the evaluation of a
    position is exactly the negative of its colour-mirrored twin."""
    return total // divisor if total >= 0 else -(-total // divisor)


def evaluate(gs):
    """Score of the position in centipawns from White's point of view.

    Honours ``gs.checkmate`` / ``gs.stalemate`` if they are set (the GUI sets
    them); the search detects mate and stalemate itself.
    """
    if gs.checkmate:
        return -CHECKMATE if gs.white_to_move else CHECKMATE
    if gs.stalemate:
        return STALEMATE

    middlegame = endgame = 0  # White minus Black
    phase = 0
    pawns = {"w": [], "b": []}
    pawn_files = {"w": [0] * 8, "b": [0] * 8}
    bishops = {"w": 0, "b": 0}
    rook_files = {"w": [], "b": []}
    kings = {}

    for r, row in enumerate(gs.board):
        for c, square in enumerate(row):
            if square == "--":
                continue
            color, kind = square
            sign, table_row = (1, r) if color == "w" else (-1, 7 - r)
            value = PIECE_VALUES[kind]
            middlegame += sign * (value + MIDDLEGAME_TABLES[kind][table_row][c])
            endgame += sign * (value + ENDGAME_TABLES[kind][table_row][c])
            if kind == "p":
                pawns[color].append((r, c))
                pawn_files[color][c] += 1
            elif kind == "K":
                kings[color] = (r, c)
            else:
                phase += PHASE_WEIGHTS[kind]
                if kind == "B":
                    bishops[color] += 1
                elif kind == "R":
                    rook_files[color].append(c)

    both = 0  # terms that are the same in the middlegame and the endgame
    for color, sign, other in (("w", 1, "b"), ("b", -1, "w")):
        files = pawn_files[color]

        # Pawn structure.
        for count in files:
            if count > 1:
                both += sign * DOUBLED_PAWN * (count - 1)
        for r, c in pawns[color]:
            neighbours = [f for f in (c - 1, c + 1) if 0 <= f < 8]
            if not any(files[f] for f in neighbours):
                both += sign * ISOLATED_PAWN
            if _is_passed(r, c, color, pawns[other]):
                rank = 8 - r if color == "w" else r + 1
                bonus = PASSED_PAWN[rank - 1]
                middlegame += sign * (bonus // 2)
                endgame += sign * bonus

        # Pieces.
        if bishops[color] >= 2:
            both += sign * BISHOP_PAIR
        for c in rook_files[color]:
            if not files[c]:
                open_file = not pawn_files[other][c]
                both += sign * (ROOK_OPEN_FILE if open_file else ROOK_HALF_OPEN_FILE)

        # King shield (only matters while there is material to attack with).
        if color in kings:
            middlegame += sign * _pawn_shield(gs.board, kings[color], color)

    phase = min(phase, MAX_PHASE)
    score = _divide(middlegame * phase + endgame * (MAX_PHASE - phase), MAX_PHASE)
    score += both
    score += TEMPO if gs.white_to_move else -TEMPO
    return score


def _is_passed(r, c, color, enemy_pawns):
    """No enemy pawn ahead of this pawn on its own or a neighbouring file."""
    for er, ec in enemy_pawns:
        if abs(ec - c) <= 1 and (er < r if color == "w" else er > r):
            return False
    return True


def _pawn_shield(board, king, color):
    """Bonus for own pawns directly in front of a king on its first two ranks."""
    r, c = king
    forward = -1 if color == "w" else 1
    home_ranks = (7, 6) if color == "w" else (0, 1)
    if r not in home_ranks:
        return 0
    pawn = color + "p"
    bonus = 0
    for step, value in zip((1, 2), SHIELD_PAWN):
        rr = r + forward * step
        if 0 <= rr < 8:
            for cc in (c - 1, c, c + 1):
                if 0 <= cc < 8 and board[rr][cc] == pawn:
                    bonus += value
    return bonus
