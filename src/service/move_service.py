"""
Move Service - handles move execution and coordination.

Business layer:
- Stateless orchestration
- Delegates validation/execution to the domain Game aggregate
- Persists runtime state in InMemoryGameStore
- Publishes events for external services (AI, logging)
"""
import logging

from ..domain import Game, Move
from ..adapter.event_publisher import EventPublisher
from ..adapter.in_memory_game_store import InMemoryGameStore

logger = logging.getLogger(__name__)


class MoveService:
    """
    Service for handling moves in games.
    """

    def __init__(self, store: InMemoryGameStore, event_publisher: EventPublisher):
        self._store = store
        self._event_publisher = event_publisher

    def execute_move(self, game_id: str, player_id: str, column: int) -> Move:
        """
        Execute a move:
        1) Load game (runtime store)
        2) Domain enforces rules + updates state
        3) Save updated game
        4) Publish events

        Returns:
            The executed Move
        """
        game: Game | None = self._store.get(game_id)
        if not game:
            raise ValueError(f"Game not found: {game_id}")

        # Domain handles ALL validation and execution
        move = game.make_move(player_id, column)

        # Save updated state (runtime only)
        self._store.save(game)

        # Publish move event for external services (AI, logging)
        self._event_publisher.publish_move_made(game, move)

        logger.info(f"Move executed in game {game.id}: player={player_id} column={column}")

        # Publish finished if terminal
        if game.status.is_finished:
            self._event_publisher.publish_game_finished(game)
            logger.info(f"Game {game.id} finished with status {game.status}")

        return move
