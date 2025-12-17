"""
Game Repository interface following Dependency Inversion Principle.
Services depend on this interface, not concrete implementations.
"""
from typing import Protocol, Optional, List

from ..domain import Game


class GameRepository(Protocol):
    """
    Repository interface for game persistence.

    Following Dependency Inversion Principle:
    - High-level modules (services) depend on this abstraction
    - Low-level modules (PostgreSQL, InMemory) implement this interface

    This allows swapping persistence mechanisms without changing business logic.
    """

    def save(self, game: Game) -> None:
        """
        Save or update a game.

        Args:
            game: Game domain aggregate to persist
        """
        ...

    def get(self, game_id: str) -> Optional[Game]:
        """
        Retrieve a game by ID.

        Args:
            game_id: Game identifier

        Returns:
            Game domain aggregate or None if not found
        """
        ...
