"""Board state and chess rules.

GameState holds the position, makes and takes back moves, and generates legal
moves; Move describes a single move; CastlingRights records who may castle.
"""

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

_PIECE_FROM_FEN = {
    "p": "bp", "n": "bN", "b": "bB", "r": "bR", "q": "bQ", "k": "bK",
    "P": "wp", "N": "wN", "B": "wB", "R": "wR", "Q": "wQ", "K": "wK",
}  # fmt: skip
_FEN_FROM_PIECE = {piece: letter for letter, piece in _PIECE_FROM_FEN.items()}
# Pieces a pawn may promote to; the queen comes first so it is searched first.
PROMOTION_PIECES = ("Q", "R", "B", "N")


class GameState:
    def __init__(self):
        # this is a 2d representation of the board from White's perspective
        # the representation is pretty easy:
        # the first character is about the piece color: b = black, w = white
        # and the second one is the piece standard notation:
        # K = King, Q = Queen, R = Rook, B = Bishop, N = Knight, p = pawn
        # finally, "--" is for empty squares
        self.board = [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],  # 8th rank
            ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],  # 7th rank
            ["--", "--", "--", "--", "--", "--", "--", "--"],  # 6th rank
            ["--", "--", "--", "--", "--", "--", "--", "--"],  # 5th rank
            ["--", "--", "--", "--", "--", "--", "--", "--"],  # 4th rank
            ["--", "--", "--", "--", "--", "--", "--", "--"],  # 3rd rank
            ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],  # 2nd rank
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],  # 1st rank
        ]

        self.white_to_move = True
        self.move_log = []  # Move objects
        self._move_generators = {
            "p": self._get_pawn_moves,
            "N": self._get_knight_moves,
            "B": self._get_bishop_moves,
            "R": self._get_rook_moves,
            "Q": self._get_queen_moves,
            "K": self._get_king_moves,
        }
        # to keep track of the kings locations because:
        # castling, checks, checkmates and stalemates
        self.white_king_location = (7, 4)
        self.black_king_location = (0, 4)
        self.checkmate = False
        self.stalemate = False
        # the square an en-passant capture would land on, or ()
        self.en_passant_square = ()
        self.en_passant_log = [self.en_passant_square]
        self.castling_rights = CastlingRights(True, True, True, True)
        self.castling_rights_log = [
            CastlingRights(
                self.castling_rights.wks,
                self.castling_rights.bks,
                self.castling_rights.wqs,
                self.castling_rights.bqs,
            )
        ]

    @classmethod
    def from_fen(cls, fen):
        """Return a new GameState set up from a FEN string.

        Reads piece placement, side to move, castling rights and the en-passant
        square. The halfmove clock and fullmove number may be present but are
        ignored, because the engine does not track them yet.

        Raises ValueError if the FEN is malformed.
        """
        fields = fen.split()
        if len(fields) < 4:
            raise ValueError(f"FEN needs at least 4 fields: {fen!r}")
        placement, side, castling, en_passant = fields[:4]

        ranks = placement.split("/")
        if len(ranks) != 8:
            raise ValueError(f"FEN placement needs 8 ranks: {fen!r}")
        board = []
        for rank in ranks:
            row = []
            for char in rank:
                if char in "12345678":
                    row.extend(["--"] * int(char))
                elif char in _PIECE_FROM_FEN:
                    row.append(_PIECE_FROM_FEN[char])
                else:
                    raise ValueError(f"invalid character {char!r} in FEN: {fen!r}")
            if len(row) != 8:
                raise ValueError(f"FEN rank {rank!r} does not have 8 squares")
            board.append(row)

        kings = {piece: [] for piece in ("wK", "bK")}
        for r in range(8):
            for c in range(8):
                if board[r][c] in kings:
                    kings[board[r][c]].append((r, c))
        if len(kings["wK"]) != 1 or len(kings["bK"]) != 1:
            raise ValueError(f"FEN must have exactly one king per side: {fen!r}")

        if side not in ("w", "b"):
            raise ValueError(f"FEN side to move must be 'w' or 'b': {fen!r}")
        if castling != "-" and (
            len(set(castling)) != len(castling) or set(castling) - set("KQkq")
        ):
            raise ValueError(f"invalid FEN castling field {castling!r}")
        if en_passant == "-":
            en_passant_square = ()
        elif (
            len(en_passant) == 2
            and en_passant[0] in "abcdefgh"
            and en_passant[1] in "36"
        ):
            en_passant_square = (8 - int(en_passant[1]), ord(en_passant[0]) - ord("a"))
        else:
            raise ValueError(f"invalid FEN en-passant square {en_passant!r}")

        gs = cls()
        gs.board = board
        gs.white_to_move = side == "w"
        gs.white_king_location = kings["wK"][0]
        gs.black_king_location = kings["bK"][0]
        gs.castling_rights = CastlingRights(
            "K" in castling, "k" in castling, "Q" in castling, "q" in castling
        )
        gs.castling_rights_log = [
            CastlingRights(
                gs.castling_rights.wks,
                gs.castling_rights.bks,
                gs.castling_rights.wqs,
                gs.castling_rights.bqs,
            )
        ]
        gs.en_passant_square = en_passant_square
        gs.en_passant_log = [en_passant_square]
        return gs

    def to_fen(self):
        """Return the position as FEN: piece placement, side to move, castling
        rights and en-passant square.

        The halfmove clock and fullmove number are left out because the engine
        does not track them yet.
        """
        ranks = []
        for row in self.board:
            rank, empty = "", 0
            for square in row:
                if square == "--":
                    empty += 1
                    continue
                if empty:
                    rank += str(empty)
                    empty = 0
                rank += _FEN_FROM_PIECE[square]
            ranks.append(rank + (str(empty) if empty else ""))

        rights = self.castling_rights
        castling = "".join(
            letter
            for letter, allowed in zip(
                "KQkq", (rights.wks, rights.wqs, rights.bks, rights.bqs)
            )
            if allowed
        )
        if self.en_passant_square:
            r, c = self.en_passant_square
            en_passant = "abcdefgh"[c] + str(8 - r)
        else:
            en_passant = "-"
        side = "w" if self.white_to_move else "b"
        return f"{'/'.join(ranks)} {side} {castling or '-'} {en_passant}"

    def make_move(self, move):
        """Play `move` and update turn, king squares, en passant and castling rights."""
        self.board[move.start_row][move.start_col] = "--"
        self.board[move.end_row][move.end_col] = move.piece_moved
        # log the move, so we can undo it later or print a PNG for the game
        self.move_log.append(move)
        self.white_to_move = not self.white_to_move  # switch turns
        # update the both of the kings location after making a move
        if move.piece_moved == "wK":
            self.white_king_location = (move.end_row, move.end_col)
        elif move.piece_moved == "bK":
            self.black_king_location = (move.end_row, move.end_col)
        # pawn promotion: replace the pawn with the chosen piece
        if move.is_promotion:
            self.board[move.end_row][move.end_col] = (
                move.piece_moved[0] + move.promotion_piece
            )
        # about enpassant move
        if move.is_en_passant:
            self.board[move.start_row][move.end_col] = "--"  # capturing the pawn
        # update the en_passant_square variable
        # only for 2 square pawn advance
        if move.piece_moved[1] == "p" and abs(move.start_row - move.end_row) == 2:
            self.en_passant_square = (
                (move.start_row + move.end_row) // 2,
                move.start_col,
            )
        else:
            self.en_passant_square = ()
        # about castling
        if move.is_castle:
            # we need to check to see if it castles to left or right
            if move.end_col - move.start_col == 2:  # to the right: king side castle
                # copy the rook to the new square
                self.board[move.end_row][move.end_col - 1] = self.board[move.end_row][
                    move.end_col + 1
                ]
                self.board[move.end_row][move.end_col + 1] = "--"  # remove the old rook
            elif move.end_col - move.start_col == -2:  # to the left: queen side castle
                # copy the rook to the new square
                self.board[move.end_row][move.end_col + 1] = self.board[move.end_row][
                    move.end_col - 2
                ]
                self.board[move.end_row][move.end_col - 2] = "--"  # remove the old rook
        # update the en_passant_log
        self.en_passant_log.append(self.en_passant_square)
        # update the castling rights whenever its a rook or a king move
        self._update_castling_rights(move)
        self.castling_rights_log.append(
            CastlingRights(
                self.castling_rights.wks,
                self.castling_rights.bks,
                self.castling_rights.wqs,
                self.castling_rights.bqs,
            )
        )

    def undo_move(self):
        """Take back the last move in the move log (no-op if the log is empty)."""
        # first let's make sure that there's a move to undo
        if len(self.move_log) != 0:
            move = self.move_log.pop()
            self.board[move.start_row][move.start_col] = move.piece_moved
            self.board[move.end_row][move.end_col] = move.piece_captured
            self.white_to_move = not self.white_to_move  # switch turns
            # update the both of the kings location after undo a move
            if move.piece_moved == "wK":
                self.white_king_location = (move.start_row, move.start_col)
            elif move.piece_moved == "bK":
                self.black_king_location = (move.start_row, move.start_col)
            # delete checkmate and stalemate states
            self.checkmate = False
            self.stalemate = False
            # undo the enpassant move
            if move.is_en_passant:
                # we make the landing square blank as it was
                self.board[move.end_row][move.end_col] = "--"
                self.board[move.start_row][move.end_col] = move.piece_captured
            self.en_passant_log.pop()
            self.en_passant_square = self.en_passant_log[-1]
            # undo the castle rights
            # first get rid of the new castle rights from the move we're undoing
            self.castling_rights_log.pop()
            # then set the castling_rights to last one we have now on the log list
            new_rights = self.castling_rights_log[-1]
            self.castling_rights = CastlingRights(
                new_rights.wks, new_rights.bks, new_rights.wqs, new_rights.bqs
            )
            # undo the castle move
            if move.is_castle:
                # we need to check to see if it castles to left or right
                if move.end_col - move.start_col == 2:  # to the right: king side castle
                    # copy the rook to its starting square
                    self.board[move.end_row][move.end_col + 1] = self.board[
                        move.end_row
                    ][move.end_col - 1]
                    # remove the castled rook
                    self.board[move.end_row][move.end_col - 1] = "--"
                elif (
                    move.end_col - move.start_col == -2
                ):  # to the left: queen side castle
                    # copy the rook to its starting square
                    self.board[move.end_row][move.end_col - 2] = self.board[
                        move.end_row
                    ][move.end_col + 1]
                    # remove the castled rook
                    self.board[move.end_row][move.end_col + 1] = "--"
            # undo the checkmate and stalemate
            self.checkmate = False
            self.stalemate = False

    def _update_castling_rights(self, move):
        """Revoke castling rights when a king or rook moves or a rook is captured."""
        # check if the king moved or the rook moved
        if move.piece_moved == "wK":
            self.castling_rights.wks = False
            self.castling_rights.wqs = False
        elif move.piece_moved == "bK":
            self.castling_rights.bks = False
            self.castling_rights.bqs = False
        elif move.piece_moved == "wR":
            if move.start_row == 7:
                if move.start_col == 0:  # White's queenside rook
                    self.castling_rights.wqs = False
                if move.start_col == 7:  # White's kingside rook
                    self.castling_rights.wks = False
        elif move.piece_moved == "bR":
            if move.start_row == 0:
                if move.start_col == 0:  # Black's queenside rook
                    self.castling_rights.bqs = False
                if move.start_col == 7:  # Black's kingside rook
                    self.castling_rights.bks = False
        # check if a rook is captured
        if move.piece_captured == "wR":
            if move.end_row == 7:
                if move.end_col == 0:
                    self.castling_rights.wqs = False
                elif move.end_col == 7:
                    self.castling_rights.wks = False
        elif move.piece_captured == "bR":
            if move.end_row == 0:
                if move.end_col == 0:
                    self.castling_rights.bqs = False
                elif move.end_col == 7:
                    self.castling_rights.bks = False

    def get_legal_moves(self):
        """Return the legal moves for the side to move.

        This is a pure query: the position (including ``checkmate`` /
        ``stalemate``) is the same afterwards. Use update_game_status() to
        refresh those flags.
        """
        saved_en_passant_square = self.en_passant_square
        saved_castling_rights = CastlingRights(
            self.castling_rights.wks,
            self.castling_rights.bks,
            self.castling_rights.wqs,
            self.castling_rights.bqs,
        )
        # the easy, but not efficient solution is:
        # 1. let's generate all the possible moves and don't worry about the kings state
        moves = self.get_pseudo_legal_moves()
        # 2. for each move found, make that move
        # when removing from the list, go backwords :)
        for i in range(len(moves) - 1, -1, -1):
            self.make_move(moves[i])
            # 3. generate all opponent's moves
            # 4. for each of those moves, check if they attack your king
            # we need this as the make_move() did swap the players once
            self.white_to_move = not self.white_to_move
            if self.in_check():
                # 5. if they do, it's not a valid move
                moves.remove(moves[i])
            # we need this to return every thing as before
            self.white_to_move = not self.white_to_move
            self.undo_move()
        # to generate castle moves
        if self.white_to_move:
            self._get_castle_moves(
                self.white_king_location[0], self.white_king_location[1], moves
            )
        else:
            self._get_castle_moves(
                self.black_king_location[0], self.black_king_location[1], moves
            )
        self.en_passant_square = saved_en_passant_square
        self.castling_rights = saved_castling_rights
        return moves

    def update_game_status(self, legal_moves=None):
        """Set ``checkmate`` / ``stalemate`` for the side to move.

        Pass the result of get_legal_moves() if it is already known, to avoid
        generating the moves a second time.
        """
        if legal_moves is None:
            legal_moves = self.get_legal_moves()
        in_check = not legal_moves and self.in_check()
        self.checkmate = in_check
        self.stalemate = not legal_moves and not in_check

    def in_check(self):
        """True if the side to move is in check."""
        if self.white_to_move:
            return self.is_square_attacked(
                self.white_king_location[0], self.white_king_location[1]
            )
        else:
            return self.is_square_attacked(
                self.black_king_location[0], self.black_king_location[1]
            )

    def is_square_attacked(self, r, c):
        """True if the side not to move has a move landing on square (r, c)."""
        # first switch to the opponents move
        self.white_to_move = not self.white_to_move
        # generate all of its moves
        opponent_moves = self.get_pseudo_legal_moves()
        self.white_to_move = not self.white_to_move  # switch the turns back
        # check if any of those moves is attacking my kings location
        for move in opponent_moves:
            if move.end_row == r and move.end_col == c:  # now my king is under attack
                # note: we have done the move on our back end, so no need to undo_move() it
                return True
        return False  # none of my opponents move will be attacking my king

    def get_pseudo_legal_moves(self):
        """All moves for the side to move, ignoring whether they leave the king in check."""
        moves = []
        for r in range(len(self.board)):  # number of rows
            # number of columns in a given row
            for c in range(len(self.board[r])):
                turn = self.board[r][c][0]  # the piece color
                if (turn == "w" and self.white_to_move) or (
                    turn == "b" and not self.white_to_move
                ):
                    piece = self.board[r][c][1]  # the piece type
                    # generate the all possible valid moves for each piece
                    # a more better version of an if statemnet
                    self._move_generators[piece](r, c, moves)
        return moves

    def _get_pawn_moves(self, r, c, moves):
        """Append the moves of the pawn on (r, c) to `moves`."""
        if self.white_to_move:  # white pawn move
            if self.board[r - 1][c] == "--":  # the square in front of a pawn is empty
                # start square, end square, board
                self._add_pawn_move((r, c), (r - 1, c), moves)
                # check if it possible to advance to squares in the first move
                if r == 6 and self.board[r - 2][c] == "--":
                    moves.append(Move((r, c), (r - 2, c), self.board))
            if c - 1 >= 0:  # don't go outside the board from the left :)
                if (
                    self.board[r - 1][c - 1][0] == "b"
                ):  # there's an enemy piece to capture
                    self._add_pawn_move((r, c), (r - 1, c - 1), moves)
                elif (r - 1, c - 1) == self.en_passant_square:
                    moves.append(
                        Move((r, c), (r - 1, c - 1), self.board, is_en_passant=True)
                    )
            if c + 1 <= 7:  # don't go outside the board from the right :)
                if (
                    self.board[r - 1][c + 1][0] == "b"
                ):  # there's an enemy piece to capture
                    self._add_pawn_move((r, c), (r - 1, c + 1), moves)
                elif (r - 1, c + 1) == self.en_passant_square:
                    moves.append(
                        Move((r, c), (r - 1, c + 1), self.board, is_en_passant=True)
                    )

        else:  # black pawn move
            if self.board[r + 1][c] == "--":  # the square in front of a pawn is empty
                # start square, end square, board
                self._add_pawn_move((r, c), (r + 1, c), moves)
                # check if it possible to advance to squares in the first move
                if r == 1 and self.board[r + 2][c] == "--":
                    moves.append(Move((r, c), (r + 2, c), self.board))
            if c - 1 >= 0:  # don't go outside the board from the left :)
                if (
                    self.board[r + 1][c - 1][0] == "w"
                ):  # there's an enemy piece to capture
                    self._add_pawn_move((r, c), (r + 1, c - 1), moves)
                elif (r + 1, c - 1) == self.en_passant_square:
                    moves.append(
                        Move((r, c), (r + 1, c - 1), self.board, is_en_passant=True)
                    )
            if c + 1 <= 7:  # don't go outside the board from the right :)
                if (
                    self.board[r + 1][c + 1][0] == "w"
                ):  # there's an enemy piece to capture
                    self._add_pawn_move((r, c), (r + 1, c + 1), moves)
                elif (r + 1, c + 1) == self.en_passant_square:
                    moves.append(
                        Move((r, c), (r + 1, c + 1), self.board, is_en_passant=True)
                    )

    def _add_pawn_move(self, start, end, moves):
        """Append a pawn push or capture; on the last rank, one move per promotion piece."""
        if end[0] in (0, 7):  # a pawn can only reach its own last rank
            for piece in PROMOTION_PIECES:
                moves.append(Move(start, end, self.board, promotion_piece=piece))
        else:
            moves.append(Move(start, end, self.board))

    def _get_knight_moves(self, r, c, moves):
        """Append the moves of the knight on (r, c) to `moves`."""
        # the logic here is somehow different than the rook or the bishop
        # as that the knight is a short range piece
        # (row, col) representation for the 8 possible moves
        knight_moves = (
            (-1, -2),
            (-1, 2),
            (-2, -1),
            (-2, 1),
            (1, -2),
            (1, 2),
            (2, -1),
            (2, 1),
        )
        ally_color = "w" if self.white_to_move else "b"
        for m in knight_moves:
            end_row = r + m[0]
            end_col = c + m[1]
            if 0 <= end_row < 8 and 0 <= end_col < 8:
                end_piece = self.board[end_row][end_col]
                if end_piece[0] != ally_color:
                    moves.append(Move((r, c), (end_row, end_col), self.board))

    def _get_bishop_moves(self, r, c, moves):
        """Append the moves of the bishop on (r, c) to `moves`."""
        # (row, col) representation for the 4 diaganol moves
        directions = ((-1, -1), (-1, 1), (1, -1), (1, 1))
        enemy_color = "b" if self.white_to_move else "w"
        for d in directions:
            for i in range(1, 8):
                end_row = r + d[0] * i
                end_col = c + d[1] * i
                if 0 <= end_row < 8 and 0 <= end_col < 8:  # still on the board
                    end_piece = self.board[end_row][end_col]
                    if end_piece == "--":
                        # empty square, so we can reach it and check \
                        # if we can reach more squares after that
                        moves.append(Move((r, c), (end_row, end_col), self.board))
                    elif end_piece[0] == enemy_color:
                        # that's our enemy, so we can still capture
                        moves.append(Move((r, c), (end_row, end_col), self.board))
                        # but if we had to capture, then we can't check for more moves
                        # in that direction
                        break
                    else:
                        # friendly piece in the way, so we can't check that direction anymore
                        break
                else:  # we can't go out of the board
                    break

    def _get_rook_moves(self, r, c, moves):
        """Append the moves of the rook on (r, c) to `moves`."""
        # (row, col) representation
        # and from the White's perspective, the rook can move:
        # up, left, down, right
        directions = ((-1, 0), (0, -1), (1, 0), (0, 1))
        enemy_color = "b" if self.white_to_move else "w"
        for d in directions:
            for i in range(1, 8):
                end_row = r + d[0] * i
                end_col = c + d[1] * i
                if 0 <= end_row < 8 and 0 <= end_col < 8:  # still on the board
                    end_piece = self.board[end_row][end_col]
                    if end_piece == "--":
                        # empty square, so we can reach it and check \
                        # if we can reach more squares after that
                        moves.append(Move((r, c), (end_row, end_col), self.board))
                    elif end_piece[0] == enemy_color:
                        # that's our enemy, so we can still capture
                        moves.append(Move((r, c), (end_row, end_col), self.board))
                        # but if we had to capture, then we can't check for more moves
                        # in that direction
                        break
                    else:
                        # friendly piece in the way, so we can't check that direction anymore
                        break
                else:  # we can't go out of the board
                    break

    def _get_queen_moves(self, r, c, moves):
        """Append the moves of the queen on (r, c) to `moves`."""
        # as the queen has the power of both the rook and a bishop
        # it makes that code a lot easier
        self._get_bishop_moves(r, c, moves)
        self._get_rook_moves(r, c, moves)

    def _get_king_moves(self, r, c, moves):
        """Append the (non-castling) moves of the king on (r, c) to `moves`."""
        king_moves = (
            (-1, 0),
            (0, -1),
            (1, 0),
            (0, 1),  # like a rook
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        )  # like a bishop
        ally_color = "w" if self.white_to_move else "b"
        for i in range(8):
            end_row = r + king_moves[i][0]
            end_col = c + king_moves[i][1]
            if 0 <= end_row < 8 and 0 <= end_col < 8:
                end_piece = self.board[end_row][end_col]
                if end_piece[0] != ally_color:
                    moves.append(Move((r, c), (end_row, end_col), self.board))
        # self._get_castle_moves(r, c, moves, ally_color)

    def _get_castle_moves(self, r, c, moves):
        """Append the legal castling moves of the king on (r, c) to `moves`."""
        # 1st check if the king is in_check as the king can't escape the check by castling
        if self.is_square_attacked(r, c):
            return
        # 2nd check if the squares in between the king and the rook is vacated or not
        # 3rd check to see if any of those squares are under attack
        if (self.white_to_move and self.castling_rights.wks) or (
            not self.white_to_move and self.castling_rights.bks
        ):
            self._get_kingside_castle_moves(r, c, moves)
        if (self.white_to_move and self.castling_rights.wqs) or (
            not self.white_to_move and self.castling_rights.bqs
        ):
            self._get_queenside_castle_moves(r, c, moves)

    def _get_kingside_castle_moves(self, r, c, moves):
        if self.board[r][c + 1] == "--" and self.board[r][c + 2] == "--":
            if not self.is_square_attacked(r, c + 1) and not self.is_square_attacked(
                r, c + 2
            ):
                moves.append(Move((r, c), (r, c + 2), self.board, is_castle=True))

    def _get_queenside_castle_moves(self, r, c, moves):
        if (
            self.board[r][c - 1] == "--"
            and self.board[r][c - 2] == "--"
            and self.board[r][c - 3] == "--"
        ):
            # we need to just check if the squares that the king is moving through is under attack
            # not the rook's square or the third square on that queen side
            if not self.is_square_attacked(r, c - 1) and not self.is_square_attacked(
                r, c - 2
            ):
                moves.append(Move((r, c), (r, c - 2), self.board, is_castle=True))


