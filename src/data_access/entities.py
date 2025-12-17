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
    id = Column(UUID(as_uuid=True), primary_key=True)

    # Board configuration
    rows = Column(Integer, nullable=False)
    cols = Column(Integer, nullable=False)

    # Board state (stored as JSONB 2D array)
    grid = Column(JSONB, nullable=False)

    # Players
    player_one_id = Column(String(255), nullable=False)
    player_one_name = Column(String(255), nullable=False)
    player_two_id = Column(String(255), nullable=False)
    player_two_name = Column(String(255), nullable=False)

    # Game state
    current_token = Column(String(1), nullable=False)
    phase = Column(String(20), nullable=False)

    # Winner (nullable)
    winner_id = Column(String(255), nullable=True)
    winner_name = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    turn_started_at = Column(TIMESTAMP(timezone=True), nullable=False)

    # Relationships
    moves = relationship(
        "MoveEntity",
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="MoveEntity.move_index"
    )

    def __repr__(self) -> str:
        return f"<GameEntity(id={self.id}, phase={self.phase})>"


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
        {"schema": "connect4_backend"}
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to game
    game_id = Column(UUID(as_uuid=True), ForeignKey("connect4_backend.games.id", ondelete="CASCADE"), nullable=False)

    # Move details
    move_index = Column(Integer, nullable=False)
    col = Column(Integer, nullable=False)  # Renamed from 'column' (reserved keyword)

    # Landing position
    landed_row = Column(Integer, nullable=False)
    landed_col = Column(Integer, nullable=False)

    # Token placed
    token = Column(String(1), nullable=False)

    # Player
    player_id = Column(String(255), nullable=False)

    # Timing
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    thinking_time_ms = Column(Float, nullable=False)

    # Relationships
    game = relationship("GameEntity", back_populates="moves")

    def __repr__(self) -> str:
        return f"<MoveEntity(id={self.id}, game_id={self.game_id}, move_index={self.move_index})>"