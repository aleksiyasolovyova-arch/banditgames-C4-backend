"""
Player value object for Connect Four.
Immutable representation of a game player.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Player:
    """
    Immutable value object representing a player.

    Following DDD principles:
    - Frozen dataclass = immutability
    - Contains identity and behavior related to player

     This is just player identity. Whether a player is controlled
    by AI is determined by external services, not stored here.
    """
    id: str
    # TODO do we need name for the front end or?
    name: str

    def __str__(self) -> str:
        return f"{self.name}"

    def to_dict(self) -> dict:
        """Serialize player to dictionary."""
        return {
            "id": self.id,
            "name": self.name
        }