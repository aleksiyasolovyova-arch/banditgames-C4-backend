"""
PostgreSQL Repository implementation for Game persistence.
Implements the repository pattern with SQLAlchemy.
"""
import logging
from typing import Optional, List
import uuid
from datetime import datetime, UTC

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from ..domain import Game, Move, Player
from .entities import GameEntity, MoveEntity, PlayerEntity, AchievementUnlockedEntity
from .mapper import GameMapper, MoveMapper, PlayerMapper, AchievementUnlockedMapper

logger = logging.getLogger(__name__)


class PostgresGameRepository:
    """
    PostgreSQL implementation of game repository.
    Handles all database operations for games, moves, players, and achievements.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self._session = session

    def ensure_player_exists(self, player: Player) -> None:
        """
        Ensure a player exists in the database.
        Creates player if not exists, updates if exists.

        Args:
            player: Domain Player value object
        """
        try:
            existing = self._session.get(PlayerEntity, uuid.UUID(player.id))

            if existing:
                # Update existing player
                existing.name = player.name
                existing.updated_at = datetime.now(UTC)
                logger.debug(f"Updated player {player.id}")
            else:
                # Insert new player
                player_entity = PlayerMapper.to_entity(player)
                self._session.add(player_entity)
                logger.debug(f"Inserted new player {player.id}")

            self._session.flush()

        except Exception as e:
            logger.error(f"Error ensuring player {player.id} exists: {e}", exc_info=True)
            raise

    def get_player(self, player_id: str) -> Optional[Player]:
        """
        Retrieve a player by ID.

        Args:
            player_id: Player identifier (UUID string)

        Returns:
            Player domain object or None if not found
        """
        try:
            entity = self._session.get(PlayerEntity, uuid.UUID(player_id))
            if entity is None:
                logger.debug(f"Player {player_id} not found")
                return None

            player = PlayerMapper.to_domain(entity)
            logger.debug(f"Retrieved player {player_id}")
            return player

        except Exception as e:
            logger.error(f"Error retrieving player {player_id}: {e}", exc_info=True)
            raise

    def save(self, game: Game) -> None:
        """
        Save or update a game in the database.
        Automatically ensures players exist before saving game.

        Args:
            game: Domain Game aggregate to persist
        """
        try:
            # Ensure both players exist in the database
            self.ensure_player_exists(game.player_one)
            self.ensure_player_exists(game.player_two)

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
                .where(GameEntity.game_id == uuid.UUID(game_id))
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
        Cascades to delete all associated moves and achievements.

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
            stmt = select(func.count(GameEntity.game_id))

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
            player_uuid = uuid.UUID(player_id)
            stmt = (
                select(GameEntity)
                .options(joinedload(GameEntity.moves))
                .where(
                    (GameEntity.player_one_id == player_uuid) |
                    (GameEntity.player_two_id == player_uuid)
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

    def record_achievement_unlock(
        self,
        player_id: str,
        achievement_type: str,
        game_id: str = None
    ) -> bool:
        """
        Record an achievement unlock for a player.
        Returns True if successfully recorded, False if already unlocked.

        Args:
            player_id: Player UUID string
            achievement_type: Achievement type string
            game_id: Optional game UUID string that triggered the achievement

        Returns:
            True if achievement was newly recorded, False if already existed
        """
        try:
            # Check if achievement already unlocked
            existing = self._session.query(AchievementUnlockedEntity).filter(
                AchievementUnlockedEntity.player_id == uuid.UUID(player_id),
                AchievementUnlockedEntity.achievement_type == achievement_type
            ).first()

            if existing:
                logger.debug(
                    f"Achievement {achievement_type} already unlocked for player {player_id}"
                )
                return False

            # Create new achievement unlock record
            achievement_entity = AchievementUnlockedMapper.to_entity(
                player_id=player_id,
                achievement_type=achievement_type,
                game_id=game_id
            )
            self._session.add(achievement_entity)
            self._session.flush()

            logger.info(
                f"Recorded achievement unlock: {achievement_type} for player {player_id}"
            )
            return True

        except IntegrityError as e:
            # Handle race condition where achievement was unlocked concurrently
            logger.warning(
                f"Achievement {achievement_type} already unlocked for player {player_id} "
                f"(concurrent unlock attempt)"
            )
            self._session.rollback()
            return False
        except Exception as e:
            logger.error(
                f"Error recording achievement unlock for player {player_id}: {e}",
                exc_info=True
            )
            raise

    def get_player_achievements(self, player_id: str) -> List[dict]:
        """
        Get all achievements unlocked by a player.

        Args:
            player_id: Player UUID string

        Returns:
            List of achievement dictionaries
        """
        try:
            achievements = self._session.query(AchievementUnlockedEntity).filter(
                AchievementUnlockedEntity.player_id == uuid.UUID(player_id)
            ).order_by(AchievementUnlockedEntity.unlocked_at.desc()).all()

            return [AchievementUnlockedMapper.to_dict(a) for a in achievements]

        except Exception as e:
            logger.error(f"Error getting achievements for player {player_id}: {e}", exc_info=True)
            raise

    def is_achievement_unlocked(self, player_id: str, achievement_type: str) -> bool:
        """
        Check if a player has already unlocked a specific achievement.

        Args:
            player_id: Player UUID string
            achievement_type: Achievement type string

        Returns:
            True if achievement is unlocked, False otherwise
        """
        try:
            count = self._session.query(func.count(AchievementUnlockedEntity.achievement_id)).filter(
                AchievementUnlockedEntity.player_id == uuid.UUID(player_id),
                AchievementUnlockedEntity.achievement_type == achievement_type
            ).scalar()

            return count > 0

        except Exception as e:
            logger.error(
                f"Error checking achievement unlock for player {player_id}: {e}",
                exc_info=True
            )
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
        entity.player_one_id = uuid.UUID(game.player_one.id)
        entity.player_one_name = game.player_one.name
        entity.player_two_id = uuid.UUID(game.player_two.id)
        entity.player_two_name = game.player_two.name
        entity.current_token = game.current_token.value
        entity.phase = game.phase
        entity.winner_id = uuid.UUID(game.winner.id) if game.winner else None
        entity.winner_name = game.winner.name if game.winner else None
        entity.created_at = game.created_at
        entity.updated_at = game.updated_at
        entity.started_at = game.started_at
        entity.finished_at = game.finished_at
        entity.turn_started_at = game.turn_started_at