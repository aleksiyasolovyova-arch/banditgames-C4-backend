"""
Move value object representing a single game move.
"""
from dataclasses import dataclass
from datetime import datetime

from .position import Position
from .token import Token


@dataclass(frozen=True)
class Move:
    """
    Immutable value object representing a move made in the game.

    Contains all information needed to:
    - Reconstruct game history
    - Display move sequence
    - Analyze gameplay
    """
    move_index: int
    column: int
    landed_at: Position
    token: Token
    player_id: str
    timestamp: datetime

    def __str__(self) -> str:
        return f"Move #{self.move_index}: Player {self.player_id} -> Col {self.column}"

    def to_dict(self) -> dict:
        """Serialize move to dictionary."""
        return {
            "moveIndex": self.move_index,
            "column": self.column,
            "landedAt": {"row": self.landed_at.row, "col": self.landed_at.col},
            "token": self.token.value,
            "playerId": self.player_id,
            "timestamp": self.timestamp.isoformat()
        }