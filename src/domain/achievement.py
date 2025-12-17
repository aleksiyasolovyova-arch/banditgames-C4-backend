"""
Achievement enum for Connect4 Backend.
Achievements checked in REAL-TIME during gameplay (after each move).

- No storage of unlocked achievements.
- Each rule must be edge-triggered (true exactly once).
"""
from enum import Enum
from typing import Dict, Any


class AchievementType(str, Enum):
    # Instant achievements
    FIRST_MOVE = "FIRST_MOVE"
    DIAGONAL_WINNER = "DIAGONAL_WINNER"
    VERTICAL_WINNER = "VERTICAL_WINNER"
    HORIZONTAL_WINNER = "HORIZONTAL_WINNER"
    CENTER_COLUMN_WIN = "CENTER_COLUMN_WIN"

    # Cumulative achievements
    FIRST_GAME = "FIRST_GAME"
    VETERAN_PLAYER = "VETERAN_PLAYER"
    CENTURION = "CENTURION"

    FIRST_VICTORY = "FIRST_VICTORY"
    WINNING_STREAK = "WINNING_STREAK"
    CHAMPION = "CHAMPION"

    SPEED_DEMON = "SPEED_DEMON"
    LIGHTNING_FAST = "LIGHTNING_FAST"

    PERFECT_GAME = "PERFECT_GAME"
    QUICK_WIN = "QUICK_WIN"

    def is_unlocked(self, statistics: Dict[str, Any]) -> bool:
        # Convenience flags
        current_game_won = statistics.get("current_game_won", False)
        current_game_finished = statistics.get("current_game_finished", False)

        # INSTANT ACHIEVEMENTS (edge-triggered)

        if self == AchievementType.FIRST_MOVE:
            # Unlocked exactly on the first move ever
            return statistics.get("total_moves_made", 0) == 1

        if self == AchievementType.DIAGONAL_WINNER:
            return current_game_won and statistics.get("win_pattern") == "diagonal"

        if self == AchievementType.VERTICAL_WINNER:
            return current_game_won and statistics.get("win_pattern") == "vertical"

        if self == AchievementType.HORIZONTAL_WINNER:
            return current_game_won and statistics.get("win_pattern") == "horizontal"

        if self == AchievementType.CENTER_COLUMN_WIN:
            winning_col = statistics.get("winning_column")
            return current_game_won and winning_col == 3

        # CUMULATIVE ACHIEVEMENTS (edge-triggered)

        if self == AchievementType.FIRST_GAME:
            return current_game_finished and statistics.get("total_games_played", 0) == 1

        if self == AchievementType.VETERAN_PLAYER:
            return current_game_finished and statistics.get("total_games_played", 0) == 50

        if self == AchievementType.CENTURION:
            return current_game_finished and statistics.get("total_games_played", 0) == 100

        if self == AchievementType.FIRST_VICTORY:
            return current_game_won and statistics.get("total_wins", 0) == 1

        if self == AchievementType.WINNING_STREAK:
            return current_game_won and statistics.get("current_win_streak", 0) == 5

        if self == AchievementType.CHAMPION:
            return current_game_won and statistics.get("total_wins", 0) == 25

        if self == AchievementType.SPEED_DEMON:
            duration = statistics.get("game_duration_seconds")
            return (
                current_game_won and
                duration is not None and
                duration <= 60.0 and
                statistics.get("wins_under_60", 0) == 1
            )

        if self == AchievementType.LIGHTNING_FAST:
            duration = statistics.get("game_duration_seconds")
            return (
                current_game_won and
                duration is not None and
                duration <= 30.0 and
                statistics.get("wins_under_30", 0) == 1
            )

        if self == AchievementType.PERFECT_GAME:
            return (
                current_game_won and
                statistics.get("current_game_moves", 0) == 4 and
                statistics.get("perfect_games", 0) == 1
            )

        if self == AchievementType.QUICK_WIN:
            return (
                current_game_won and
                statistics.get("current_game_moves", 0) < 10 and
                statistics.get("quick_wins", 0) == 1
            )

        return False

    def get_metadata(self) -> Dict[str, str]:

        metadata = {
            AchievementType.FIRST_MOVE: {
                "title": "First Move",
                "description": "Make your first move ever"
            },
            AchievementType.DIAGONAL_WINNER: {
                "title": "Diagonal Master",
                "description": "Win with a diagonal line"
            },
            AchievementType.VERTICAL_WINNER: {
                "title": "Stack 'Em Up",
                "description": "Win with a vertical line"
            },
            AchievementType.HORIZONTAL_WINNER: {
                "title": "Horizontal Hero",
                "description": "Win with a horizontal line"
            },
            AchievementType.CENTER_COLUMN_WIN: {
                "title": "Center Stage",
                "description": "Win by placing the winning piece in the center column"
            },
            AchievementType.FIRST_GAME: {
                "title": "First Steps",
                "description": "Play your first game"
            },
            AchievementType.VETERAN_PLAYER: {
                "title": "Veteran Player",
                "description": "Play 50 games"
            },
            AchievementType.CENTURION: {
                "title": "Centurion",
                "description": "Play 100 games"
            },
            AchievementType.FIRST_VICTORY: {
                "title": "First Victory",
                "description": "Win your first game"
            },
            AchievementType.WINNING_STREAK: {
                "title": "On Fire!",
                "description": "Win 5 games in a row"
            },
            AchievementType.CHAMPION: {
                "title": "Champion",
                "description": "Win 25 games"
            },
            AchievementType.SPEED_DEMON: {
                "title": "Speed Demon",
                "description": "Win a game in under 60 seconds"
            },
            AchievementType.LIGHTNING_FAST: {
                "title": "Lightning Fast",
                "description": "Win a game in under 30 seconds"
            },
            AchievementType.PERFECT_GAME: {
                "title": "Perfect Game",
                "description": "Win with exactly 4 moves"
            },
            AchievementType.QUICK_WIN: {
                "title": "Quick Thinker",
                "description": "Win in under 10 moves"
            }
        }

        return metadata.get(self, {
            "title": self.value,
            "description": "Unknown achievement",
        })
