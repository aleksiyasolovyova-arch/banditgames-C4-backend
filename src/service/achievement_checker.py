"""
Achievement Checker Service.
Evaluates player statistics and publishes achievement unlock events.
Integrates with database to prevent duplicate achievement unlocks.
"""
import logging
from typing import Dict, Any, List

from ..domain.achievement import AchievementType
from ..data_access import EventPublisher

logger = logging.getLogger(__name__)


class AchievementChecker:
    """
    Service that checks for newly unlocked achievements.

    - Checks database to avoid duplicate unlocks
    - Each AchievementType rule is designed to be true exactly once
    - Only publishes events for newly unlocked achievements
    """

    def __init__(self, event_publisher: EventPublisher, repository=None):
        """
        Initialize achievement checker.

        Args:
            event_publisher: Event publisher for achievement events
            repository: Game repository for checking already-unlocked achievements
        """
        self._event_publisher = event_publisher
        self._repository = repository

    def check_achievements(
        self,
        player_id: str,
        statistics: Dict[str, Any],
        game_id: str = None
    ) -> List[AchievementType]:
        """
        Check which achievements are unlocked based on edge-triggered rules.
        Only returns achievements that were newly unlocked (not previously recorded).

        Args:
            player_id: Player UUID string
            statistics: Player statistics dictionary
            game_id: Optional game UUID that triggered the check

        Returns:
            List of achievements that were newly unlocked
        """
        unlocked_now: List[AchievementType] = []

        for achievement_type in AchievementType:
            # Check if achievement condition is met
            if not achievement_type.is_unlocked(statistics):
                continue

            # Check if achievement already unlocked (if repository available)
            if self._repository:
                if self._repository.is_achievement_unlocked(player_id, achievement_type.value):
                    logger.debug(
                        f"Achievement {achievement_type.value} already unlocked for player {player_id}"
                    )
                    continue

                # Record achievement unlock in database
                was_recorded = self._repository.record_achievement_unlock(
                    player_id=player_id,
                    achievement_type=achievement_type.value,
                    game_id=game_id
                )

                if not was_recorded:
                    # Another process already recorded this achievement (race condition)
                    logger.debug(
                        f"Achievement {achievement_type.value} was already recorded "
                        f"for player {player_id} (concurrent unlock)"
                    )
                    continue

            # Achievement is newly unlocked - publish event
            unlocked_now.append(achievement_type)
            self._publish_achievement_unlocked(
                player_id=player_id,
                achievement_type=achievement_type,
                game_id=game_id
            )

        if unlocked_now:
            logger.info(
                f"Player {player_id} unlocked {len(unlocked_now)} new achievements: "
                f"{[a.value for a in unlocked_now]}"
            )

        return unlocked_now

    def _publish_achievement_unlocked(
        self,
        player_id: str,
        achievement_type: AchievementType,
        game_id: str = None
    ) -> None:
        """
        Publish achievement unlocked event.

        Args:
            player_id: Player UUID string
            achievement_type: Achievement that was unlocked
            game_id: Optional game UUID that triggered the unlock
        """
        metadata = achievement_type.get_metadata()

        event_data = {
            "playerId": player_id,
            "achievementType": achievement_type.value,
            "title": metadata["title"],
            "description": metadata["description"],
            "gameId": game_id
        }

        self._event_publisher.publish_achievement_unlocked(event_data)

        logger.debug(
            f"Published achievement unlock event: {achievement_type.value} "
            f"for player {player_id}"
        )
