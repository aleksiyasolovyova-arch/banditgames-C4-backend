"""
Event Publisher interface following Dependency Inversion Principle.
Services depend on this interface, not concrete implementation.
"""
from typing import Protocol

from ..domain import Game, Move


class EventPublisher(Protocol):
    """
    Interface for event publishing.

    Following Dependency Inversion Principle:
    - High-level modules (services) depend on this abstraction
    - Low-level modules (RabbitMQ adapter) implement this interface

    This makes the system testable and allows swapping implementations.

    The game backend publishes domain events. External services
    (AI, logging, analytics) subscribe to these events.

    event set (3 events):
    1. game.created - Game exists
    2. move.made - Move happened
    3. game.finished - Game ended
    """

    def publish_game_created(self, game: Game) -> None:
        """Publish game created event."""
        ...

    def publish_move_made(self, game: Game, move: Move, pre_state: dict, post_state: dict) -> None:
        """
        Publish move made event.

        This is the event that external services listen to:
        - AI service: To know when it's their turn
        - Logging service: To record game data
        """
        ...

    def publish_game_finished(self, game: Game) -> None:
        """Publish game finished event."""
        ...