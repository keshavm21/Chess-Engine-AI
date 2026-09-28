"""Static evaluation: material, piece-square tables and positional terms.

Scores are in pawns from White's point of view (positive = good for White).
"""

CHECKMATE = 1000
STALEMATE = 0

# ---------- Piece values ----------
PIECE_VALUES = {"K": 0, "Q": 10, "R": 5, "B": 3, "N": 3, "p": 1}

# ---------- Piece-square tables (8x8 matrices) ----------
PAWN_TABLE = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [78, 83, 86, 73, 102, 82, 85, 90],
    [7, 29, 41, 74, 80, 31, 44, 7],
    [-17, 16, -2, 15, 14, 0, 15, -13],
    [-26, 3, 10, 9, 6, 1, 0, -23],
    [-22, 9, 5, -11, -10, -2, 3, -19],
    [-31, 8, -7, -37, -36, -14, 3, -31],
    [0, 0, 0, 0, 0, 0, 0, 0],
]

KNIGHT_TABLE = [
    [-66, -53, -75, -75, -10, -55, -58, -70],
    [-3, -6, 100, -36, 4, 62, -4, -14],
    [10, 67, 41, 74, 73, 27, 62, -2],
    [24, 24, 45, 37, 33, 41, 25, 17],
    [-1, 5, 31, 21, 22, 35, 2, 0],
    [-18, 10, 13, 22, 18, 15, 11, -14],
    [-23, -15, 2, 0, 2, 0, -23, -20],
    [-74, -23, -26, -24, -19, -35, -22, -69],
]

BISHOP_TABLE = [
    [-59, -78, -82, -76, -23, -107, -37, -50],
    [-11, 20, 35, -42, -39, 31, 2, -22],
    [-9, 39, -32, 41, 52, -10, 28, -14],
    [25, 17, 20, 34, 26, 25, 15, 10],
    [13, 10, 17, 23, 17, 16, 0, 7],
    [14, 25, 24, 15, 8, 25, 20, 15],
    [19, 20, 11, 6, 7, 6, 20, 16],
    [-7, 2, -15, -12, -14, -15, -10, -10],
]

ROOK_TABLE = [
    [35, 29, 33, 4, 37, 33, 56, 50],
    [55, 29, 56, 67, 55, 62, 34, 60],
    [19, 35, 28, 33, 45, 27, 25, 15],
    [0, 5, 16, 13, 18, -4, -9, -6],
    [-28, -35, -16, -21, -13, -29, -46, -30],
    [-42, -28, -42, -25, -25, -35, -26, -46],
    [-53, -38, -31, -26, -29, -43, -44, -53],
    [-30, -24, -18, 5, -2, -18, -31, -32],
]

QUEEN_TABLE = [
    [6, 1, -8, -104, 69, 24, 88, 26],
    [14, 32, 60, -10, 20, 76, 57, 24],
    [-2, 43, 32, 60, 72, 63, 43, 2],
    [1, -16, 22, 17, 25, 20, -13, -6],
    [-14, -15, -2, -5, -1, -10, -20, -22],
    [-30, -6, -13, -11, -16, -11, -16, -27],
    [-36, -18, 0, -19, -15, -15, -21, -38],
    [-39, -30, -31, -13, -31, -36, -34, -42],
]

KING_TABLE = [
    [4, 54, 47, -99, -99, 60, 83, -62],
    [-32, 10, 55, 56, 56, 55, 10, 3],
    [-62, 12, -57, 44, -67, 28, 37, -31],
    [-55, 50, 11, -4, -19, 13, 0, -49],
    [-55, -43, -52, -28, -51, -47, -8, -50],
    [-47, -42, -43, -79, -64, -32, -29, -32],
    [-4, 3, -14, -50, -57, -18, 13, 4],
    [17, 30, -3, -14, 6, -1, 40, 18],
]

PIECE_SQUARE_TABLES = {
    "N": KNIGHT_TABLE,
    "B": BISHOP_TABLE,
    "Q": QUEEN_TABLE,
    "R": ROOK_TABLE,
    "K": KING_TABLE,
    "wp": PAWN_TABLE,
    "bp": PAWN_TABLE,
}


