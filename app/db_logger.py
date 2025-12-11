"""
PostgreSQL Database Logger for Connect4 Gameplay.

Logs game data for analytics, AI training, and replay.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import ThreadedConnectionPool

from app.schemas import (
    GameConfig, GameState, MoveInfo, Player, PlayerType,
    GameStatus, SkillLevel, MCTSStatistics, TransitionLogEntry
)

logger = logging.getLogger(__name__)


class DatabaseLogger:

    def __init__(
            self,
            host: str = None,
            port: int = None,
            database: str = None,
            user: str = None,
            password: str = None,
            min_connections: int = 2,
            max_connections: int = 10
    ):
        # Get configuration from environment variables with defaults
        self.host = host or os.getenv('POSTGRES_HOST', 'platform-postgres')
        self.port = port or int(os.getenv('POSTGRES_PORT', 5432))
        self.database = database or os.getenv('POSTGRES_DB', 'postgres')
        self.user = user or os.getenv('POSTGRES_USER', 'user')
        self.password = password or os.getenv('POSTGRES_PASSWORD', 'password')

        logger.info(f"Database config: host={self.host}, port={self.port}, database={self.database}, user={self.user}")

        self.pool: Optional[ThreadedConnectionPool] = None
        self.initialize_pool(min_connections, max_connections)

    def initialize_pool(self, min_conn: int, max_conn: int):
        """Initialize connection pool"""
        try:
            self.pool = ThreadedConnectionPool(
                min_conn,
                max_conn,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                options="-c search_path=connect4,public"
            )
            logger.info(f"Database pool initialized: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            self.pool = None

    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic return"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")

        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.pool.putconn(conn)

    def close(self):
        """Close all connections"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database pool closed")

    # PLAYER MANAGEMENT
    def get_or_create_player(
            self,
            player_type: PlayerType,
            skill_level: Optional[SkillLevel] = None,
            display_name: Optional[str] = None
    ) -> str:
        """Get or create a player record, return player_id"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try to find existing player
                cur.execute("""
                            SELECT player_id
                            FROM players
                            WHERE player_type = %s
                              AND skill_level IS NOT DISTINCT
                            FROM %s
                                LIMIT 1
                            """, (player_type.value, skill_level.value if skill_level else None))

                result = cur.fetchone()
                if result:
                    return str(result['player_id'])

                # Create new player
                player_id = str(uuid.uuid4())
                cur.execute("""
                            INSERT INTO players (player_id, player_type, skill_level, display_name)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (player_id, player_type.value, skill_level.value if skill_level else None, display_name))

                return player_id

    # =========================================================================
    # GAME LOGGING
    # =========================================================================

    def log_game_created(self, game_id: str, config: GameConfig) -> None:
        """Log a new game creation"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get or create player IDs
                player1_id = self.get_or_create_player(config.player1_type, config.player1_skill_level)
                player2_id = self.get_or_create_player(config.player2_type, config.player2_skill_level)

                cur.execute("""
                            INSERT INTO games (game_id, player1_id, player2_id,
                                               player1_type, player2_type,
                                               player1_skill_level, player2_skill_level,
                                               rows, cols, connect,
                                               empty_token, player1_token, player2_token,
                                               starting_player, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                game_id, player1_id, player2_id,
                                config.player1_type.value, config.player2_type.value,
                                config.player1_skill_level.value if config.player1_skill_level else None,
                                config.player2_skill_level.value if config.player2_skill_level else None,
                                config.rows, config.cols, config.connect,
                                config.empty_token, config.player1_token, config.player2_token,
                                config.starting_player.value, GameStatus.IN_PROGRESS.value
                            ))

                logger.info(f"Logged game creation: {game_id}")

    def log_game_started(self, game_id: str) -> None:
        """Log game start time"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            UPDATE games
                            SET started_at = CURRENT_TIMESTAMP
                            WHERE game_id = %s
                            """, (game_id,))

    def log_game_ended(
            self,
            game_id: str,
            status: GameStatus,
            winner: Optional[Player],
            total_moves: int,
            final_board: List[List[str]],
            final_utilities: Dict[Player, float]
    ) -> None:
        """Log game completion"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            UPDATE games
                            SET status           = %s,
                                winner           = %s,
                                total_moves      = %s,
                                final_board      = %s,
                                final_utilities  = %s,
                                ended_at         = CURRENT_TIMESTAMP,
                                duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))
                            WHERE game_id = %s
                            """, (
                                status.value,
                                winner.value if winner else None,
                                total_moves,
                                Json(final_board),
                                Json({k.value: v for k, v in final_utilities.items()}),
                                game_id
                            ))

                logger.info(f"Logged game end: {game_id} ({status.value})")

    # =========================================================================
    # MOVE & STATE LOGGING
    # =========================================================================

    def log_transition(self, entry: TransitionLogEntry) -> str:
        """Log a game state transition (move)"""
        move_id = str(uuid.uuid4())

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Log the move
                cur.execute("""
                            INSERT INTO moves (move_id, game_id, move_index, player,
                                               column_played, row_placed,
                                               board_before, board_after,
                                               utility_before, utility_after,
                                               thinking_time_ms, move_timestamp)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                move_id,
                                entry.game_id,
                                entry.move_index,
                                entry.player.value,
                                entry.action,
                                entry.next_state.last_move.row if entry.next_state.last_move else None,
                                Json(entry.prev_state.board),
                                Json(entry.next_state.board),
                                Json({k.value: v for k, v in entry.utility_before.items()}),
                                Json({k.value: v for k, v in entry.utility_after.items()}),
                                entry.thinking_time_ms,
                                entry.timestamp
                            ))

                # Log game state
                state_id = self.log_game_state(cur, entry.next_state)

                # Log MCTS statistics if present
                if entry.mcts_stats:
                    self.log_mcts_stats(cur, move_id, entry.game_id, entry.move_index, entry.mcts_stats)

        return move_id

    def log_game_state(self, cur, state: GameState) -> str:
        """Log a game state snapshot"""
        state_id = str(uuid.uuid4())

        # Get utility values for each player
        utility_p1 = state.utilities.get(Player.PLAYER1, 0.0)
        utility_p2 = state.utilities.get(Player.PLAYER2, 0.0)

        cur.execute("""
                    INSERT INTO game_states (state_id, game_id, move_index,
                                             board, current_player, status, legal_actions,
                                             state_hash, utility_player1, utility_player2)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (game_id, move_index) DO NOTHING
                    """, (
                        state_id,
                        state.game_id,
                        state.turn_index,
                        Json(state.board),
                        state.current_player.value,
                        state.status.value,
                        Json(state.legal_actions),
                        state.state_hash or state.compute_state_hash(),
                        utility_p1,
                        utility_p2
                    ))

        return state_id

    def log_mcts_stats(
            self,
            cur,
            move_id: str,
            game_id: str,
            move_index: int,
            stats: MCTSStatistics
    ) -> None:
        """Log MCTS search statistics"""
        cur.execute("""
                    INSERT INTO mcts_statistics (stat_id, move_id, game_id, move_index,
                                                 skill_level, time_limit_seconds, actual_search_time_seconds,
                                                 num_rollouts, best_move, visit_counts, q_values,
                                                 time_adjustment_factor, exploration_constant)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(uuid.uuid4()),
                        move_id,
                        game_id,
                        move_index,
                        stats.skill_level,
                        stats.time_limit_seconds,
                        stats.actual_search_time_seconds,
                        stats.num_rollouts,
                        stats.best_move,
                        Json({str(ms.column): ms.visit_count for ms in stats.move_stats}),
                        Json({str(ms.column): ms.q_value for ms in stats.move_stats}),
                        stats.time_adjustment_factor,
                        stats.exploration_constant
                    ))


    # PLAYER PERFORMANCE (FOR DDA)

    def update_player_performance(
            self,
            player_id: str,
            game_id: str,
            won: bool,
            consecutive_wins: int,
            consecutive_losses: int,
            recent_win_rate: float,
            opponent_skill: str = None
    ) -> None:
        """Update player performance after a game"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Check if record exists for this player
                cur.execute("""
                            SELECT performance_id, games_played, games_won, games_lost, games_drawn
                            FROM player_performance
                            WHERE player_id = %s
                            ORDER BY updated_at DESC LIMIT 1
                            """, (player_id,))

                existing = cur.fetchone()

                if existing:
                    # Update existing record
                    perf_id, games_played, games_won, games_lost, games_drawn = existing

                    # Increment counts
                    games_played += 1
                    if won:
                        games_won += 1
                    else:
                        games_lost += 1

                    cur.execute("""
                                UPDATE player_performance
                                SET games_played           = %s,
                                    games_won              = %s,
                                    games_lost             = %s,
                                    consecutive_wins       = %s,
                                    consecutive_losses     = %s,
                                    recent_win_rate        = %s,
                                    current_opponent_skill = %s,
                                    updated_at             = CURRENT_TIMESTAMP
                                WHERE performance_id = %s
                                """, (
                                    games_played,
                                    games_won,
                                    games_lost,
                                    consecutive_wins,
                                    consecutive_losses,
                                    recent_win_rate,
                                    opponent_skill,
                                    perf_id
                                ))

                    logger.info(f"Updated performance for player {player_id}: "
                                f"{games_played} games, {consecutive_wins}W/{consecutive_losses}L streak")
                else:
                    # Create new record
                    cur.execute("""
                                INSERT INTO player_performance (performance_id, player_id, game_id,
                                                                games_played, games_won, games_lost, games_drawn,
                                                                consecutive_wins, consecutive_losses,
                                                                recent_win_rate, current_opponent_skill)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    str(uuid.uuid4()),
                                    player_id,
                                    game_id,
                                    1,  # games_played
                                    1 if won else 0,  # games_won
                                    0 if won else 1,  # games_lost
                                    0,  # games_drawn
                                    consecutive_wins,
                                    consecutive_losses,
                                    recent_win_rate,
                                    opponent_skill
                                ))

                    logger.info(f"Created performance record for player {player_id}: "
                                f"{'Win' if won else 'Loss'}")

    # SELF-PLAY SESSION LOGGING
    def log_self_play_session_start(
            self,
            session_id: str,
            agent1_skill: str,
            agent2_skill: str,
            noise_level: float = 0.0,
            temperature: float = 0.0
    ) -> None:
        """Log start of a self-play session"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO self_play_sessions (session_id, agent1_skill, agent2_skill,
                                                            noise_level, randomness_temperature)
                            VALUES (%s, %s, %s, %s, %s)
                            """, (session_id, agent1_skill, agent2_skill, noise_level, temperature))

    def update_self_play_session(
            self,
            session_id: str,
            total_games: int,
            agent1_wins: int,
            agent2_wins: int,
            draws: int
    ) -> None:
        """Update self-play session progress"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            UPDATE self_play_sessions
                            SET total_games = %s,
                                agent1_wins = %s,
                                agent2_wins = %s,
                                draws       = %s
                            WHERE session_id = %s
                            """, (total_games, agent1_wins, agent2_wins, draws, session_id))

    def log_self_play_session_end(
            self,
            session_id: str,
            parquet_path: Optional[str] = None,
            dvc_version: Optional[str] = None
    ) -> None:
        """Log end of a self-play session"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            UPDATE self_play_sessions
                            SET ended_at            = CURRENT_TIMESTAMP,
                                exported_to_parquet = %s,
                                parquet_file_path   = %s,
                                dvc_version         = %s
                            WHERE session_id = %s
                            """, (parquet_path is not None, parquet_path, dvc_version, session_id))

    # DATASET EXPORT LOGGING
    def log_dataset_export(
            self,
            export_id: str,
            version: str,
            num_games: int,
            num_moves: int,
            file_path: str,
            file_size_bytes: int,
            checksum: str,
            skill_levels: List[str],
            date_range_start: Optional[str] = None,
            date_range_end: Optional[str] = None
    ) -> None:
        """Log a dataset export"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO dataset_exports (export_id, version, num_games, num_moves,
                                                         file_path, file_size_bytes, checksum,
                                                         skill_levels_included, date_range_start, date_range_end)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                export_id, version, num_games, num_moves,
                                file_path, file_size_bytes, checksum,
                                Json(skill_levels), date_range_start, date_range_end
                            ))

    def update_dataset_export_dvc(
            self,
            export_id: str,
            dvc_tracked: bool,
            dvc_file_path: Optional[str] = None,
            minio_bucket: Optional[str] = None,
            minio_key: Optional[str] = None
    ) -> None:
        """Update dataset export with DVC tracking info"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            UPDATE dataset_exports
                            SET dvc_tracked   = %s,
                                dvc_file_path = %s,
                                minio_bucket  = %s,
                                minio_key     = %s
                            WHERE export_id = %s
                            """, (dvc_tracked, dvc_file_path, minio_bucket, minio_key, export_id))

    # DATA RETRIEVAL
    def get_game_replay(self, game_id: str) -> Optional[Dict]:
        """Get complete game data for replay"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get game info
                cur.execute("SELECT * FROM games WHERE game_id = %s", (game_id,))
                game = cur.fetchone()

                if not game:
                    return None

                # Get all moves
                cur.execute("""
                            SELECT *
                            FROM moves
                            WHERE game_id = %s
                            ORDER BY move_index
                            """, (game_id,))
                moves = cur.fetchall()

                # Get MCTS stats for each move
                cur.execute("""
                            SELECT *
                            FROM mcts_statistics
                            WHERE game_id = %s
                            ORDER BY move_index
                            """, (game_id,))
                mcts_stats = {s['move_index']: dict(s) for s in cur.fetchall()}

                return {
                    'game': dict(game),
                    'moves': [dict(m) for m in moves],
                    'mcts_stats': mcts_stats
                }

    def get_training_data(
            self,
            limit: Optional[int] = None,
            skill_levels: Optional[List[str]] = None,
            game_status: Optional[List[str]] = None
    ) -> List[Dict]:
        """Get training data for ML models"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM training_data WHERE 1=1"
                params = []

                if skill_levels:
                    query += " AND (player1_skill_level = ANY(%s) OR player2_skill_level = ANY(%s))"
                    params.extend([skill_levels, skill_levels])

                query += " ORDER BY game_id, move_index"

                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]


# SINGLETON INSTANCE

db_logger: Optional[DatabaseLogger] = None


def get_db_logger() -> Optional[DatabaseLogger]:
    """Get or create the database logger singleton"""
    global db_logger
    if db_logger is None:
        try:
            db_logger = DatabaseLogger()
            if db_logger.pool is None:
                logger.warning("Database logger created but pool not initialized")
                return None
        except Exception as e:
            logger.error(f"Failed to create database logger: {e}")
            return None
    return db_logger


def close_db_logger():
    """Close the database logger"""
    global db_logger
    if db_logger:
        db_logger.close()
        db_logger = None


# =============================================================================
# ADD THIS METHOD TO db_logger.py (DatabaseLogger class)
# =============================================================================

def log_oracle_analysis(
        self,
        game_id: str,
        move_index: int,
        state_hash: str,
        board_state: list,
        current_player: str,
        best_move: int,
        move_ranking: List[int],
        visit_counts: Dict[int, int],
        q_values: Dict[int, float],
        probabilities: Dict[int, float],
        num_rollouts: int,
        search_time: float,
        exploration_constant: float = 0.5,
        actual_move: int = None,
        move_id: str = None
) -> str:
    """
    Log oracle analysis for a board position.

    Args:
        game_id: Game identifier
        move_index: Move number in the game
        state_hash: Hash of the board state
        board_state: The board as 2D list
        current_player: 'player1' or 'player2'
        best_move: Oracle's recommended best move
        move_ranking: All moves ranked by strength [best, 2nd, ...]
        visit_counts: Visit counts for each move {col: count}
        q_values: Q values for each move {col: value}
        probabilities: Move probabilities {col: prob}
        num_rollouts: Total rollouts performed
        search_time: Time spent analyzing in seconds
        exploration_constant: MCTS exploration constant used
        actual_move: The move that was actually played (optional)
        move_id: Reference to moves table (optional)

    Returns:
        analysis_id
    """
    analysis_id = str(uuid.uuid4())

    # Calculate comparison metrics if actual move provided
    actual_move_rank = None
    move_agreement = None
    best_move_q = None
    actual_move_q = None
    q_value_loss = None

    if actual_move is not None:
        try:
            actual_move_rank = move_ranking.index(actual_move) + 1  # 1-indexed
            move_agreement = (actual_move == best_move)
        except ValueError:
            actual_move_rank = len(move_ranking) + 1  # Worst possible
            move_agreement = False

        # Calculate Q-value loss
        best_move_q = q_values.get(best_move, 0.0)
        actual_move_q = q_values.get(actual_move, 0.0)
        q_value_loss = best_move_q - actual_move_q

    with self.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO connect4.oracle_analysis (analysis_id, game_id, move_id, move_index,
                                                              state_hash, board_state, current_player,
                                                              best_move, move_ranking,
                                                              visit_counts, q_values, probabilities,
                                                              num_rollouts, search_time_seconds, exploration_constant,
                                                              actual_move, actual_move_rank, move_agreement,
                                                              best_move_q, actual_move_q, q_value_loss)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s) ON CONFLICT (game_id, move_index) DO
                        UPDATE SET
                            best_move = EXCLUDED.best_move,
                            move_ranking = EXCLUDED.move_ranking,
                            visit_counts = EXCLUDED.visit_counts,
                            q_values = EXCLUDED.q_values,
                            probabilities = EXCLUDED.probabilities,
                            num_rollouts = EXCLUDED.num_rollouts,
                            search_time_seconds = EXCLUDED.search_time_seconds,
                            actual_move = EXCLUDED.actual_move,
                            actual_move_rank = EXCLUDED.actual_move_rank,
                            move_agreement = EXCLUDED.move_agreement,
                            best_move_q = EXCLUDED.best_move_q,
                            actual_move_q = EXCLUDED.actual_move_q,
                            q_value_loss = EXCLUDED.q_value_loss
                        """, (
                            analysis_id,
                            game_id,
                            move_id,
                            move_index,
                            state_hash,
                            Json(board_state),
                            current_player,
                            best_move,
                            move_ranking,
                            Json({str(k): v for k, v in visit_counts.items()}),
                            Json({str(k): v for k, v in q_values.items()}),
                            Json({str(k): v for k, v in probabilities.items()}),
                            num_rollouts,
                            search_time,
                            exploration_constant,
                            actual_move,
                            actual_move_rank,
                            move_agreement,
                            best_move_q,
                            actual_move_q,
                            q_value_loss
                        ))

    logger.info(f"Logged oracle analysis for game {game_id} move {move_index}: "
                f"best={best_move}, actual={actual_move}, rank={actual_move_rank}, "
                f"agreement={move_agreement}")

    return analysis_id
