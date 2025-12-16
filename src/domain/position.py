"""
Position value object representing a board coordinate.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """
    Immutable value object representing a position on the board.

    Attributes:
        row: Row index (0-based, 0 = top)
        col: Column index (0-based, 0 = left)
    """
    row: int
    col: int

    def __str__(self) -> str:
        return f"({self.row}, {self.col})"

    def is_valid(self, rows: int, cols: int) -> bool:
        """Check if position is within board bounds."""
        return 0 <= self.row < rows and 0 <= self.col < cols

    def add(self, row_delta: int, col_delta: int) -> 'Position':
        """Create new position with offset applied."""
        return Position(self.row + row_delta, self.col + col_delta)