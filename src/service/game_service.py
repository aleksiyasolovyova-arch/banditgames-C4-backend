import logging
import uuid

from ..domain import Game, Player
from data_access import EventPublisher
from data_access import InMemoryGameStore

logger = logging.getLogger(__name__)


class GameService:
    """
    Stateless business service orchestrating game lifecycle.
    """

    def __init__(self, store: InMemoryGameStore, event_publisher: EventPublisher):
        self._store = store
        self._event_publisher = event_publisher

    def create_game(
        self,
        player_one: Player,
        player_two: Player,
        rows: int = 6,
        cols: int = 7
    ) -> Game:
        game = Game(
            game_id=str(uuid.uuid4()),
            rows=rows,
            cols=cols,
            player_one=player_one,
            player_two=player_two
        )

        self._store.save(game)
        self._event_publisher.publish_game_created(game)

        logger.info(
            f"Created game {game.id}: "
            f"{player_one.name} vs {player_two.name}"
        )

        return game

    def get_game(self, game_id: str) -> Game:
        game = self._store.get(game_id)
        if not game:
            raise ValueError(f"Game not found: {game_id}")
        return game

    def abandon_game(self, game_id: str) -> Game:
        game = self.get_game(game_id)
        game.abandon()
        self._store.save(game)
        return game
