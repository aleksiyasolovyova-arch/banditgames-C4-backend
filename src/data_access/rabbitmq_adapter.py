"""
RabbitMQ Event Publisher Implementation.
Publishes domain events to RabbitMQ exchange.

Location: src/data_access/rabbitmq_adapter.py
"""
import json
import logging
from datetime import datetime, UTC
from typing import Dict, Any, List
import uuid

import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from ..domain import Game, Move
from ..config import Settings

logger = logging.getLogger(__name__)


class RabbitMQEventPublisher:
    EXCHANGE = "connect4.events"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._connection: pika.BlockingConnection | None = None
        self._channel: pika.channel.Channel | None = None
        self._setup_connection()

    def _setup_connection(self) -> None:
        try:
            credentials = pika.PlainCredentials(
                self.settings.rabbitmq_user,
                self.settings.rabbitmq_password
            )

            parameters = pika.ConnectionParameters(
                host=self.settings.rabbitmq_host,
                port=self.settings.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )

            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()

            self._channel.exchange_declare(
                exchange=self.EXCHANGE,
                exchange_type="topic",
                durable=True
            )

            logger.info(
                f"Connected to RabbitMQ at "
                f"{self.settings.rabbitmq_host}:{self.settings.rabbitmq_port}"
            )

        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def _ensure_connection(self) -> None:
        if not self._connection or self._connection.is_closed:
            logger.warning("RabbitMQ connection lost, reconnecting...")
            self._setup_connection()

    def _publish(self, routing_key: str, event: Dict[str, Any]) -> None:
        try:
            self._ensure_connection()
            message_body = json.dumps(event, default=str)

            self._channel.basic_publish(
                exchange=self.EXCHANGE,
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                    timestamp=int(datetime.now(UTC).timestamp())
                )
            )

            logger.debug(f"Published event {routing_key}")

        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Failed to publish event {routing_key}: {e}")

    def publish_game_created(self, game: Game) -> None:
        if not game.player_one or not game.player_two:
            raise RuntimeError("Invariant violation: game created without two players")

        event = {
            "eventId": str(uuid.uuid4()),
            "eventType": "game.created",
            "timestamp": datetime.now(UTC).isoformat(),
            "gameId": game.id,
            "board": {"rows": game.board.rows, "cols": game.board.cols},
            "playerOne": game.player_one.to_dict(),
            "playerTwo": game.player_two.to_dict(),
            "phase": game.phase
        }
        self._publish("game.created", event)

    def publish_move_made(
            self,
            game: Game,
            move: Move,
            pre_state: Dict[str, Any],
            post_state: Dict[str, Any],
            legal_moves: List[int]
    ) -> None:
        event = {
            "eventId": str(uuid.uuid4()),
            "eventType": "move.made",
            "timestamp": move.timestamp.isoformat(),
            "gameId": game.id,
            "nextPlayerId": game.get_current_player().id,
            "move": move.to_dict(),  # includes thinkingTimeMs
            "legalMoves": legal_moves,
            "preState": pre_state,
            "postState": post_state
        }
        self._publish("move.made", event)

    def publish_game_finished(self, game: Game) -> None:
        event = {
            "eventId": str(uuid.uuid4()),
            "eventType": "game.finished",
            "timestamp": datetime.now(UTC).isoformat(),
            "gameId": game.id,
            "phase": game.phase,
            "winner": game.winner.to_dict() if game.winner else None,
            "totalMoves": game.get_move_count(),
            "durationSeconds": game.get_duration_seconds()
        }
        self._publish("game.finished", event)

    def publish_achievement_unlocked(self, event_data: Dict[str, Any]) -> None:
        """
        Publish achievement unlocked event.

        Args:
            event_data: Dictionary containing:
                - playerId: Player who unlocked achievement
                - achievementType: Type of achievement
                - title: Achievement title
                - description: Achievement description
        """
        event = {
            "eventId": str(uuid.uuid4()),
            "eventType": "achievement.unlocked",
            "timestamp": datetime.now(UTC).isoformat(),
            "playerId": event_data["playerId"],
            "achievementType": event_data["achievementType"],
            "title": event_data["title"],
            "description": event_data["description"],
        }
        self._publish("achievement.unlocked", event)

        logger.info(
            f"Published achievement.unlocked event for player {event_data['playerId']}: "
            f"{event_data['achievementType']}"
        )

    def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            logger.info("RabbitMQ connection closed")