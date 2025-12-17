"""
PostgreSQL Repository implementation for Game persistence.
Implements the repository pattern with SQLAlchemy.
"""
import logging
from typing import Optional, List
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from ..domain import Game, Move
from .entities import GameEntity, MoveEntity
from .mapper import GameMapper, MoveMapper

logger = logging.getLogger(__name__)


class PostgresGameRepository:
    """
    PostgreSQL implementation of game repository.
    Handles all database operations for games and moves.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self._session = session

    def save(self, game: Game) -> None:
        """
        Save or update a game in the database.
        Uses merge to handle both insert and update operations.

        Args:
            game: Domain Game aggregate to persist
        """
        try:
            # Check if game exists
            existing = self._session.get(GameEntity, uuid.UUID(game.id))

            if existing:
                # Update existing game
                self._update_game_entity(existing, game)

                # Handle moves - delete old ones and insert new ones
                # This is simpler than tracking diffs
                self._session.query(MoveEntity).filter(
                    MoveEntity.game_id == uuid.UUID(game.id)
                ).delete()

                # Insert all current moves
                for move in game.moves:
                    move_entity = MoveMapper.to_entity(move, game.id)
                    self._session.add(move_entity)

                logger.debug(f"Updated game {game.id} with {len(game.moves)} moves")
            else:
                # Insert new game
                game_entity = GameMapper.to_entity(game)
                self._session.add(game_entity)

                # Insert moves
                for move in game.moves:
                    move_entity = MoveMapper.to_entity(move, game.id)
                    self._session.add(move_entity)

                logger.debug(f"Inserted new game {game.id}")

            self._session.flush()  # Ensure changes are sent to DB

        except Exception as e:
            logger.error(f"Error saving game {game.id}: {e}", exc_info=True)
            raise

    def get(self, game_id: str) -> Optional[Game]:
        """
        Retrieve a game by ID.
        Uses eager loading to fetch moves in a single query.

        Args:
            game_id: Game identifier

        Returns:
            Game domain aggregate or None if not found
        """
        try:
            # Use joinedload to eagerly fetch moves
            stmt = (
                select(GameEntity)
                .options(joinedload(GameEntity.moves))
                .where(GameEntity.id == uuid.UUID(game_id))
            )

            result = self._session.execute(stmt)
            entity = result.unique().scalar_one_or_none()

            if entity is None:
                logger.debug(f"Game {game_id} not found")
                return None

            # Convert to domain with moves
            game = GameMapper.to_domain(entity, entity.moves)
            logger.debug(f"Retrieved game {game_id} with {len(game.moves)} moves")
            return game

        except Exception as e:
            logger.error(f"Error retrieving game {game_id}: {e}", exc_info=True)
            raise

    def delete(self, game_id: str) -> None:
        """
        Delete a game from the database.
        Cascades to delete all associated moves.

        Args:
            game_id: Game identifier
        """
        try:
            entity = self._session.get(GameEntity, uuid.UUID(game_id))
            if entity:
                self._session.delete(entity)
                self._session.flush()
                logger.debug(f"Deleted game {game_id}")
            else:
                logger.debug(f"Game {game_id} not found for deletion")

        except Exception as e:
            logger.error(f"Error deleting game {game_id}: {e}", exc_info=True)
            raise

    def list_games(
            self,
            phase: Optional[str] = None,
            limit: int = 100,
            offset: int = 0
    ) -> List[Game]:
        """
        List games with optional filtering.

        Args:
            phase: Optional filter by game phase (NOT_STARTED, IN_PROGRESS, FINISHED)
            limit: Maximum number of games to return
            offset: Number of games to skip

        Returns:
            List of Game domain aggregates
        """
        try:
            stmt = select(GameEntity).options(joinedload(GameEntity.moves))

            if phase:
                stmt = stmt.where(GameEntity.phase == phase)

            stmt = stmt.order_by(GameEntity.updated_at.desc())
            stmt = stmt.limit(limit).offset(offset)

            result = self._session.execute(stmt)
            entities = result.scalars().unique().all()

            games = [GameMapper.to_domain(entity, entity.moves) for entity in entities]
            logger.debug(f"Retrieved {len(games)} games (phase={phase})")
            return games

        except Exception as e:
            logger.error(f"Error listing games: {e}", exc_info=True)
            raise

    def count_games(self, phase: Optional[str] = None) -> int:
        """
        Count games with optional filtering.

        Args:
            phase: Optional filter by game phase

        Returns:
            Number of games matching criteria
        """
        try:
            stmt = select(func.count(GameEntity.id))

            if phase:
                stmt = stmt.where(GameEntity.phase == phase)

            result = self._session.execute(stmt)
            count = result.scalar_one()
            return count

        except Exception as e:
            logger.error(f"Error counting games: {e}", exc_info=True)
            raise

    def get_games_by_player(
            self,
            player_id: str,
            limit: int = 100,
            offset: int = 0
    ) -> List[Game]:
        """
        Get all games involving a specific player.

        Args:
            player_id: Player identifier
            limit: Maximum number of games to return
            offset: Number of games to skip

        Returns:
            List of Game domain aggregates
        """
        try:
            stmt = (
                select(GameEntity)
                .options(joinedload(GameEntity.moves))
                .where(
                    (GameEntity.player_one_id == player_id) |
                    (GameEntity.player_two_id == player_id)
                )
                .order_by(GameEntity.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = self._session.execute(stmt)
            entities = result.scalars().unique().all()

            games = [GameMapper.to_domain(entity, entity.moves) for entity in entities]
            logger.debug(f"Retrieved {len(games)} games for player {player_id}")
            return games

        except Exception as e:
            logger.error(f"Error getting games for player {player_id}: {e}", exc_info=True)
            raise

    def _update_game_entity(self, entity: GameEntity, game: Game) -> None:
        """
        Update an existing GameEntity with values from Game domain object.

        Args:
            entity: Database entity to update
            game: Domain object with new values
        """
        entity.rows = game.board.rows
        entity.cols = game.board.cols
        entity.grid = game.board.to_2d_list()
        entity.player_one_id = game.player_one.id
        entity.player_one_name = game.player_one.name
        entity.player_two_id = game.player_two.id
        entity.player_two_name = game.player_two.name
        entity.current_token = game.current_token.value
        entity.phase = game.phase
        entity.winner_id = game.winner.id if game.winner else None
        entity.winner_name = game.winner.name if game.winner else None
        entity.created_at = game.created_at
        entity.updated_at = game.updated_at
        entity.started_at = game.started_at
        entity.finished_at = game.finished_at
        entity.turn_started_at = game.turn_started_at