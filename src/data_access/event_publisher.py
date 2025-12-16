"""
Event Publisher interface following Dependency Inversion Principle.

Services depend on this interface, not concrete implementations.
"""
from typing import Protocol, Dict, Any, List

from ..domain import Game, Move


class EventPublisher(Protocol):
    """
    Interface for event publishing.

    Following Dependency Inversion Principle:
    - High-level modules (services) depend on this abstraction
    - Low-level modules (RabbitMQ adapter) implement this interface

    The game backend publishes domain events.
    External services (AI, logging, analytics) subscribe to these events.

    Event set:
    1. game.created   - Game exists
    2. move.made     - Move happened
    3. game.finished - Game ended
    """

    def publish_game_created(self, game: Game) -> None:
        """Publish game created event."""
        ...

    def publish_move_made(
        self,
        game: Game,
        move: Move,
        pre_state: Dict[str, Any],
        post_state: Dict[str, Any],
        legal_moves: List[int]
    ) -> None:
        """
        Publish move made event.

        Includes:
        - pre_state: state BEFORE the move (AI features / ML input)
        - post_state: state AFTER the move
        - legal_moves: available actions BEFORE the move
        - move.thinking_time_ms: player response time (inside Move)

        Consumers:
        - AI service: difficulty adaptation, decision-making
        - Logging service: dataset construction
        """
        ...

    def publish_game_finished(self, game: Game) -> None:
        """Publish game finished event."""
        ...

    def close(self) -> None:
        """Close publisher resources (connections, channels, etc.)."""
        ...
