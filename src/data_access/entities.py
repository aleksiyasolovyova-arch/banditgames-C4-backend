"""
SQLAlchemy ORM entities for database persistence.
These are the database representations (infrastructure layer).
"""
from datetime import datetime
from typing import List

from sqlalchemy import (
    Column, String, Integer, Float, ForeignKey,
    CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PlayerEntity(Base):
    """
    ORM entity for players table.
    Represents player information in the database.
    """
    __tablename__ = "players"
    __table_args__ = (
        Index("idx_players_created_at", "created_at"),
        Index("idx_players_name", "name"),
        {"schema": "connect4_backend"}
    )

    # Primary key
    player_id = Column(UUID(as_uuid=True), primary_key=True, name="player_id")

    # Player information
    name = Column(String(255), nullable=False)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)

    # Relationships
    games_as_player_one = relationship(
        "GameEntity",
        foreign_keys="GameEntity.player_one_id",
        back_populates="player_one_entity"
    )
    games_as_player_two = relationship(
        "GameEntity",
        foreign_keys="GameEntity.player_two_id",
        back_populates="player_two_entity"
    )
    moves = relationship(
        "MoveEntity",
        back_populates="player_entity",
        cascade="all, delete-orphan"
    )
    achievements = relationship(
        "AchievementUnlockedEntity",
        back_populates="player_entity",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PlayerEntity(player_id={self.player_id}, name={self.name})>"


class GameEntity(Base):
    """
    ORM entity for games table.
    Represents the database structure for game persistence.
    """
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("rows >= 4 AND rows <= 10", name="check_rows_range"),
        CheckConstraint("cols >= 4 AND cols <= 10", name="check_cols_range"),
        CheckConstraint("current_token IN ('X', 'O')", name="check_current_token"),
        CheckConstraint(
            "phase IN ('NOT_STARTED', 'IN_PROGRESS', 'FINISHED')",
            name="check_phase"
        ),
        CheckConstraint(
            "player_one_id != player_two_id",
            name="check_different_players"
        ),
        CheckConstraint(
            "winner_id IS NULL OR winner_id = player_one_id OR winner_id = player_two_id",
            name="check_winner_is_player"
        ),
        Index("idx_games_player_one", "player_one_id"),
        Index("idx_games_player_two", "player_two_id"),
        Index("idx_games_phase", "phase"),
        Index("idx_games_created_at", "created_at"),
        Index("idx_games_updated_at", "updated_at"),
        {"schema": "connect4_backend"}
    )

    # Primary key
    game_id = Column(UUID(as_uuid=True), primary_key=True, name="game_id")

    # Board configuration
    rows = Column(Integer, nullable=False)
    cols = Column(Integer, nullable=False)

    # Board state (stored as JSONB 2D array)
    grid = Column(JSONB, nullable=False)

    # Players (foreign keys to players table)
    player_one_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.players.player_id", ondelete="RESTRICT"), nullable=False)
    player_one_name = Column(String(255), nullable=False)
    player_two_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.players.player_id", ondelete="RESTRICT"), nullable=False)
    player_two_name = Column(String(255), nullable=False)

    # Game state
    current_token = Column(String(1), nullable=False)
    phase = Column(String(20), nullable=False)

    # Winner (nullable)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.players.player_id", ondelete="RESTRICT"), nullable=True)
    winner_name = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    turn_started_at = Column(TIMESTAMP(timezone=True), nullable=False)

    # Relationships
    player_one_entity = relationship(
        "PlayerEntity",
        foreign_keys=[player_one_id],
        back_populates="games_as_player_one"
    )
    player_two_entity = relationship(
        "PlayerEntity",
        foreign_keys=[player_two_id],
        back_populates="games_as_player_two"
    )
    moves = relationship(
        "MoveEntity",
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="MoveEntity.move_index"
    )
    achievements = relationship(
        "AchievementUnlockedEntity",
        back_populates="game_entity",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GameEntity(game_id={self.game_id}, phase={self.phase})>"


class MoveEntity(Base):
    """
    ORM entity for moves table.
    Represents individual moves in a game.
    """
    __tablename__ = "moves"
    __table_args__ = (
        UniqueConstraint("game_id", "move_index", name="unique_move_index_per_game"),
        CheckConstraint("token IN ('X', 'O')", name="check_token"),
        CheckConstraint("col >= 0", name="check_column_positive"),
        CheckConstraint("landed_row >= 0", name="check_landed_row_positive"),
        CheckConstraint("landed_col >= 0", name="check_landed_col_positive"),
        CheckConstraint("move_index >= 0", name="check_move_index_positive"),
        CheckConstraint("thinking_time_ms >= 0", name="check_thinking_time_positive"),
        Index("idx_moves_game_id", "game_id"),
        Index("idx_moves_game_move_index", "game_id", "move_index"),
        Index("idx_moves_timestamp", "timestamp"),
        Index("idx_moves_player_id", "player_id"),
        {"schema": "connect4_backend"}
    )

    # Primary key
    move_id = Column(UUID(as_uuid=True), primary_key=True, name="move_id")

    # Foreign key to game
    game_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.games.game_id", ondelete="CASCADE"), nullable=False)

    # Move details
    move_index = Column(Integer, nullable=False)
    col = Column(Integer, nullable=False)  # Renamed from 'column' (reserved keyword)

    # Landing position
    landed_row = Column(Integer, nullable=False)
    landed_col = Column(Integer, nullable=False)

    # Token placed
    token = Column(String(1), nullable=False)

    # Player (foreign key to players table)
    player_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.players.player_id", ondelete="RESTRICT"), nullable=False)

    # Timing
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    thinking_time_ms = Column(Float, nullable=False)

    # Relationships
    game = relationship("GameEntity", back_populates="moves")
    player_entity = relationship("PlayerEntity", back_populates="moves")

    def __repr__(self) -> str:
        return f"<MoveEntity(move_id={self.move_id}, game_id={self.game_id}, move_index={self.move_index})>"


class AchievementUnlockedEntity(Base):
    """
    ORM entity for achievement_unlocked table.
    Represents achievements unlocked by players.
    Prevents duplicate achievement unlocks via unique constraint.
    """
    __tablename__ = "achievement_unlocked"
    __table_args__ = (
        UniqueConstraint("player_id", "achievement_type", name="uq_player_achievement"),
        Index("idx_achievement_unlocked_player", "player_id"),
        Index("idx_achievement_unlocked_type", "achievement_type"),
        Index("idx_achievement_unlocked_game", "game_id"),
        Index("idx_achievement_unlocked_at", "unlocked_at"),
        {"schema": "connect4_backend"}
    )

    # Primary key
    achievement_id = Column(UUID(as_uuid=True), primary_key=True, name="achievement_id")

    # Player who unlocked the achievement
    player_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.players.player_id", ondelete="CASCADE"), nullable=False)

    # Achievement type
    achievement_type = Column(String(64), nullable=False)

    # When the achievement was unlocked
    unlocked_at = Column(TIMESTAMP(timezone=True), nullable=False)

    # Optional: which game caused the unlock
    game_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.games.game_id", ondelete="SET NULL"), nullable=True)

    # Relationships
    player_entity = relationship("PlayerEntity", back_populates="achievements")
    game_entity = relationship("GameEntity", back_populates="achievements")

    def __repr__(self) -> str:
        return f"<AchievementUnlockedEntity(achievement_id={self.achievement_id}, player_id={self.player_id}, achievement_type={self.achievement_type})>"