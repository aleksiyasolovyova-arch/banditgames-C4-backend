"""
Move Service with Real-Time Achievement Checking.
Checks achievements AFTER EVERY MOVE, not just when games finish.

- No storage of unlocked achievements.
- Achievement rules are edge-triggered to fire only once.
"""
import logging
from typing import Any, Dict, List

from ..domain import Game, Move
from ..data_access import EventPublisher
from ..data_access.game_repository import GameRepository
from .player_statistics_calculator import PlayerStatisticsCalculator
from .achievement_checker import AchievementChecker

logger = logging.getLogger(__name__)


class MoveService:
    def __init__(
        self,
        repository: GameRepository,
        event_publisher: EventPublisher,
        stats_calculator: PlayerStatisticsCalculator,
        achievement_checker: AchievementChecker
    ):
        self._repository = repository
        self._event_publisher = event_publisher
        self._stats_calculator = stats_calculator
        self._achievement_checker = achievement_checker

    def execute_move(self, game_id: str, player_id: str, column: int) -> Move:
        game: Game | None = self._repository.get(game_id)
        if not game:
            raise ValueError(f"Game not found: {game_id}")

        # PRE state (before the move)
        pre_state: Dict[str, Any] = game.get_state_snapshot()

        # Legal moves before the move (AI features)
        legal_moves: List[int] = list(game.get_available_columns())

        # Execute move (domain computes thinking_time_ms)
        move = game.make_move(player_id, column)

        # Save game state
        self._repository.save(game)

        # POST state (after the move)
        post_state: Dict[str, Any] = game.get_state_snapshot()

        # Publish move event
        self._event_publisher.publish_move_made(
            game, move, pre_state, post_state, legal_moves
        )

        logger.info(
            f"Move executed in game {game.id}: player={player_id} column={column}"
        )

        # Check achievements AFTER EVERY MOVE (edge-triggered rules)
        self._check_achievements_for_player(player_id, game)

        # If game finished, also publish game finished event
        if game.phase == "FINISHED":
            self._event_publisher.publish_game_finished(game)
            logger.info(f"Game {game.id} finished")

            # Check achievements for the OTHER player too (they didn't move but game ended)
            other_player = (
                game.player_two if player_id == game.player_one.id
                else game.player_one
            )
            self._check_achievements_for_player(other_player.id, game)

        return move

    def _check_achievements_for_player(
        self,
        player_id: str,
        current_game: Game
    ) -> None:
        """
        Check achievements for a player in real-time.
        Includes both lifetime stats and current game state.
        """
        try:
            statistics = self._stats_calculator.calculate_statistics(
                player_id=player_id,
                current_game=current_game
            )

            #  no 'already unlocked' set; rules must be edge-triggered
            newly_unlocked = self._achievement_checker.check_achievements(
                player_id=player_id,
                statistics=statistics
            )

            if newly_unlocked:
                logger.info(
                    f"Player {player_id} unlocked {len(newly_unlocked)} achievements: "
                    f"{[a.value for a in newly_unlocked]}"
                )

        except Exception as e:
            # Don't fail the move if achievement checking fails
            logger.error(
                f"Failed to check achievements for player {player_id}: {e}",
                exc_info=True
            )


