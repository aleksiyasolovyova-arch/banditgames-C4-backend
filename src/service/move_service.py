import logging
from typing import Any, Dict, List

from ..domain import Game, Move
from ..data_access import EventPublisher
from ..data_access.in_memory_game_store import InMemoryGameStore

logger = logging.getLogger(__name__)


class MoveService:
    def __init__(self, store: InMemoryGameStore, event_publisher: EventPublisher):
        self._store = store
        self._event_publisher = event_publisher

    def execute_move(self, game_id: str, player_id: str, column: int) -> Move:
        game: Game | None = self._store.get(game_id)
        if not game:
            raise ValueError(f"Game not found: {game_id}")

        # PRE state (before the move)
        pre_state: Dict[str, Any] = game.get_state_snapshot()

        # NEW: legal moves before the move (AI features)
        legal_moves: List[int] = list(game.get_available_columns())

        # Execute move (domain computes thinking_time_ms)
        move = game.make_move(player_id, column)

        self._store.save(game)

        # POST state (after the move)
        post_state: Dict[str, Any] = game.get_state_snapshot()

        # Publish move event with pre/post + legal moves
        self._event_publisher.publish_move_made(game, move, pre_state, post_state, legal_moves)

        logger.info(f"Move executed in game {game.id}: player={player_id} column={column}")

        if game.status.is_finished:
            self._event_publisher.publish_game_finished(game)
            logger.info(f"Game {game.id} finished with status {game.status}")

        return move


