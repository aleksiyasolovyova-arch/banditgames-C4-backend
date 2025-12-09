# app/rabbitmq_publisher.py
"""
RabbitMQ publisher for Connect4 game events.
Supports game lifecycle, AI moves, self-play, and dataset export events.
"""

import json
import uuid
import logging
import os
from datetime import datetime, UTC
import pika
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    def __init__(
            self,
            host: str = None,
            port: int = None,
            username: str = None,
            password: str = None
    ):
        # Read from environment variables with defaults
        self.host = host or os.getenv('RABBITMQ_HOST', 'rabbitmq')
        self.port = port or int(os.getenv('RABBITMQ_PORT', '5672'))
        username = username or os.getenv('RABBITMQ_USER', 'user')
        password = password or os.getenv('RABBITMQ_PASSWORD', 'password')

        self.credentials = pika.PlainCredentials(username, password)
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel = None

        # Log connection parameters for debugging (without password)
        logger.info(f"RabbitMQ config: host={self.host}, port={self.port}, user={username}")

        self.setup_connection()

    def setup_connection(self):
        """Setup RabbitMQ connection and declare exchanges/queues"""
        try:
            params = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=self.credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()

            # Declare main exchange for game events
            self.channel.exchange_declare(
                exchange='connect4_events',
                exchange_type='topic',
                durable=True
            )

            # Declare exchange for dataset/ML events
            self.channel.exchange_declare(
                exchange='connect4_ml',
                exchange_type='topic',
                durable=True
            )

            logger.info("RabbitMQ Publisher connected successfully")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def _ensure_connection(self):
        """Ensure connection is active, reconnect if needed"""
        if not self.connection or self.connection.is_closed:
            self.setup_connection()

    def publish_event(
            self,
            routing_key: str,
            event: Dict[str, Any],
            exchange: str = 'connect4_events'
    ):
        """Publish event to RabbitMQ"""
        try:
            self._ensure_connection()

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(event, default=str),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    content_type='application/json',
                    timestamp=int(datetime.now(UTC).timestamp())
                )
            )
            logger.debug(f"Published event: {routing_key}")

        except Exception as e:
            logger.error(f"Failed to publish event {routing_key}: {e}")

    # =========================================================================
    # Game Lifecycle Events
    # =========================================================================

    def publish_game_created(self, game_id: str, config: dict):
        """Publish game created event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'game.created',
            'timestamp': datetime.now(UTC).isoformat(),
            'game_id': game_id,
            'config': config
        }
        self.publish_event('game.created', event)

    def publish_game_ended(
            self,
            game_id: str,
            winner: str,
            final_board: list,
            total_moves: int = None,
            duration_seconds: float = None
    ):
        """Publish game ended event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'game.ended',
            'timestamp': datetime.now(UTC).isoformat(),
            'game_id': game_id,
            'winner': winner,
            'final_board': final_board,
            'total_moves': total_moves,
            'duration_seconds': duration_seconds
        }
        self.publish_event('game.ended', event)

    # =========================================================================
    # Human Move Events
    # =========================================================================

    def publish_human_move(
            self,
            game_id: str,
            player: str,
            column: int,
            board: list,
            current_player: str,
            status: str,
            thinking_time_ms: int = None
    ):
        """Publish human move made event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'human.move.made',
            'timestamp': datetime.now(UTC).isoformat(),
            'game_id': game_id,
            'player': player,
            'column': column,
            'board': board,
            'current_player': current_player,
            'status': status,
            'thinking_time_ms': thinking_time_ms
        }
        self.publish_event('human.move.made', event)

    # AI Move Events
    def publish_ai_move_needed(
            self,
            game_id: str,
            board: list,
            current_player: int,
            skill_level: str = None,
            dda_adjustment: float = 1.0
    ):
        """Publish event that AI move is needed"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'ai.move.needed',
            'timestamp': datetime.now(UTC).isoformat(),
            'game_id': game_id,
            'board': board,
            'current_player': current_player,
            'skill_level': skill_level,
            'dda_adjustment': dda_adjustment
        }
        self.publish_event('ai.move.needed', event)

    def publish_ai_move_made(
            self,
            game_id: str,
            player: str,
            column: int,
            board: list,
            mcts_stats: dict,
            current_player: str,
            status: str
    ):
        """Publish AI move made event with MCTS statistics"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'ai.move.made',
            'timestamp': datetime.now(UTC).isoformat(),
            'game_id': game_id,
            'player': player,
            'column': column,
            'board': board,
            'mcts_stats': mcts_stats,
            'current_player': current_player,
            'status': status
        }
        self.publish_event('ai.move.made', event)

    # Self-Play Events
    def publish_self_play_started(
            self,
            session_id: str,
            config: dict,
            num_games: int
    ):
        """Publish self-play session started event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'self_play.session.started',
            'timestamp': datetime.now(UTC).isoformat(),
            'session_id': session_id,
            'config': config,
            'num_games': num_games
        }
        self.publish_event('self_play.session.started', event)
        # Also publish to ML exchange
        self.publish_event('self_play.session.started', event, exchange='connect4_ml')

    def publish_self_play_progress(
            self,
            session_id: str,
            games_completed: int,
            games_total: int,
            agent1_wins: int,
            agent2_wins: int,
            draws: int
    ):
        """Publish self-play session progress"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'self_play.session.progress',
            'timestamp': datetime.now(UTC).isoformat(),
            'session_id': session_id,
            'games_completed': games_completed,
            'games_total': games_total,
            'agent1_wins': agent1_wins,
            'agent2_wins': agent2_wins,
            'draws': draws,
            'progress_percent': (games_completed / games_total) * 100
        }
        self.publish_event('self_play.session.progress', event)

    def publish_self_play_ended(
            self,
            session_id: str,
            total_games: int,
            agent1_wins: int,
            agent2_wins: int,
            draws: int,
            duration_seconds: float
    ):
        """Publish self-play session ended event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'self_play.session.ended',
            'timestamp': datetime.now(UTC).isoformat(),
            'session_id': session_id,
            'total_games': total_games,
            'agent1_wins': agent1_wins,
            'agent2_wins': agent2_wins,
            'draws': draws,
            'duration_seconds': duration_seconds
        }
        self.publish_event('self_play.session.ended', event)
        self.publish_event('self_play.session.ended', event, exchange='connect4_ml')

    # Dataset Export Events
    def publish_dataset_export_requested(
            self,
            export_id: str,
            version: str,
            config: dict
    ):
        """Publish dataset export requested event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'dataset.export.requested',
            'timestamp': datetime.now(UTC).isoformat(),
            'export_id': export_id,
            'version': version,
            'config': config
        }
        self.publish_event('dataset.export.requested', event, exchange='connect4_ml')

    def publish_dataset_export_completed(
            self,
            export_id: str,
            version: str,
            file_path: str,
            num_games: int,
            num_moves: int,
            file_size_bytes: int,
            checksum: str
    ):
        """Publish dataset export completed event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'dataset.export.completed',
            'timestamp': datetime.now(UTC).isoformat(),
            'export_id': export_id,
            'version': version,
            'file_path': file_path,
            'num_games': num_games,
            'num_moves': num_moves,
            'file_size_bytes': file_size_bytes,
            'checksum': checksum
        }
        self.publish_event('dataset.export.completed', event, exchange='connect4_ml')

    # Connection Management
    def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ Publisher connection closed")