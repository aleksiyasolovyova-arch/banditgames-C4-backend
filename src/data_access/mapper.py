"""
Mapper layer - converts between domain objects and database entities.
"""
from typing import List
import uuid
from datetime import datetime, UTC

from ..domain import Game, Move, Player, Token, Position, Board
from .entities import GameEntity, MoveEntity, PlayerEntity, AchievementUnlockedEntity


class PlayerMapper:
    """
    Bidirectional mapper between Player domain value object and PlayerEntity.
    """

    @staticmethod
    def to_entity(player: Player) -> PlayerEntity:
        """
        Convert domain Player to database PlayerEntity.

        Args:
            player: Domain Player value object

        Returns:
            PlayerEntity for database persistence
        """
        now = datetime.now(UTC)
        return PlayerEntity(
            player_id=uuid.UUID(player.id),
            name=player.name,
            created_at=now,
            updated_at=now
        )

    @staticmethod
    def to_domain(entity: PlayerEntity) -> Player:
        """
        Convert database PlayerEntity to domain Player.

        Args:
            entity: Database PlayerEntity

        Returns:
            Domain Player value object
        """
        return Player(
            id=str(entity.player_id),
            name=entity.name
        )


class GameMapper:
    """
    Bidirectional mapper between Game domain aggregate and GameEntity.
    """

    @staticmethod
    def to_entity(game: Game) -> GameEntity:
        """
        Convert domain Game to database GameEntity.

        Args:
            game: Domain Game aggregate

        Returns:
            GameEntity for database persistence
        """
        return GameEntity(
            game_id=uuid.UUID(game.id),
            rows=game.board.rows,
            cols=game.board.cols,
            grid=game.board.to_2d_list(),  # Store as JSONB
            player_one_id=uuid.UUID(game.player_one.id),
            player_one_name=game.player_one.name,
            player_two_id=uuid.UUID(game.player_two.id),
            player_two_name=game.player_two.name,
            current_token=game.current_token.value,
            phase=game.phase,
            winner_id=uuid.UUID(game.winner.id) if game.winner else None,
            winner_name=game.winner.name if game.winner else None,
            created_at=game.created_at,
            updated_at=game.updated_at,
            started_at=game.started_at,
            finished_at=game.finished_at,
            turn_started_at=game.turn_started_at
        )

    @staticmethod
    def to_domain(entity: GameEntity, move_entities: List[MoveEntity] = None) -> Game:
        """
        Convert database GameEntity to domain Game.

        Args:
            entity: Database GameEntity
            move_entities: Optional list of MoveEntity objects (for eager loading)

        Returns:
            Domain Game aggregate
        """
        # Reconstruct board from grid
        board = Board.from_2d_list(entity.grid)

        # Reconstruct players
        player_one = Player(id=str(entity.player_one_id), name=entity.player_one_name)
        player_two = Player(id=str(entity.player_two_id), name=entity.player_two_name)

        # Create game with minimal constructor
        game = Game(
            game_id=str(entity.game_id),
            rows=entity.rows,
            cols=entity.cols,
            player_one=player_one,
            player_two=player_two
        )

        # Restore board state
        game.board = board

        # Restore game state
        game.current_token = Token(entity.current_token)

        # Restore winner
        if entity.winner_id:
            if str(entity.winner_id) == player_one.id:
                game.winner = player_one
            elif str(entity.winner_id) == player_two.id:
                game.winner = player_two

        # Restore timestamps
        game.created_at = entity.created_at
        game.updated_at = entity.updated_at
        game.started_at = entity.started_at
        game.finished_at = entity.finished_at
        game.turn_started_at = entity.turn_started_at

        # Restore moves
        if move_entities is not None:
            game.moves = [MoveMapper.to_domain(move_entity) for move_entity in move_entities]
        elif hasattr(entity, 'moves') and entity.moves:
            game.moves = [MoveMapper.to_domain(move_entity) for move_entity in entity.moves]

        return game


class MoveMapper:
    """
    Bidirectional mapper between Move value object and MoveEntity.
    """

    @staticmethod
    def to_entity(move: Move, game_id: str) -> MoveEntity:
        """
        Convert domain Move to database MoveEntity.

        Args:
            move: Domain Move value object
            game_id: Game ID this move belongs to

        Returns:
            MoveEntity for database persistence
        """
        return MoveEntity(
            move_id=uuid.uuid4(),
            game_id=uuid.UUID(game_id),
            move_index=move.move_index,
            col=move.column,  # Domain uses 'column', DB uses 'col'
            landed_row=move.landed_at.row,
            landed_col=move.landed_at.col,
            token=move.token.value,
            player_id=uuid.UUID(move.player_id),
            timestamp=move.timestamp,
            thinking_time_ms=move.thinking_time_ms
        )

    @staticmethod
    def to_domain(entity: MoveEntity) -> Move:
        """
        Convert database MoveEntity to domain Move.

        Args:
            entity: Database MoveEntity

        Returns:
            Domain Move value object
        """
        return Move(
            move_index=entity.move_index,
            column=entity.col,  # DB uses 'col', Domain uses 'column'
            landed_at=Position(row=entity.landed_row, col=entity.landed_col),
            token=Token(entity.token),
            player_id=str(entity.player_id),
            timestamp=entity.timestamp,
            thinking_time_ms=entity.thinking_time_ms
        )


class AchievementUnlockedMapper:
    """
    Mapper for AchievementUnlockedEntity.
    Maps achievement unlock records between domain and database.
    """

    @staticmethod
    def to_entity(
        player_id: str,
        achievement_type: str,
        game_id: str = None,
        unlocked_at: datetime = None
    ) -> AchievementUnlockedEntity:
        """
        Create AchievementUnlockedEntity from domain data.

        Args:
            player_id: Player UUID string
            achievement_type: Achievement type string
            game_id: Optional game UUID string
            unlocked_at: Optional unlock timestamp

        Returns:
            AchievementUnlockedEntity for database persistence
        """
        return AchievementUnlockedEntity(
            achievement_id=uuid.uuid4(),
            player_id=uuid.UUID(player_id),
            achievement_type=achievement_type,
            game_id=uuid.UUID(game_id) if game_id else None,
            unlocked_at=unlocked_at or datetime.now(UTC)
        )

    @staticmethod
    def to_dict(entity: AchievementUnlockedEntity) -> dict:
        """
        Convert AchievementUnlockedEntity to dictionary.

        Args:
            entity: Database AchievementUnlockedEntity

        Returns:
            Dictionary representation
        """
        return {
            "id": str(entity.achievement_id),
            "playerId": str(entity.player_id),
            "achievementType": entity.achievement_type,
            "gameId": str(entity.game_id) if entity.game_id else None,
            "unlockedAt": entity.unlocked_at.isoformat()
        }