# ---------- Caching and Optimization ----------
class EvaluationCache:
    def __init__(self, max_size=1000):
        self.cache = {}
        self.max_size = max_size
        self.access_count = {}

    def get_key(self, board, white_to_move):
        # Create a simple hash of the board state
        key_parts = []
        for r in range(8):
            for c in range(8):
                key_parts.append(board[r][c])
        key_parts.append(str(white_to_move))
        return "".join(key_parts)

    def get(self, key):
        if key in self.cache:
            self.access_count[key] = self.access_count.get(key, 0) + 1
            return self.cache[key]
        return None

    def put(self, key, value):
        if len(self.cache) >= self.max_size:
            # Remove least frequently used
            least_used = min(self.access_count.items(), key=lambda x: x[1])
            del self.cache[least_used[0]]
            del self.access_count[least_used[0]]
        self.cache[key] = value
        self.access_count[key] = 1


eval_cache = EvaluationCache()


# ---------- Helpers ----------
def flip_board_index_for_black(row, col):
    return 7 - row, col


def get_pst_value(square, row, col):
    piece = square[1]
    color = square[0]
    if piece == "p":
        table = PIECE_SQUARE_TABLES[square]  # 'wp' or 'bp' key provided
        if color == "w":
            return table[row][col]
        else:
            r, c = flip_board_index_for_black(row, col)
            return table[r][c]
    else:
        table = PIECE_SQUARE_TABLES[piece]
        if color == "w":
            return table[row][col]
        else:
            r, c = flip_board_index_for_black(row, col)
            return table[r][c]


def find_king_positions_from_board(board):
    """
    Return (white_king_pos, black_king_pos) as ( (wr,wc), (br,bc) )
    If a king isn't found, returns None for that king.
    """
    wk = None
    bk = None
    for r in range(8):
        for c in range(8):
            sq = board[r][c]
            if sq == "wK":
                wk = (r, c)
            elif sq == "bK":
                bk = (r, c)
            if wk and bk:
                return wk, bk
    return wk, bk


def _position_key(gs, white_to_move):
    """Hashable key describing the position content relevant to attack
    generation: board layout, which side's attacks are being asked for,
    the en-passant target square, and castling rights. This replaces
    id(gs.board), which never changes because GameState mutates the
    board in place -- so it can't tell two different positions apart."""
    board_tuple = tuple(cell for row in gs.board for cell in row)
    cr = gs.castling_rights
    return (
        white_to_move,
        board_tuple,
        gs.en_passant_square,
        cr.wks,
        cr.bks,
        cr.wqs,
        cr.bqs,
    )


def clear_attack_cache(gs):
    """Forget the attack sets cached on `gs` by get_all_attacks()."""
    if hasattr(gs, "_attack_cache"):
        gs._attack_cache.clear()


def get_all_attacks(gs, white_to_move):
    """Squares the given side can move to (from its legal moves), cached per position."""
    cache_key = _position_key(gs, white_to_move)
    if hasattr(gs, "_attack_cache") and cache_key in gs._attack_cache:
        return gs._attack_cache[cache_key]

    original = gs.white_to_move
    original_ep = gs.en_passant_square
    gs.white_to_move = white_to_move
    # En passant is only a real option for whichever side is actually on
    # move. When we're asking about the side that is NOT really on move
    # (a hypothetical "what could this side do" query), the live
    # en_passant_square square belongs to a different context and must be
    # suppressed -- otherwise _get_pawn_moves() can manufacture a bogus
    # en-passant capture that corrupts the board on make/undo.
    if white_to_move != original:
        gs.en_passant_square = ()
    try:
        moves = gs.get_legal_moves()
        attacks = set((m.end_row, m.end_col) for m in moves)
    finally:
        gs.white_to_move = original
        gs.en_passant_square = original_ep

    # Cache the result
    if not hasattr(gs, "_attack_cache"):
        gs._attack_cache = {}
    gs._attack_cache[cache_key] = attacks
    return attacks


def is_opening_phase(gs):
    """Check if we're still in opening phase"""
    piece_count = 0
    for r in range(8):
        for c in range(8):
            if gs.board[r][c] != "--":
                piece_count += 1
    return piece_count > 28  # Adjust based on when opening typically ends


