"""
Game aggregate root - central domain entity for Connect Four.
"""
from __future__ import annotations

from typing import Optional, List
from datetime import datetime, UTC
import uuid

from .board import Board
from .player import Player
from .token import Token
from .move import Move
from .game_status import GameStatus


class Game:
    """
    Aggregate root for Connect Four game.

    Invariants:
    - A game always has exactly two players at creation time.
    - Domain enforces rules: turn order, legal moves, win/draw.
    - The game is agnostic to whether a player is human or AI.
    """

    def __init__(
        self,
        game_id: Optional[str] = None,
        rows: int = Board.DEFAULT_ROWS,
        cols: int = Board.DEFAULT_COLS,
        player_one: Optional[Player] = None,
        player_two: Optional[Player] = None
    ):
        self.id = game_id or str(uuid.uuid4())
        self.board = Board(rows, cols)

        # Enforce invariant: two players must exist.
        if player_one is None or player_two is None:
            raise ValueError("A game must be created with two players (player_one and player_two).")

        if player_one.id == player_two.id:
            raise ValueError("player_one and player_two must be different players.")

        self.player_one = player_one
        self.player_two = player_two

        # Game state
        self.current_token = Token.PLAYER_ONE  # Player 1 always starts
        self.status = GameStatus.IN_PROGRESS

        # TODO Why do we save the winner like this if the winner information is in the game status enum?

        self.winner: Optional[Player] = None

        # Move history
        self.moves: List[Move] = []

        # Timestamps
        self.created_at = datetime.now(UTC)
        self.updated_at = self.created_at
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None

    # Player Management

    def get_player_for_token(self, token: Token) -> Optional[Player]:
        if token == Token.PLAYER_ONE:
            return self.player_one
        if token == Token.PLAYER_TWO:
            return self.player_two
        return None

    def get_token_for_player(self, player_id: str) -> Optional[Token]:
        if self.player_one.id == player_id:
            return Token.PLAYER_ONE
        if self.player_two.id == player_id:
            return Token.PLAYER_TWO
        return None

    def get_current_player(self) -> Player:
        player = self.get_player_for_token(self.current_token)
        # With our invariants, this should never be None.
        if player is None:
            raise RuntimeError("Invariant broken: current player is missing.")
        return player

    # Game Actions

    def make_move(self, player_id: str, column: int) -> Move:
        """
        Execute a move in the game.
        Domain validates everything and updates game state.
        """
        if self.status != GameStatus.IN_PROGRESS:
            raise ValueError(f"Game is not in progress (status: {self.status})")

        token = self.get_token_for_player(player_id)
        if token is None:
            raise ValueError(f"Player {player_id} is not in this game")

        if token != self.current_token:
            current_player = self.get_current_player()
            raise ValueError(f"Not your turn. Waiting for {current_player.name}")

        if not self.board.is_column_available(column):
            raise ValueError(f"Column {column} is not available")

        # Mark start time on first valid move
        if self.started_at is None:
            self.started_at = datetime.now(UTC)

        # Execute move (functional style - returns new board)
        new_board, landing_position = self.board.drop_piece(column, token)
        self.board = new_board

        # Record the move
        move = Move(
            move_index=len(self.moves),
            column=column,
            landed_at=landing_position,
            token=token,
            player_id=player_id,
            timestamp=datetime.now(UTC)
        )
        self.moves.append(move)

        # Check for game end
        self._check_game_end()

        # Switch turns if game continues
        if self.status == GameStatus.IN_PROGRESS:
            self.current_token = self.current_token.opposite()

        self.updated_at = datetime.now(UTC)
        return move

    def abandon(self) -> None:
        if self.status.is_finished:
            raise ValueError("Cannot abandon a finished game")

        self.status = GameStatus.ABANDONED
        self.finished_at = datetime.now(UTC)
        self.updated_at = self.finished_at

    # Game State Queries

    def get_available_columns(self) -> List[int]:
        if self.status != GameStatus.IN_PROGRESS:
            return []
        return self.board.get_available_columns()

    def get_move_count(self) -> int:
        return len(self.moves)

    def get_last_move(self) -> Optional[Move]:
        return self.moves[-1] if self.moves else None

    def get_duration_seconds(self) -> Optional[float]:
        if not self.started_at:
            return None
        end_time = self.finished_at or datetime.now(UTC)
        return (end_time - self.started_at).total_seconds()

    def is_player_turn(self, player_id: str) -> bool:
        token = self.get_token_for_player(player_id)
        return token == self.current_token if token else False

    # Internal - Game End Detection

    def _check_game_end(self) -> None:
        winning_token = self.board.check_winner()
        if winning_token:
            self._end_game_with_winner(winning_token)
            return

        if self.board.is_full():
            self._end_game_with_draw()
            return

    def _end_game_with_winner(self, winning_token: Token) -> None:
        self.winner = self.get_player_for_token(winning_token)

        if winning_token == Token.PLAYER_ONE:
            self.status = GameStatus.PLAYER_ONE_WIN
        else:
            self.status = GameStatus.PLAYER_TWO_WIN

        self.finished_at = datetime.now(UTC)

    def _end_game_with_draw(self) -> None:
        self.status = GameStatus.DRAW
        self.finished_at = datetime.now(UTC)

    # Serialization

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "board": self.board.to_dict(),
            "playerOne": self.player_one.to_dict(),
            "playerTwo": self.player_two.to_dict(),
            "currentToken": self.current_token.value,
            "currentPlayer": self.get_current_player().to_dict(),
            "status": self.status.value,
            "winner": self.winner.to_dict() if self.winner else None,
            "moveCount": self.get_move_count(),
            "lastMove": self.get_last_move().to_dict() if self.get_last_move() else None,
            "availableColumns": self.get_available_columns(),
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "durationSeconds": self.get_duration_seconds()
        }

    def get_state_snapshot(self) -> dict:
        return {
            "gameId": self.id,
            "board": self.board.to_2d_list(),
            "currentToken": self.current_token.value,
            "moveIndex": self.get_move_count(),
            "availableColumns": self.get_available_columns(),
            "status": self.status.value,
            "playerOneId": self.player_one.id,
            "playerTwoId": self.player_two.id,
            "lastMove": self.get_last_move().to_dict() if self.get_last_move() else None,
            "timestamp": datetime.now(UTC).isoformat()
        }

    def __str__(self) -> str:
        return f"Game {self.id[:8]}: {self.player_one.name} vs {self.player_two.name} - {self.status.value}"
