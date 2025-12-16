"""
Token value object for Connect Four.
Represents the three possible cell states on the board.
"""
from enum import Enum


class Token(str, Enum):
    """
    Cell state in Connect Four board.
    Using str Enum for easy JSON serialization.
    """
    PLAYER_ONE = "X"
    PLAYER_TWO = "O"
    EMPTY = "."

    def __str__(self) -> str:
        return self.value

    @property
    def is_empty(self) -> bool:
        """Check if token represents an empty cell."""
        return self == Token.EMPTY

    @property
    def is_player_token(self) -> bool:
        """Check if token belongs to a player."""
        return self != Token.EMPTY

    def opposite(self) -> 'Token':
        """Get the opposite player's token."""
        if self == Token.PLAYER_ONE:
            return Token.PLAYER_TWO
        elif self == Token.PLAYER_TWO:
            return Token.PLAYER_ONE
        else:
            raise ValueError("Cannot get opposite of EMPTY token")