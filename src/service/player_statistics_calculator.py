"""
Real-Time Player Statistics Calculator.
Calculates statistics DURING gameplay (includes current game state).
"""
import logging
from typing import Dict, Any, List, Optional

from ..domain import Game, Move, Position
from ..data_access.game_repository import GameRepository

logger = logging.getLogger(__name__)


class PlayerStatisticsCalculator:
    """
    Service that calculates player statistics including current game state.
    Used for real-time achievement checking during gameplay.
    """

    def __init__(self, repository: GameRepository):
        """
        Initialize statistics calculator with game repository.

        Args:
            repository: Game repository for fetching player games
        """
        self._repository = repository

    def calculate_statistics(
        self,
        player_id: str,
        current_game: Optional[Game] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics for a player.
        Includes BOTH lifetime stats AND current game state.

        Returns:
            Dictionary containing:
                # Lifetime statistics
                - total_games_played: int
                - total_wins: int
                - total_losses: int
                - total_moves_made: int
                - fastest_win_seconds: float | None
                - current_win_streak: int
                - perfect_games: int
                - quick_wins: int
                - wins_under_60: int
                - wins_under_30: int

                # Current game statistics (if current_game provided)
                - current_game_moves: int
                - current_game_won: bool
                - current_game_finished: bool
                - win_pattern: str | None
                - winning_column: int | None
                - game_duration_seconds: float | None
        """
        lifetime_stats = self._calculate_lifetime_stats(player_id)

        if current_game:
            current_game_stats = self._calculate_current_game_stats(player_id, current_game)
            lifetime_stats.update(current_game_stats)

            lifetime_stats["total_moves_made"] = (
                lifetime_stats.get("total_moves_made", 0) +
                current_game_stats.get("current_game_moves", 0)
            )
        else:
            lifetime_stats.update({
                "current_game_moves": 0,
                "current_game_won": False,
                "current_game_finished": False,
                "win_pattern": None,
                "winning_column": None,
                "game_duration_seconds": None
            })

        return lifetime_stats

    def _calculate_lifetime_stats(self, player_id: str) -> Dict[str, Any]:
        # Fetch all games for player
        games = self._repository.get_games_by_player(
            player_id=player_id,
            limit=1000
        )

        finished_games = [g for g in games if g.phase == "FINISHED"]

        total_games = len(finished_games)
        wins = [g for g in finished_games if g.winner and g.winner.id == player_id]
        losses = [g for g in finished_games if g.winner and g.winner.id != player_id]

        total_wins = len(wins)
        total_losses = len(losses)

        total_moves_made = sum(
            len([m for m in g.moves if m.player_id == player_id])
            for g in finished_games
        )

        # Fastest win
        fastest_win_seconds = None
        if wins:
            win_durations = [g.get_duration_seconds() for g in wins]
            valid_durations = [d for d in win_durations if d is not None]
            if valid_durations:
                fastest_win_seconds = min(valid_durations)

        # Current win streak
        current_win_streak = self._calculate_current_win_streak(
            finished_games,
            player_id
        )

        # Perfect games (won with exactly 4 moves)
        perfect_games = sum(
            1 for g in wins
            if len([m for m in g.moves if m.player_id == player_id]) == 4
        )

        # Quick wins (won in under 10 moves)
        quick_wins = sum(
            1 for g in wins
            if len([m for m in g.moves if m.player_id == player_id]) < 10
        )

        # Speed wins (used for one-time unlock under Option A)
        wins_under_60 = 0
        wins_under_30 = 0
        for g in wins:
            d = g.get_duration_seconds()
            if d is None:
                continue
            if d <= 60.0:
                wins_under_60 += 1
            if d <= 30.0:
                wins_under_30 += 1

        statistics = {
            "total_games_played": total_games,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "total_moves_made": total_moves_made,
            "fastest_win_seconds": fastest_win_seconds,
            "current_win_streak": current_win_streak,
            "perfect_games": perfect_games,
            "quick_wins": quick_wins,
            "wins_under_60": wins_under_60,
            "wins_under_30": wins_under_30,
        }

        logger.debug(f"Calculated lifetime stats for player {player_id}: {statistics}")
        return statistics

    def _calculate_current_game_stats(self, player_id: str, game: Game) -> Dict[str, Any]:
        # Count moves made by this player in current game
        player_moves = [m for m in game.moves if m.player_id == player_id]
        current_game_moves = len(player_moves)

        current_game_finished = (game.phase == "FINISHED")

        # Check if player won this game
        current_game_won = (
            current_game_finished and
            game.winner is not None and
            game.winner.id == player_id
        )

        # Detect win pattern if player won (only if player's last move ended the game)
        win_pattern = None
        winning_column = None
        if current_game_won and game.moves:
            last_move = game.moves[-1]
            if last_move.player_id == player_id:
                win_pattern = self._detect_win_pattern(game.board, last_move)
                winning_column = last_move.column

        game_duration_seconds = game.get_duration_seconds()

        stats = {
            "current_game_moves": current_game_moves,
            "current_game_won": current_game_won,
            "current_game_finished": current_game_finished,
            "win_pattern": win_pattern,
            "winning_column": winning_column,
            "game_duration_seconds": game_duration_seconds
        }

        logger.debug(f"Calculated current game stats for player {player_id}: {stats}")
        return stats

    def _detect_win_pattern(self, board, last_move: Move) -> Optional[str]:
        """
        Detect the winning pattern (horizontal, vertical, or diagonal).
        """
        pos = last_move.landed_at
        token = last_move.token

        # Horizontal
        if self._check_direction(board, pos, token, 0, 1):
            return "horizontal"

        # Vertical
        if self._check_direction(board, pos, token, 1, 0):
            return "vertical"

        # Diagonal down-right
        if self._check_direction(board, pos, token, 1, 1):
            return "diagonal"

        # Diagonal down-left
        if self._check_direction(board, pos, token, 1, -1):
            return "diagonal"

        return None

    def _check_direction(
        self,
        board,
        pos: Position,
        token,
        delta_row: int,
        delta_col: int
    ) -> bool:
        """
        Check if there's a line of 4 in a specific direction.
        """
        count = 1

        # Forward direction
        current = pos.add(delta_row, delta_col)
        while current.is_valid(board.rows, board.cols):
            if board.get_cell(current) != token:
                break
            count += 1
            current = current.add(delta_row, delta_col)

        # Backward direction
        current = pos.add(-delta_row, -delta_col)
        while current.is_valid(board.rows, board.cols):
            if board.get_cell(current) != token:
                break
            count += 1
            current = current.add(-delta_row, -delta_col)

        return count >= 4

    def _calculate_current_win_streak(self, games: List[Game], player_id: str) -> int:
        """
        Calculate current win streak for player.
        """
        streak = 0
        sorted_games = sorted(games, key=lambda g: g.updated_at, reverse=True)

        for game in sorted_games:
            if game.winner and game.winner.id == player_id:
                streak += 1
            else:
                break

        return streak
