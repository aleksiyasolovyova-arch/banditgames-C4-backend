"""
Game status enumeration.
"""
from enum import Enum


class GameStatus(str, Enum):
    """
    Current state of a game.
    Using str Enum for easy JSON serialization.
    """
    IN_PROGRESS = "in_progress"
    PLAYER_ONE_WIN = "player_one_win"
    PLAYER_TWO_WIN = "player_two_win"
    DRAW = "draw"
    ABANDONED = "abandoned"

    @property
    def is_finished(self) -> bool:
        """Check if game is in a terminal state."""
        return self in {
            GameStatus.PLAYER_ONE_WIN,
            GameStatus.PLAYER_TWO_WIN,
            GameStatus.DRAW,
            GameStatus.ABANDONED
        }

    @property
    def is_in_progress(self) -> bool:
        """Check if game is actively being played."""
        return self == GameStatus.IN_PROGRESS

    def __str__(self) -> str:
        return self.value