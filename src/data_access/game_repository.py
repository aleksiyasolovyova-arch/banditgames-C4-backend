"""
Game Repository interface following Dependency Inversion Principle.
Services depend on this interface, not concrete implementations.
"""
from typing import Protocol, Optional, List

from ..domain import Game, Player


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

    def get_games_by_player(
        self,
        player_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Game]:
        """
        Get all games involving a specific player.

        Args:
            player_id: Player identifier
            limit: Maximum number of games to return
            offset: Number of games to skip

        Returns:
            List of Game domain aggregates
        """
        ...

    def ensure_player_exists(self, player: Player) -> None:
        """
        Ensure a player exists in the database.
        Creates player if not exists, updates if exists.

        Args:
            player: Domain Player value object
        """
        ...

    def get_player(self, player_id: str) -> Optional[Player]:
        """
        Retrieve a player by ID.

        Args:
            player_id: Player identifier (UUID string)

        Returns:
            Player domain object or None if not found
        """
        ...

    def record_achievement_unlock(
        self,
        player_id: str,
        achievement_type: str,
        game_id: str = None
    ) -> bool:
        """
        Record an achievement unlock for a player.
        Returns True if successfully recorded, False if already unlocked.

        Args:
            player_id: Player UUID string
            achievement_type: Achievement type string
            game_id: Optional game UUID string that triggered the achievement

        Returns:
            True if achievement was newly recorded, False if already existed
        """
        ...

    def is_achievement_unlocked(self, player_id: str, achievement_type: str) -> bool:
        """
        Check if a player has already unlocked a specific achievement.

        Args:
            player_id: Player UUID string
            achievement_type: Achievement type string

        Returns:
            True if achievement is unlocked, False otherwise
        """
        ...

    def get_player_achievements(self, player_id: str) -> List[dict]:
        """
        Get all achievements unlocked by a player.

        Args:
            player_id: Player UUID string

        Returns:
            List of achievement dictionaries
        """
        ...