# ---------- Opening Principles ----------
def count_developed_pieces(board, is_white):
    """Count developed minor pieces (knights and bishops off starting squares)"""
    developed = 0
    if is_white:
        if board[7][1] != "wN":
            developed += 1
        if board[7][6] != "wN":
            developed += 1
        if board[7][2] != "wB":
            developed += 1
        if board[7][5] != "wB":
            developed += 1
    else:
        if board[0][1] != "bN":
            developed += 1
        if board[0][6] != "bN":
            developed += 1
        if board[0][2] != "bB":
            developed += 1
        if board[0][5] != "bB":
            developed += 1
    return developed


def is_center_pawn_moved(board, is_white):
    """Check if center pawns (d and e pawns) have been moved"""
    if is_white:
        d_moved = board[6][3] != "wp"
        e_moved = board[6][4] != "wp"
        return d_moved or e_moved
    else:
        d_moved = board[1][3] != "bp"
        e_moved = board[1][4] != "bp"
        return d_moved or e_moved


def has_castled(board, is_white):
    """Check if a side has castled by looking at king position"""
    if is_white:
        king_pos = None
        for c in range(8):
            if board[7][c] == "wK":
                king_pos = c
                break
        return king_pos in [2, 6]
    else:
        king_pos = None
        for c in range(8):
            if board[0][c] == "bK":
                king_pos = c
                break
        return king_pos in [2, 6]


def has_queen_moved(board, is_white):
    """Check if queen has moved from starting position"""
    if is_white:
        return board[7][3] != "wQ"
    else:
        return board[0][3] != "bQ"


def opening_phase_score(gs):
    """
    Evaluate opening principles:
    - Penalize early queen moves (especially before development/castling)
    - Reward minor piece development
    - Reward castling
    - Reward center control with pawns
    """
    board = gs.board
    score = 0.0

    # Only apply opening principles in early game
    if not is_opening_phase(gs):
        return score

    # Count developed pieces for both sides
    white_developed = count_developed_pieces(board, True)
    black_developed = count_developed_pieces(board, False)

    # Reward development (0.5 per developed piece - increased)
    score += white_developed * 0.5
    score -= black_developed * 0.5

    # Check center pawn moves (good opening principle)
    white_center_moved = is_center_pawn_moved(board, True)
    black_center_moved = is_center_pawn_moved(board, False)

    if white_center_moved:
        score += 0.3
    if black_center_moved:
        score -= 0.3

    # Check if queens have moved
    white_queen_moved = has_queen_moved(board, True)
    black_queen_moved = has_queen_moved(board, False)

    # Check castling status
    white_castled = has_castled(board, True)
    black_castled = has_castled(board, False)

    # STRONGER penalties for early queen moves
    if black_queen_moved:
        if black_developed == 0:
            score += 2.5
        elif black_developed == 1:
            score += 2.0
        elif black_developed < 3:
            score += 1.5
        elif not black_center_moved:
            score += 1.0
        # NEW: Penalty for moving queen before castling
        if not black_castled:
            score += 0.8

    if white_queen_moved:
        if white_developed == 0:
            score -= 2.5
        elif white_developed == 1:
            score -= 2.0
        elif white_developed < 3:
            score -= 1.5
        elif not white_center_moved:
            score -= 1.0
        # NEW: Penalty for moving queen before castling
        if not white_castled:
            score -= 0.8

    # Reward castling (Increased reward)
    if black_castled:
        score -= 1.5
        if black_developed >= 2:
            score -= 0.6  # Extra bonus for castling after developing

    if white_castled:
        score += 1.5
        if white_developed >= 2:
            score += 0.6  # Extra bonus for castling after developing

    # Encourage castling if developed but haven't castled yet
    if black_developed >= 2 and not black_castled and not black_queen_moved:
        score -= 0.5

    if white_developed >= 2 and not white_castled and not white_queen_moved:
        score += 0.5

    return score


# ---------- Evaluation components ----------


