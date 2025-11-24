# RabbitMQ publisher for Connect4 Backend

import json
import uuid
import logging
from datetime import datetime
import pika
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """Publisher for Connect4 game events"""

    def __init__(self, host='rabbitmq', port=5672, username='user', password='password'):
        self.host = host
        self.port = port
        self.credentials = pika.PlainCredentials(username, password)
        self.connection = None
        self.channel = None
        self.setup_connection()

    def setup_connection(self):
        """Setup RabbitMQ connection"""
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

            # Declare exchange for game events
            self.channel.exchange_declare(
                exchange='connect4_events',
                exchange_type='topic',
                durable=True
            )

            logger.info("RabbitMQ Publisher connected")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")

    def publish_event(self, routing_key: str, event: Dict[str, Any]):
        """Publish event to RabbitMQ"""
        try:
            if not self.connection or self.connection.is_closed:
                self.setup_connection()

            self.channel.basic_publish(
                exchange='connect4_events',
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            logger.info(f"Published event: {routing_key}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")

    def publish_game_created(self, game_id: str, config: dict):
        """Publish game created event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'game.created',
            'timestamp': datetime.utcnow().isoformat(),
            'game_id': game_id,
            'config': config
        }
        self.publish_event('game.created', event)

    def publish_human_move(self, game_id: str, player: str, column: int,
                           board: list, current_player: str, status: str):
        """Publish human move made event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'human.move.made',
            'timestamp': datetime.utcnow().isoformat(),
            'game_id': game_id,
            'player': player,
            'column': column,
            'board': board,
            'current_player': current_player,
            'status': status
        }
        self.publish_event('human.move.made', event)

    def publish_ai_move_needed(self, game_id: str, board: list, current_player: int):
        """Publish event that AI move is needed"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'ai.move.needed',
            'timestamp': datetime.utcnow().isoformat(),
            'game_id': game_id,
            'board': board,
            'current_player': current_player
        }
        self.publish_event('ai.move.needed', event)

    def publish_game_ended(self, game_id: str, winner: str, final_board: list):
        """Publish game ended event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'game.ended',
            'timestamp': datetime.utcnow().isoformat(),
            'game_id': game_id,
            'winner': winner,
            'final_board': final_board
        }
        self.publish_event('game.ended', event)

    def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
