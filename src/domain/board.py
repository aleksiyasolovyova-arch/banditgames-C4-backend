"""
Board value object with rich domain behavior.
RICH DOMAIN MODEL - contains business logic related to board state.

"""
from typing import List, Optional, Tuple

from .token import Token
from .position import Position


class Board:
    """
    Rich domain model representing the Connect Four board.

    """

    # Constants
    DEFAULT_ROWS = 6
    DEFAULT_COLS = 7
    WIN_LENGTH = 4

    def __init__(self, rows: int = DEFAULT_ROWS, cols: int = DEFAULT_COLS,
                 grid: Optional[List[List[Token]]] = None):
        """
        Initialize board.

        Args:
            rows: Number of rows
            cols: Number of columns
            grid: Optional pre-existing grid (for cloning)
        """
        self.rows = rows
        self.cols = cols

        if grid is None:
            self._grid = [[Token.EMPTY for _ in range(cols)] for _ in range(rows)]
        else:
            # Deep copy the grid
            self._grid = [row[:] for row in grid]

    # Query Methods - Read board state

    def get_cell(self, position: Position) -> Token:
        """Get token at position."""
        if not position.is_valid(self.rows, self.cols):
            raise ValueError(f"Invalid position: {position}")
        return self._grid[position.row][position.col]

    def is_column_available(self, column: int) -> bool:
        """Check if column has space for a piece."""
        if not 0 <= column < self.cols:
            return False
        return self._grid[0][column] == Token.EMPTY

    def get_available_columns(self) -> List[int]:
        """Get list of columns that can accept a piece."""
        return [col for col in range(self.cols) if self.is_column_available(col)]

    def is_full(self) -> bool:
        """Check if board is completely full."""
        return len(self.get_available_columns()) == 0

    def find_landing_row(self, column: int) -> Optional[int]:
        """
        Find the row where a piece would land if dropped in column.

        Returns:
            Row index, or None if column is full
        """
        if not self.is_column_available(column):
            return None

        # Find lowest empty row
        for row in range(self.rows - 1, -1, -1):
            if self._grid[row][column] == Token.EMPTY:
                return row
        return None

    # Command Methods - Modify board state

    def drop_piece(self, column: int, token: Token) -> Tuple['Board', Position]:
        """
        Drop a piece in the column and return NEW board (functional style).

        Following functional programming principles:
        - Returns new Board instead of modifying this one
        - Original board remains unchanged
        - Thread-safe and testable

        Args:
            column: Column to drop piece
            token: Token to place

        Returns:
            Tuple of (new_board, landing_position)

        Raises:
            ValueError: If move is invalid
        """
        if not self.is_column_available(column):
            raise ValueError(f"Column {column} is not available")

        if token == Token.EMPTY:
            raise ValueError("Cannot drop EMPTY token")

        row = self.find_landing_row(column)
        if row is None:
            raise ValueError(f"No space in column {column}")

        # Create new board with the piece placed
        new_grid = [row[:] for row in self._grid]
        new_grid[row][column] = token
        new_board = Board(self.rows, self.cols, new_grid)

        landing_position = Position(row, column)
        return new_board, landing_position

    # Win Detection - Core game logic

    def check_winner(self) -> Optional[Token]:
        """
        Check if there's a winner on the board.

        Returns:
            Winning token, or None if no winner yet
        """
        # Check all positions and directions
        directions = [
            (0, 1),  # Horizontal
            (1, 0),  # Vertical
            (1, 1),  # Diagonal down-right
            (1, -1)  # Diagonal down-left
        ]

        for row in range(self.rows):
            for col in range(self.cols):
                token = self._grid[row][col]

                if token == Token.EMPTY:
                    continue

                # Check each direction from this position
                for delta_row, delta_col in directions:
                    if self._check_line_from_position(
                            Position(row, col),
                            delta_row,
                            delta_col,
                            token
                    ):
                        return token

        return None

    def _check_line_from_position(
            self,
            start: Position,
            delta_row: int,
            delta_col: int,
            token: Token
    ) -> bool:
        """
        Check if there's a winning line starting from position.

        Args:
            start: Starting position
            delta_row: Row increment direction
            delta_col: Column increment direction
            token: Token to check for

        Returns:
            True if winning line found
        """
        count = 0
        current = start

        # Count consecutive tokens in direction
        while current.is_valid(self.rows, self.cols) and count < self.WIN_LENGTH:
            if self.get_cell(current) != token:
                break
            count += 1
            current = current.add(delta_row, delta_col)

        return count >= self.WIN_LENGTH

    # Serialization

    def to_2d_list(self) -> List[List[str]]:
        """Convert board to 2D list of string tokens."""
        return [[cell.value for cell in row] for row in self._grid]

    def to_dict(self) -> dict:
        """Serialize board to dictionary."""
        return {
            "rows": self.rows,
            "cols": self.cols,
            "grid": self.to_2d_list(),
            "availableColumns": self.get_available_columns()
        }

    @classmethod
    def from_2d_list(cls, grid: List[List[str]]) -> 'Board':
        """
        Create board from 2D list of string tokens.

        Args:
            grid: 2D list where each cell is "X", "O", or "."
        """
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0

        # Convert strings to Token enums
        token_grid = [
            [Token(cell) for cell in row]
            for row in grid
        ]

        return cls(rows, cols, token_grid)

    def clone(self) -> 'Board':
        """Create a deep copy of this board."""
        return Board(self.rows, self.cols, self._grid)

    def __str__(self) -> str:
        """Pretty print the board."""
        lines = []

        # Column numbers
        lines.append("  " + " ".join(str(i) for i in range(self.cols)))
        lines.append("  " + "-" * (self.cols * 2 - 1))

        # Board rows
        for row in self._grid:
            lines.append("  " + " ".join(cell.value for cell in row))

        return "\n".join(lines)