def bishop_pair_bonus(board):
    """Adds a bonus for the bishop pair"""
    score = 0.0
    white_bishops = 0
    black_bishops = 0
    for r in range(8):
        for c in range(8):
            sq = board[r][c]
            if sq == "wB":
                white_bishops += 1
            elif sq == "bB":
                black_bishops += 1

    # Give a 0.5 advantage for holding the pair
    if white_bishops >= 2:
        score += 0.5
    if black_bishops >= 2:
        score -= 0.5

    return score


def rooks_on_files_score(board):
    """
    Rewards rooks on open or semi-open files.
    """
    score = 0.0

    # First, get a count of pawns on each file
    white_pawns_on_file = [0] * 8
    black_pawns_on_file = [0] * 8
    for r in range(8):
        for c in range(8):
            sq = board[r][c]
            if sq == "wp":
                white_pawns_on_file[c] += 1
            elif sq == "bp":
                black_pawns_on_file[c] += 1

    # Now, check for rooks and apply bonuses
    for r in range(8):
        for c in range(8):
            sq = board[r][c]
            if sq == "wR":
                if white_pawns_on_file[c] == 0:
                    # File is semi-open for white
                    score += 0.25
                    if black_pawns_on_file[c] == 0:
                        # File is fully open
                        score += 0.35  # Additional bonus
            elif sq == "bR":
                if black_pawns_on_file[c] == 0:
                    # File is semi-open for black
                    score -= 0.25
                    if white_pawns_on_file[c] == 0:
                        # File is fully open
                        score -= 0.35  # Additional bonus
    return score


def pawn_shield_bonus(gs, wk, bk):
    board = gs.board
    score = 0.0
    if wk:
        wk_r, wk_c = wk
        for dr, dc in [(1, -1), (1, 0), (1, 1)]:
            r, c = wk_r + dr, wk_c + dc
            if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == "wp":
                score += 0.15
    if bk:
        bk_r, bk_c = bk
        for dr, dc in [(-1, -1), (-1, 0), (-1, 1)]:
            r, c = bk_r + dr, bk_c + dc
            if 0 <= r < 8 and 0 <= c < 8 and board[r][c] == "bp":
                score -= 0.15
    return score


def king_safety(gs, wk, bk):
    score = 0.0
    black_attacks = get_all_attacks(gs, False)
    white_attacks = get_all_attacks(gs, True)

    def around(r, c):
        squares = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < 8 and 0 <= cc < 8:
                    squares.append((rr, cc))
        return squares

    if wk:
        wk_r, wk_c = wk
        for s in around(wk_r, wk_c):
            if s in black_attacks:
                score -= 0.25
    if bk:
        bk_r, bk_c = bk
        for s in around(bk_r, bk_c):
            if s in white_attacks:
                score += 0.25

    score += pawn_shield_bonus(gs, wk, bk)
    return score


def pawn_structure(gs):
    board = gs.board
    score = 0.0
    white_files = [0] * 8
    black_files = [0] * 8

    for r in range(8):
        for c in range(8):
            if board[r][c] == "wp":
                white_files[c] += 1
            elif board[r][c] == "bp":
                black_files[c] += 1

    for f in range(8):
        if white_files[f] > 1:
            score -= 0.20 * (white_files[f] - 1)
        if black_files[f] > 1:
            score += 0.20 * (black_files[f] - 1)

    for f in range(8):
        if white_files[f] > 0:
            if (f == 0 or white_files[f - 1] == 0) and (
                f == 7 or white_files[f + 1] == 0
            ):
                score -= 0.30
        if black_files[f] > 0:
            if (f == 0 or black_files[f - 1] == 0) and (
                f == 7 or black_files[f + 1] == 0
            ):
                score += 0.30

    # Passed pawns - only check relevant files to save time
    for c in range(8):
        if white_files[c] > 0:
            for r in range(7, -1, -1):
                if board[r][c] == "wp":
                    is_passed = True
                    # Quick check for blocking pawns
                    for rr in range(r + 1, 8):
                        for fc in (max(0, c - 1), c, min(7, c + 1)):
                            if board[rr][fc] == "bp":
                                is_passed = False
                                break
                        if not is_passed:
                            break
                    if is_passed:
                        score += 0.25 + (7 - r) * 0.03
                    break

        if black_files[c] > 0:
            for r in range(8):
                if board[r][c] == "bp":
                    is_passed = True
                    for rr in range(0, r):
                        for fc in (max(0, c - 1), c, min(7, c + 1)):
                            if board[rr][fc] == "wp":
                                is_passed = False
                                break
                        if not is_passed:
                            break
                    if is_passed:
                        score -= 0.25 + r * 0.03
                    break

    return score