class CastlingRights:
    def __init__(self, wks, bks, wqs, bqs):
        self.wks = wks
        self.bks = bks
        self.wqs = wqs
        self.bqs = bqs


class Move:
    RANKS_TO_ROWS = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}

    ROWS_TO_RANKS = {v: k for k, v in RANKS_TO_ROWS.items()}

    FILES_TO_COLS = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}

    COLS_TO_FILES = {v: k for k, v in FILES_TO_COLS.items()}

    def __init__(
        self,
        start_sq,
        end_sq,
        board,
        is_en_passant=False,
        is_castle=False,
        promotion_piece="Q",
    ):
        self.start_row, self.start_col = start_sq
        self.end_row, self.end_col = end_sq
        self.piece_moved = board[self.start_row][self.start_col]
        self.piece_captured = board[self.end_row][self.end_col]

        # enpassant move
        self.is_en_passant = is_en_passant
        if self.is_en_passant:
            self.piece_captured = "wp" if self.piece_moved == "bp" else "bp"

        # pawn promotion move: promotion_piece is "Q", "R", "B" or "N" (a queen
        # unless told otherwise, e.g. for a move built from two GUI clicks)
        self.is_promotion = (self.piece_moved == "wp" and self.end_row == 0) or (
            self.piece_moved == "bp" and self.end_row == 7
        )
        self.promotion_piece = promotion_piece if self.is_promotion else None

        # castle move
        self.is_castle = is_castle

        # see if the move was a capture move or not
        self.is_capture = self.piece_captured != "--"

        # a unique id for each move in the range of 0 and 7777
        self.move_id = (
            self.start_row * 1000
            + self.start_col * 100
            + self.end_row * 10
            + self.end_col
        )
        # print(self.move_id) # for debugging

    def __eq__(self, other):
        """Moves are equal when they have the same start and end squares and,
        for promotions, the same promotion piece."""
        if isinstance(other, Move):
            return (
                self.move_id == other.move_id
                and self.promotion_piece == other.promotion_piece
            )
        return False

    def coordinate_notation(self):
        """Long algebraic / UCI style notation, e.g. "e2e4" or "e7e8n"."""
        return (
            self.square_name(self.start_row, self.start_col)
            + self.square_name(self.end_row, self.end_col)
            + (self.promotion_piece.lower() if self.is_promotion else "")
        )

    def square_name(self, r, c):
        return self.COLS_TO_FILES[c] + self.ROWS_TO_RANKS[r]

    def __str__(self):
        # the castle move
        if self.is_castle:
            return "O-O" if self.end_col == 6 else "O-O-O"
        end_square = self.square_name(self.end_row, self.end_col)
        # pawn moves, captures, promotion
        if self.piece_moved[1] == "p":
            if self.is_capture:
                move_string = self.COLS_TO_FILES[self.start_col] + "x" + end_square
            else:
                move_string = end_square
            if self.is_promotion:
                move_string += "=" + self.promotion_piece
            return move_string
        # TODO: + for check, # for checkmate, and disambiguation when two
        # pieces can move to the same square
        # other piece moves, captures
        move_string = self.piece_moved[1]
        if self.is_capture:
            move_string += "x"
        return move_string + end_square
