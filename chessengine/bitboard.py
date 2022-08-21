from copy import copy
from math import log2

from .moves import (
    get_white_pawn_moves,
    get_white_rook_moves,
    get_white_bishop_moves,
    get_white_knight_moves,
    get_white_king_moves,
    get_white_queen_moves,
    get_black_pawn_moves,
    get_black_rook_moves,
    get_black_bishop_moves,
    get_black_knight_moves,
    get_black_king_moves,
    get_black_queen_moves,
)
from .lookup_tables import mask_position, clear_position, coords_to_pos, pos_to_coords
from .utils import get_bit_positions

# import logging

# logging.basicConfig(
#     filemode="w", filename="./log/debug_forward_search.log", level=logging.DEBUG
# )


class Board:
    """
    A class implementing a bitboard representation of a chess board
    """

    def __init__(self, side: str):
        self.white_pawns = 65280  # (A2 to H2)
        self.white_rooks = 129  # (A1 and H1)
        self.white_knights = 66  # (B1 and G1)
        self.white_bishops = 36  # (C1 and F1)
        self.white_queens = 8  # (D1)
        self.white_kings = 16  # (E1)

        self.black_pawns = 71776119061217280  # (A7 to H7)
        self.black_rooks = 9295429630892703744  # (A8 and H8)
        self.black_knights = 4755801206503243776  # (B8 and G8)
        self.black_bishops = 2594073385365405696  # (C8 and F8)
        self.black_queens = 576460752303423488  # (D8)
        self.black_kings = 1152921504606846976  # (E8)

        self.all_white = (
            self.white_pawns
            | self.white_rooks
            | self.white_knights
            | self.white_bishops
            | self.white_queens
            | self.white_kings
        )

        self.all_black = (
            self.black_pawns
            | self.black_rooks
            | self.black_knights
            | self.black_bishops
            | self.black_queens
            | self.black_kings
        )

        self.all_pieces = self.all_black | self.all_white

        self.piece_count = {
            ("white", "kings"): 1,
            ("white", "queens"): 1,
            ("white", "rooks"): 2,
            ("white", "bishops"): 2,
            ("white", "knights"): 2,
            ("white", "pawns"): 8,
            ("black", "kings"): 1,
            ("black", "queens"): 1,
            ("black", "rooks"): 2,
            ("black", "bishops"): 2,
            ("black", "knights"): 2,
            ("black", "pawns"): 8,
        }

        if side.lower().strip() not in ["black", "white"]:
            raise ValueError(f'side must be one of "black" or "white". Got {side}')
        self.side = side.lower().strip()
        self.opponent_side = "black" if self.side == "white" else "white"

        # A dictionary matching a side and piece to its corresponding bit board.
        # Useful when we want to iterate through all of the bitboards of the board.
        self.board_table = {
            ("white", "kings"): self.white_kings,
            ("white", "queens"): self.white_queens,
            ("white", "rooks"): self.white_rooks,
            ("white", "bishops"): self.white_bishops,
            ("white", "knights"): self.white_knights,
            ("white", "pawns"): self.white_pawns,
            ("black", "kings"): self.black_kings,
            ("black", "queens"): self.black_queens,
            ("black", "rooks"): self.black_rooks,
            ("black", "bishops"): self.black_bishops,
            ("black", "knights"): self.black_knights,
            ("black", "pawns"): self.black_pawns,
        }

        # Keep track of all moves made
        self.moves = []

    def __repr__(self):
        piece_list = ["\u2001" for _ in range(64)]
        unicode_piece = {
            ("white", "kings"): "\u2654",
            ("white", "queens"): "\u2655",
            ("white", "rooks"): "\u2656",
            ("white", "bishops"): "\u2657",
            ("white", "knights"): "\u2658",
            ("white", "pawns"): "\u2659",
            ("black", "kings"): "\u265A",
            ("black", "queens"): "\u265B",
            ("black", "rooks"): "\u265C",
            ("black", "bishops"): "\u265D",
            ("black", "knights"): "\u265E",
            ("black", "pawns"): "\u265F",
        }

        def add_bitboard_to_repr(board, s, p):
            board_string = bin(board)[2:]
            board_string = "0" * (64 - len(board_string)) + board_string
            for _ in range(64):
                if board_string[_] == "1":
                    piece_list[_] = unicode_piece[(s, p)]

        for side, piece in self.board_table:
            add_bitboard_to_repr(self.board_table[(side, piece)], side, piece)

        board_repr = ""
        for i in range(8):
            board_repr += "\u2001".join(piece_list[8 * i : 8 * i + 8][::-1])
            board_repr += "\n"
        return board_repr

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if self.side != other.side:
            return False
        return str(self) == str(other)

    @property
    def score(self):
        K = self.piece_count[("white", "kings")]
        Q = self.piece_count[("white", "queens")]
        R = self.piece_count[("white", "rooks")]
        B = self.piece_count[("white", "bishops")]
        N = self.piece_count[("white", "knights")]
        P = self.piece_count[("white", "pawns")]
        k = self.piece_count[("black", "kings")]
        q = self.piece_count[("black", "queens")]
        r = self.piece_count[("black", "rooks")]
        b = self.piece_count[("black", "bishops")]
        n = self.piece_count[("black", "knights")]
        p = self.piece_count[("black", "pawns")]
        s = 200 * (K - k) + 9 * (Q - q) + 5 * (R - r) + 3 * (B - b + N - n) + (P - p)
        if self.side == "white":
            return s
        return -s

    @property
    def board_pieces(self):
        if self.side == "white":
            return [
                ("white", "kings"),
                ("white", "queens"),
                ("white", "rooks"),
                ("white", "bishops"),
                ("white", "knights"),
                ("white", "pawns"),
            ]
        return [
            ("black", "kings"),
            ("black", "queens"),
            ("black", "rooks"),
            ("black", "bishops"),
            ("black", "knights"),
            ("black", "pawns"),
        ]

    @property
    def opponent_pieces(self):
        if self.side == "black":
            return [
                ("white", "kings"),
                ("white", "queens"),
                ("white", "rooks"),
                ("white", "bishops"),
                ("white", "knights"),
                ("white", "pawns"),
            ]
        return [
            ("black", "kings"),
            ("black", "queens"),
            ("black", "rooks"),
            ("black", "bishops"),
            ("black", "knights"),
            ("black", "pawns"),
        ]

    def copy(self):
        return copy(self)

    def get_side_bitboard(self, side: str) -> int:
        """
        Returns the bitboard containing all pieces for the given side
        """
        if side == "white":
            return self.all_white
        return self.all_black

    def get_bitboard(self, side: str, piece: str) -> int:
        """
        Returns the bitboard of the passed side for the passed pieces.
        Calling with side="black" and piece="king" will return the black_kings bitboard, and so on.
        """
        attrname = side + "_" + piece
        return getattr(self, attrname)

    def get_self_piece_bitboard(self, piece: str) -> int:
        """
        Returns the attribute corresponding to the passed piece, considering the board's
        own side. i.e. - If the board is white, calling with piece='king' will return
        white king, etc.
        piece can be one of - "kings", "queens", "bishops", "knights", "rooks", "pawns"
        """
        return self.get_bitboard(side=self.side, piece=piece)

    def update_board_state(self) -> None:
        """
        Updates self.all_white, self.all_black, self.all_pieces, and self.board_table
        every time a bitboard is updated
        """
        self.all_white = (
            self.white_pawns
            | self.white_rooks
            | self.white_knights
            | self.white_bishops
            | self.white_queens
            | self.white_kings
        )

        self.all_black = (
            self.black_pawns
            | self.black_rooks
            | self.black_knights
            | self.black_bishops
            | self.black_queens
            | self.black_kings
        )

        self.all_pieces = self.all_black | self.all_white

        self.board_table = {
            ("white", "kings"): self.white_kings,
            ("white", "queens"): self.white_queens,
            ("white", "rooks"): self.white_rooks,
            ("white", "bishops"): self.white_bishops,
            ("white", "knights"): self.white_knights,
            ("white", "pawns"): self.white_pawns,
            ("black", "kings"): self.black_kings,
            ("black", "queens"): self.black_queens,
            ("black", "rooks"): self.black_rooks,
            ("black", "bishops"): self.black_bishops,
            ("black", "knights"): self.black_knights,
            ("black", "pawns"): self.black_pawns,
        }

    def set_bitboard(self, side: str, piece: str, board: int) -> None:
        """
        Sets the bitboard for the passed arguments to the passed bitboard
        """
        attrname = side + "_" + piece
        setattr(self, attrname, board)
        self.update_board_state()

    def identify_piece_at(self, position: int) -> tuple:
        """
        Identifies if there is any piece on the position passed. Returns
        the identified piece, its side, and its board if a piece is found
        at that position, None otherwise. Position is a power of 2
        """
        for side, piece in self.board_table:
            board = self.board_table[(side, piece)]
            if board & position > 0:
                return side, piece, board
        return None, None, None

    def move(self, start: int, end: int, track: bool = True) -> None:
        """
        Moves the piece at start to end. Doesn't check anything, just makes
        the move (unless the start or end positions are invalid).
        """
        start_pos = log2(start)
        end_pos = log2(end)
        if not start_pos.is_integer():
            raise ValueError("The start position provided is not a power of 2")
        if not end_pos.is_integer():
            raise ValueError("The end position provided is not a power of 2")
        if not 0 <= start_pos <= 63:
            raise ValueError(
                f"The start position is outside the board - moving from {start_pos} to {end_pos}"
            )
        if not 0 <= end_pos <= 63:
            raise ValueError(
                f"The end position is outside the board - moving from {start_pos} to {end_pos}"
            )

        start_side, start_piece, start_board = self.identify_piece_at(start)
        if start_side is None:
            raise ValueError(f"There is no piece at position {start_pos} to move")

        end_side, end_piece, end_board = self.identify_piece_at(end)
        if end_side == start_side:
            raise ValueError(
                f"Can't move from {start_pos} to {end_pos}, both positions have {end_side} pieces."
            )

        if track:
            # Keep track of the board state before the move was made so we can undo
            start_state = (start, end, end_side, end_piece, end_board)
            self.moves.append(start_state)

        if end_piece is not None:
            # Clear the captured piece's position (set "end" to 0)
            opp_side_board = self.get_bitboard(end_side, end_piece)
            opp_side_board &= clear_position[end_pos]
            self.set_bitboard(end_side, end_piece, opp_side_board)
            self.piece_count[(end_side, end_piece)] -= 1

        # Clear the moved piece's original position (set "start" to 0)
        move_side_board = self.get_bitboard(start_side, start_piece)
        move_side_board &= clear_position[start_pos]

        # Set the moved piece's final position (set "end" to 1)
        move_side_board |= mask_position[end_pos]
        self.set_bitboard(start_side, start_piece, move_side_board)

    def make_moves(self, *moves: tuple[int]) -> None:
        """
        Given a number of moves as tuples (start, end), call
        Board.move on all
        """
        for start, end in moves:
            self.move(start, end)

    def undo_move(self):
        if not self.moves:
            raise RuntimeError("No moves have been made yet to undo.")
        end, start, side, piece, board = self.moves.pop()
        self.move(start=start, end=end, track=False)
        if side is not None:
            self.set_bitboard(side, piece, board)
            self.piece_count[(side, piece)] += 1

    def get_moves(
        self, side: str, piece: str = None, position: int = None
    ) -> list[tuple[int, int]]:
        """
        Gets all end positions a piece of side can reach starting from position
        """
        if piece is not None:
            if position is None:
                raise TypeError("'position' cannot be None if piece is provided.")
            move_gens = {
                ("white", "kings"): get_white_king_moves,
                ("white", "queens"): get_white_queen_moves,
                ("white", "rooks"): get_white_rook_moves,
                ("white", "bishops"): get_white_bishop_moves,
                ("white", "knights"): get_white_knight_moves,
                ("white", "pawns"): get_white_pawn_moves,
                ("black", "kings"): get_black_king_moves,
                ("black", "queens"): get_black_queen_moves,
                ("black", "rooks"): get_black_rook_moves,
                ("black", "bishops"): get_black_bishop_moves,
                ("black", "knights"): get_black_knight_moves,
                ("black", "pawns"): get_black_pawn_moves,
            }
            # TODO - Add support for en passant move detection
            return move_gens[(side, piece)](self, position)
        else:
            moves = []
            for side, piece in self.board_pieces:
                positions = get_bit_positions(self.get_bitboard(side, piece))
                for position in positions:
                    moves.extend(self.get_moves(side, piece, position))
            return moves

    def search_forward(self, depth: int = 4) -> tuple[int, tuple]:
        maximize = self.side == "white"
        best_score = -1000 if maximize else 1000

        moves = self.get_moves(self.side)
        best_move = moves[0]

        for move in moves:
            self.move(start=move[0], end=move[1])
            value = self.alpha_beta_search(
                depth=depth - 1, maximizing_player=not maximize
            )
            self.undo_move()

            if maximize and value >= best_score:
                best_score = value
                best_move = move
            elif not maximize and value <= best_score:
                best_score = value
                best_move = move
        return best_score, best_move

    def alpha_beta_search(
        self,
        depth: int = 4,
        alpha: int = -1000,
        beta: int = 1000,
        maximizing_player: bool = True,
    ) -> int:
        if depth == 0:
            return self.score

        if maximizing_player:
            value = -1000
            moves = self.get_moves(self.side)
            for move in moves:
                self.move(start=move[0], end=move[1])
                final_score = self.alpha_beta_search(depth - 1, alpha, beta, False)
                value = max(value, final_score)
                self.undo_move()
                if value >= beta:
                    break
                alpha = max(alpha, value)
            return value
        else:
            value = 1000
            moves = self.get_moves(self.opponent_side)
            for move in moves:
                self.move(start=move[0], end=move[1])
                final_score = self.alpha_beta_search(depth - 1, alpha, beta, True)
                value = min(value, final_score)
                self.undo_move()
                if value <= alpha:
                    break
                beta = min(beta, value)
            return value

    def play(self, search_depth: int = 4) -> None:
        """
        The game loop.
        """

        def clear_lines(n):
            """
            Clears the last n lines printed so we can print there again
            """
            LINE_UP = "\033[1A"
            LINE_CLEAR = "\x1b[2K"
            for i in range(n):
                print(LINE_UP, end=LINE_CLEAR)

        print("\n" * 10)
        side_to_move = "white"
        while True:
            clear_lines(1)
            if side_to_move == self.side:
                best_score, best_move = self.search_forward(search_depth)
                print(f"Chose to move {log2(best_move[0])} to {log2(best_move[1])}")
                self.move(best_move[0], best_move[1])

                clear_lines(10)
                print(
                    f"Board moves from {pos_to_coords[log2(best_move[0])]} to {pos_to_coords[log2(best_move[1])]}"
                )
                print(self)
            else:
                move_to_make = input(
                    "Enter the move you want to make (e.g. A4-C5 moves a piece from A4 to C5) - "
                ).strip()
                if move_to_make.lower() == "q":
                    print(f"Thanks for playing!")
                    return
                if move_to_make.lower() == "u":
                    try:
                        self.undo_move()
                        self.undo_move()
                    except RuntimeError:
                        print("No moves have been made yet to undo!\n")
                    continue

                move = move_to_make.upper().split("-")
                try:
                    start = 2 ** coords_to_pos[move[0]]
                    end = 2 ** coords_to_pos[move[1]]
                except KeyError:
                    print('The move you entered was in an incorrect format. Try again\n')
                    continue

                moving_side, moving_piece, moving_board = self.identify_piece_at(start)
                if moving_side == self.side:
                    raise ValueError(f"You cannot move {moving_side} pieces.")
                if moving_side is None:
                    print(f"There is no piece at {move[0]} to move. Try again.\n")
                    continue

                valid_moves = self.get_moves(moving_side, moving_piece, start)
                if (start, end) not in valid_moves:
                    print(
                        f"{move[0]} to {move[1]} is not a valid move for your {moving_piece[:-1]}.\n"
                    )
                    continue
                self.move(start, end)
                clear_lines(10)
                print(f"You moved from {move[0]} to {move[1]}")
                print(self)

            if side_to_move == "white":
                side_to_move = "black"
            else:
                side_to_move = "white"