def mobility_score(gs):
    # Use cached attack sets for faster calculation
    white_attacks = get_all_attacks(gs, True)
    black_attacks = get_all_attacks(gs, False)
    return (len(white_attacks) - len(black_attacks)) * 0.08


def tactical_score(gs):
    score = 0.0
    original = gs.white_to_move
    moves = gs.get_legal_moves()

    # Quick capture evaluation
    for m in moves:
        if m.piece_captured != "--":
            captured_value = PIECE_VALUES.get(m.piece_captured[1], 0)
            if original:
                score += 0.25 * captured_value
            else:
                score -= 0.25 * captured_value

    # Hanging pieces evaluation using cached attacks
    white_attacks = get_all_attacks(gs, True)
    black_attacks = get_all_attacks(gs, False)
    board = gs.board

    for r in range(8):
        for c in range(8):
            sq = board[r][c]
            if sq == "--":
                continue
            color = sq[0]
            piece_val = PIECE_VALUES.get(sq[1], 0)
            if color == "w":
                if (r, c) in black_attacks and (r, c) not in white_attacks:
                    score -= 0.15 * piece_val
            else:
                if (r, c) in white_attacks and (r, c) not in black_attacks:
                    score += 0.15 * piece_val
    return score


def is_in_check(gs, checking_black):
    wk, bk = find_king_positions_from_board(gs.board)
    king_pos = bk if checking_black else wk
    if king_pos is None:
        return False

    attacks = get_all_attacks(gs, not checking_black)
    return king_pos in attacks


# ---------- Main evaluation function ----------
def evaluate(gs, depth=0):
    # depth = plies of search still remaining when this terminal position
    # was reached. A mate found with more depth remaining took fewer
    # actual moves to arrive at (a faster mate); adding it to CHECKMATE
    # makes faster mates score more extreme than slower ones, so the
    # search prefers the fastest available mate and prefers resisting
    # the longest when it is the one being mated.
    if gs.checkmate:
        return -(CHECKMATE + depth) if gs.white_to_move else (CHECKMATE + depth)
    if gs.stalemate:
        return STALEMATE

    # Try cache first
    cache_key = eval_cache.get_key(gs.board, gs.white_to_move)
    cached = eval_cache.get(cache_key)
    if cached is not None:
        return cached

    board = gs.board
    score = 0.0

    # find kings from board
    wk, bk = find_king_positions_from_board(board)

    # MATERIAL + PST
    for r in range(8):
        for c in range(8):
            sq = board[r][c]
            if sq == "--":
                continue
            color = sq[0]
            piece = sq[1]
            base = PIECE_VALUES.get(piece, 0)
            pst = 0
            if piece != "K":
                pst = get_pst_value(sq, r, c) * 0.01
            if color == "w":
                score += base + pst
            else:
                score -= base + pst

    # NEW PARAMETER: BISHOP PAIR
    score += bishop_pair_bonus(board)

    # NEW PARAMETER: ROOKS ON FILES
    score += rooks_on_files_score(board)

    # OPENING PRINCIPLES (only in opening)
    score += opening_phase_score(gs)

    # MOBILITY
    score += mobility_score(gs)

    # KING SAFETY
    score += king_safety(gs, wk, bk)

    # CHECKS
    if is_in_check(gs, True):
        score -= 0.6
    if is_in_check(gs, False):
        score += 0.6

    # PAWN STRUCTURE
    score += pawn_structure(gs)

    # TACTICAL
    score += tactical_score(gs)

    if score > CHECKMATE:
        score = CHECKMATE
    if score < -CHECKMATE:
        score = -CHECKMATE

    # Cache the result
    eval_cache.put(cache_key, score)
    return score
