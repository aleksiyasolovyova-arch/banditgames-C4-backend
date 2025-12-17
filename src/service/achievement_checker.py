"""
Achievement Checker Service.
Evaluates player statistics and publishes achievement unlock events.

- No storage of unlocked achievements.
- Achievements are "edge-triggered" (only true exactly once).
"""
import logging
from typing import Dict, Any, List

from ..domain.achievement import AchievementType
from ..data_access import EventPublisher

logger = logging.getLogger(__name__)


class AchievementChecker:
    """
    Service that checks for newly unlocked achievements.

    - Does NOT track already unlocked achievements.
    - Each AchievementType rule must be designed to be true exactly once.
    """

    def __init__(self, event_publisher: EventPublisher):
        self._event_publisher = event_publisher

    def check_achievements(
        self,
        player_id: str,
        statistics: Dict[str, Any]
    ) -> List[AchievementType]:
        """
        Check which achievements are unlocked based on edge-triggered rules.

        Returns:
            List of achievements that are unlocked now (should be one-time).
        """
        unlocked_now: List[AchievementType] = []

        for achievement_type in AchievementType:
            if achievement_type.is_unlocked(statistics):
                unlocked_now.append(achievement_type)

                self._publish_achievement_unlocked(
                    player_id=player_id,
                    achievement_type=achievement_type
                )

        if unlocked_now:
            logger.info(
                f"Player {player_id} unlocked {len(unlocked_now)} achievements now: "
                f"{[a.value for a in unlocked_now]}"
            )

        return unlocked_now

    def _publish_achievement_unlocked(
        self,
        player_id: str,
        achievement_type: AchievementType,
    ) -> None:
        metadata = achievement_type.get_metadata()

        event_data = {
            "playerId": player_id,
            "achievementType": achievement_type.value,
            "title": metadata["title"],
            "description": metadata["description"]
        }

        self._event_publisher.publish_achievement_unlocked(event_data)

        logger.debug(
            f"Published achievement unlock event: {achievement_type.value} "
            f"for player {player_id}"
        )
