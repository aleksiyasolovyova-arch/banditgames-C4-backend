"""
Player Performance Manager for DDA tracking in backend.
WITH DYNAMIC IN-GAME DDA SUPPORT
"""

import logging
from typing import Dict, Optional, List
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

class PlayerPerformance:
    """Player performance tracking for DDA"""

    def __init__(self, window_size: int = 10):
        self.results = deque(maxlen=window_size)
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.total_games = 0
        self.total_wins = 0
        self.recent_move_times: List[int] = []  # Times in ms for moves in current game

    def add_result(self, won: bool):
        """Add game result"""
        self.results.append(1 if won else 0)
        self.total_games += 1

        if won:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.total_wins += 1
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0

        # Reset move times for next game
        self.recent_move_times = []

    def get_win_rate(self) -> float:
        """Calculate recent win rate"""
        if not self.results:
            return 0.5
        return sum(self.results) / len(self.results)

    def should_increase_difficulty(self) -> bool:
        """Check if difficulty should increase"""
        return (
            self.consecutive_wins >= 3 or
            self.get_win_rate() > 0.7
        )

    def should_decrease_difficulty(self) -> bool:
        """Check if difficulty should decrease"""
        return (
            self.consecutive_losses >= 3 or
            self.get_win_rate() < 0.3
        )


class PlayerPerformanceManager:
    """
    Manages player performance tracking for DDA.
    Backend-only version - no MCTS dependencies.
    NOW WITH DYNAMIC IN-GAME DDA SUPPORT!
    """

    def __init__(self):
        self.performance: Dict[str, PlayerPerformance] = {}  # player_id → performance
        self.player_mapping: Dict[str, str] = {}  # game_id → player_id

    def load_player_performance_from_db(self, player_id: str, db) -> PlayerPerformance:
        """Load player performance from database"""
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT consecutive_wins,
                               consecutive_losses,
                               recent_win_rate,
                               games_played,
                               games_won
                        FROM player_performance
                        WHERE player_id = %s
                        ORDER BY updated_at DESC LIMIT 1
                    """, (player_id,))

                    row = cur.fetchone()
                    if row:
                        perf = PlayerPerformance()
                        perf.consecutive_wins = row[0] or 0
                        perf.consecutive_losses = row[1] or 0
                        perf.total_games = row[3] or 0
                        perf.total_wins = row[4] or 0

                        # Restore recent results based on win rate
                        win_rate = row[2] or 0.5
                        recent_games = min(10, perf.total_games)
                        if recent_games > 0:
                            wins = int(win_rate * recent_games)
                            perf.results = deque(
                                [1] * wins + [0] * (recent_games - wins),
                                maxlen=10
                            )

                        print(f"Loaded performance for {player_id}: "
                              f"{perf.consecutive_wins}W / {perf.consecutive_losses}L streak")
                        return perf

        except Exception as e:
            print(f"Failed to load performance from DB: {e}")

        print(f"New player {player_id} - starting fresh")
        return PlayerPerformance()

    def register_player(self, game_id: str, player_id: str, db=None):
        """Register player for a game"""
        self.player_mapping[game_id] = player_id

        if player_id not in self.performance:
            if db:
                self.performance[player_id] = self.load_player_performance_from_db(player_id, db)
            else:
                self.performance[player_id] = PlayerPerformance()

    def update_performance(self, game_id: str, player_won: bool):
        """Update performance after game ends"""
        player_id = self.player_mapping.get(game_id)

        if not player_id:
            print(f" No player_id found for game {game_id}")
            return

        if player_id not in self.performance:
            self.performance[player_id] = PlayerPerformance()

        perf = self.performance[player_id]
        perf.add_result(player_won)

        print(f"Performance updated for player {player_id}: "
              f"{perf.consecutive_wins}W / {perf.consecutive_losses}L, "
              f"Win rate: {perf.get_win_rate():.2%}")

    def get_performance(self, player_id: str) -> Optional[PlayerPerformance]:
        """Get player performance"""
        return self.performance.get(player_id)


    #  DYNAMIC IN-GAME DDA METHODS
    def record_human_move_time(self, game_id: str, thinking_time_ms: Optional[int]):
        """
        Record a human player's move time during the game.
        This is called DURING gameplay to track in-game DDA.

        Args:
            game_id: Current game ID
            thinking_time_ms: Time taken for this move in milliseconds
        """
        player_id = self.player_mapping.get(game_id)
        if not player_id:
            return

        perf = self.performance.get(player_id)
        if not perf:
            return

        if thinking_time_ms is None:
            thinking_time_ms = 0

        perf.recent_move_times.append(thinking_time_ms)

        # Keep only last 5 moves for trend detection
        if len(perf.recent_move_times) > 5:
            perf.recent_move_times = perf.recent_move_times[-5:]

        logger.debug(f" Recorded move time for {player_id}: {thinking_time_ms}ms "
                    f"(Recent: {perf.recent_move_times})")

    def get_move_speed_trend(self, recent_move_times: List[int]) -> tuple[float, str]:
        """
        Analyze move speed trend to detect confidence changes.

        Returns:
            (avg_time, trend): avg time and trend direction
            - "accelerating": moves getting faster (gaining confidence)
            - "decelerating": moves getting slower (losing confidence)
            - "steady": no significant trend
        """
        if len(recent_move_times) < 3:
            return (0, "steady")

        avg_time = sum(recent_move_times) / len(recent_move_times)

        # Split into two halves to detect trend
        mid = len(recent_move_times) // 2
        first_half_avg = sum(recent_move_times[:mid]) / len(recent_move_times[:mid]) if mid > 0 else avg_time
        second_half_avg = sum(recent_move_times[mid:]) / (len(recent_move_times) - mid) if len(recent_move_times) > mid else avg_time

        # Threshold: 20% change = significant trend
        change_percent = abs(second_half_avg - first_half_avg) / max(first_half_avg, 1)

        if change_percent > 0.2:
            if second_half_avg < first_half_avg:
                trend = "accelerating"  # Getting faster = more confident
            else:
                trend = "decelerating"  # Getting slower = less confident
        else:
            trend = "steady"

        return (avg_time, trend)

    def get_in_game_adjustment(self, player_id: str) -> float:
        """
        Calculate DYNAMIC IN-GAME DDA adjustment based on current game performance.

        Called DURING gameplay to dynamically adjust AI time budget in real-time.
        The adjustment responds to:
        1. Cross-game performance (win/loss streaks)
        2. Current game move speed (confidence level)
        3. Move speed TREND (gaining/losing confidence)

        This creates a truly responsive system where DDA adjusts up/down as player
        confidence changes within a single game.

        Args:
            player_id: Player ID

        Returns:
            DDA multiplier (0.6 = 40% easier, 1.0 = normal, 1.5 = 50% harder)
        """
        perf = self.performance.get(player_id)
        if not perf:
            return 1.0

        adjustment = 1.0
        factors = []  # Track all factors for logging

        #  Factor 1: Cross-Game Winning/Losing Streaks
        if perf.consecutive_wins >= 3:
            # Player is on a winning streak - make it harder
            streak_bonus = 0.1 * min(perf.consecutive_wins - 2, 2)  # Max +0.2
            adjustment += streak_bonus
            factors.append(f" Winning streak {perf.consecutive_wins}: +{streak_bonus:.2f}x")

        elif perf.consecutive_losses >= 2:
            # Player is losing - make it easier
            loss_penalty = 0.1 * min(perf.consecutive_losses - 1, 2)  # Max -0.2
            adjustment -= loss_penalty
            factors.append(f" Losing streak {perf.consecutive_losses}: -{loss_penalty:.2f}x")

        #  Factor 2: Move Speed Trend (DYNAMIC!)
        if len(perf.recent_move_times) >= 3:
            avg_time, trend = self.get_move_speed_trend(perf.recent_move_times)

            # Base speed adjustment (current average)
            speed_adjustment = 0.0

            if avg_time < 500:
                # Currently fast = confident
                speed_adjustment = 0.15
                factors.append(f"Currently fast ({avg_time:.0f}ms): +{speed_adjustment:.2f}x")
            elif avg_time > 2000:
                # Currently slow = struggling
                speed_adjustment = -0.1
                factors.append(f" Currently slow ({avg_time:.0f}ms): {speed_adjustment:.2f}x")
            else:
                factors.append(f" Normal pace ({avg_time:.0f}ms): +0.00x")

            adjustment += speed_adjustment

            #  TREND ADJUSTMENT
            # This responds to changes in confidence within the current game
            if trend == "accelerating":
                # Moves getting faster = gaining confidence = increase difficulty
                trend_adjustment = 0.05
                adjustment += trend_adjustment
                factors.append(f" Accelerating trend: +{trend_adjustment:.2f}x (player getting confident)")

            elif trend == "decelerating":
                # Moves getting slower = losing confidence = decrease difficulty
                trend_adjustment = -0.05
                adjustment -= trend_adjustment
                factors.append(f" Decelerating trend: -{trend_adjustment:.2f}x (player losing confidence)")

            else:
                factors.append(f"Steady trend: +0.00x (consistent pace)")

        # Clamp adjustment between 0.6x and 1.5x
        original_adjustment = adjustment
        adjustment = max(0.6, min(1.5, adjustment))

        # Log all factors
        factors_str = " | ".join(factors)
        logger.info(f"In-game DDA: {adjustment:.2f}x "
                   f"(Streak: {perf.consecutive_wins}W/{perf.consecutive_losses}L, "
                   f"Moves: {len(perf.recent_move_times)}) | {factors_str}")

        if adjustment != original_adjustment:
            logger.info(f" Clamped {original_adjustment:.2f}x → {adjustment:.2f}x")

        return adjustment