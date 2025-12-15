# app/game.py
# app/game.py
"""
 Connect Four Game with comprehensive state tracking.
Supports gameplay logging, replay, and ML training data collection.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import List, Optional, Dict, Tuple
import random
import hashlib
import json

from app.schemas import (
    GameConfig, Player, PlayerType, GameStatus, SkillLevel,
    GameState, MoveInfo, MCTSStatistics
)


class ConnectFourGame:
    def __init__(self, game_id: str, config: Optional[GameConfig] = None):
        self.id = game_id
        self.config = config or GameConfig()

        self.rows = self.config.rows
        self.cols = self.config.cols

        # Initialize empty board
        self.board: List[List[str]] = [
            [self.config.empty_token for _ in range(self.cols)]
            for _ in range(self.rows)
        ]

        self.current_player = self.config.starting_player
        self.status = GameStatus.IN_PROGRESS
        self.winner: Optional[Player] = None
        self.turn_index = 0
        self.move_history: List[MoveInfo] = []

        # Timestamps
        self.created_at = datetime.now(UTC).isoformat()
        self.updated_at = self.created_at
        self.started_at: Optional[str] = None
        self.ended_at: Optional[str] = None

        # Last MCTS stats (if AI made the move)
        self.last_mcts_stats: Optional[MCTSStatistics] = None

    # Utility Methods
    def _token_for(self, player: Player) -> str:
        """Get token for a player"""
        return (
            self.config.player1_token if player == Player.PLAYER1
            else self.config.player2_token
        )

    def _player_for_token(self, token: str) -> Optional[Player]:
        """Get player for a token"""
        if token == self.config.player1_token:
            return Player.PLAYER1
        elif token == self.config.player2_token:
            return Player.PLAYER2
        return None

    def _other(self, player: Player) -> Player:
        """Get the other player"""
        return Player.PLAYER2 if player == Player.PLAYER1 else Player.PLAYER1

    def _copy_board(self) -> List[List[str]]:
        """Create a deep copy of the board"""
        return [row[:] for row in self.board]

    def _compute_state_hash(self) -> str:
        """Compute unique hash for current board state"""
        board_str = json.dumps(self.board, sort_keys=True)
        player_str = self.current_player.value
        hash_input = f"{board_str}:{player_str}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]

    # ============================================================================
    # Public API - State Queries
    # ============================================================================

    def legal_actions(self) -> List[int]:
        """Get list of valid column indices for next move"""
        if self.status != GameStatus.IN_PROGRESS:
            return []
        return [
            c for c in range(self.cols)
            if self.board[0][c] == self.config.empty_token
        ]

    def is_valid_action(self, column: int) -> bool:
        """Check if a column is a valid move"""
        return column in self.legal_actions()

    def is_terminal(self) -> bool:
        """Check if game is in terminal state"""
        return self.status != GameStatus.IN_PROGRESS

    # Public API - Game Actions
    def play_move(
            self,
            column: int,
            thinking_time_ms: Optional[int] = None,
            mcts_stats: Optional[MCTSStatistics] = None
    ) -> GameState:
        """
        Play a move in the specified column.

        Args:
            column: Column index to place piece
            thinking_time_ms: Time taken to make this move (for logging)
            mcts_stats: MCTS statistics if this was an AI move

        Returns:
            GameState after the move

        Raises:
            ValueError: If game is finished or move is invalid
        """
        if self.status != GameStatus.IN_PROGRESS:
            raise ValueError("Game is already finished.")

        if not self.is_valid_action(column):
            raise ValueError(f"Invalid move: column {column} is not a legal action.")

        # Record start time if first move
        if self.turn_index == 0:
            self.started_at = datetime.now(UTC).isoformat()

        player = self.current_player
        token = self._token_for(player)

        # Drop the piece
        row = self._drop_piece(column, token)

        # Record the move
        timestamp = datetime.now(UTC).isoformat()
        move = MoveInfo(
            move_index=self.turn_index,
            player=player,
            column=column,
            row=row,
            timestamp=timestamp,
            thinking_time_ms=thinking_time_ms
        )

        self.move_history.append(move)
        self.turn_index += 1
        self.updated_at = timestamp

        # Store MCTS stats if provided
        self.last_mcts_stats = mcts_stats

        # Check game outcome
        if self._has_winning_line(token):
            self.status = GameStatus.WIN
            self.winner = player
            self.ended_at = timestamp
        elif not self.legal_actions():
            self.status = GameStatus.DRAW
            self.ended_at = timestamp
        else:
            self.current_player = self._other(player)

        return self.get_state()

    def select_cpu_action(self) -> int:
        """Select a random action for CPU (fallback when MCTS not used)"""
        legal = self.legal_actions()
        if not legal:
            raise ValueError("No legal actions available.")
        return random.choice(legal)

    def abandon_game(self) -> GameState:
        """Mark game as abandoned"""
        self.status = GameStatus.ABANDONED
        self.ended_at = datetime.now(UTC).isoformat()
        self.updated_at = self.ended_at
        return self.get_state()

    # Public API - State Retrieval
    def get_state(self, include_history: bool = False) -> GameState:
        """
        Get comprehensive current game state.

        Args:
            include_history: Whether to include complete move history

        Returns:
            Complete GameState object
        """
        legal = self.legal_actions()
        utilities = self._utilities()
        last_move = self.move_history[-1] if self.move_history else None

        state = GameState(
            game_id=self.id,
            config=self.config,
            board=self._copy_board(),
            current_player=self.current_player,
            turn_index=self.turn_index,
            legal_actions=legal,
            status=self.status,
            winner=self.winner,
            last_move=last_move,
            utilities=utilities,
            heuristic_score=self._evaluate_position(),
            move_history=list(self.move_history) if include_history else None,
            created_at=self.created_at,
            updated_at=self.updated_at,
            state_hash=self._compute_state_hash(),
            mcts_stats=self.last_mcts_stats
        )

        return state

    def get_state_at_move(self, move_index: int) -> Optional[GameState]:
        """
        Reconstruct game state at a specific move index.

        Args:
            move_index: The move index to reconstruct (0 = initial state)

        Returns:
            GameState at that point, or None if invalid index
        """
        if move_index < 0 or move_index > len(self.move_history):
            return None

        # Create a temporary game and replay moves
        temp_game = ConnectFourGame(self.id, self.config)

        for i, move in enumerate(self.move_history[:move_index]):
            temp_game.play_move(
                move.column,
                thinking_time_ms=move.thinking_time_ms
            )

        return temp_game.get_state()

    def get_history(self) -> List[MoveInfo]:
        """Get complete move history"""
        return list(self.move_history)

    def get_duration_seconds(self) -> Optional[float]:
        """Get game duration in seconds"""
        if not self.started_at:
            return None

        end = self.ended_at or datetime.now(UTC).isoformat()
        start_dt = datetime.fromisoformat(self.started_at.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))

        return (end_dt - start_dt).total_seconds()

    # Internal - Board Operations
    def _drop_piece(self, column: int, token: str) -> int:
        """Drop a piece in the column and return the row it landed in"""
        for r in range(self.rows - 1, -1, -1):
            if self.board[r][column] == self.config.empty_token:
                self.board[r][column] = token
                return r
        raise RuntimeError(f"No space in column {column}.")

    # Internal - Evaluation
    def _utilities(self) -> Dict[Player, float]:
        """Calculate utility values for each player"""
        if self.status == GameStatus.IN_PROGRESS:
            return {Player.PLAYER1: 0.0, Player.PLAYER2: 0.0}

        if self.status == GameStatus.DRAW:
            return {Player.PLAYER1: 0.0, Player.PLAYER2: 0.0}

        if self.status == GameStatus.ABANDONED:
            return {Player.PLAYER1: 0.0, Player.PLAYER2: 0.0}

        # WIN status
        win = 1.0
        lose = -1.0
        return {
            Player.PLAYER1: win if self.winner == Player.PLAYER1 else lose,
            Player.PLAYER2: win if self.winner == Player.PLAYER2 else lose,
        }

    def _evaluate_position(self) -> float:
        """
        Heuristic evaluation of current position.
        Returns score from current player's perspective.
        Positive = good for current player, Negative = bad.
        """
        if self.status == GameStatus.WIN:
            return 1000.0 if self.winner == self.current_player else -1000.0
        if self.status in (GameStatus.DRAW, GameStatus.ABANDONED):
            return 0.0

        score = 0.0

        # Evaluate potential lines for each player
        my_token = self._token_for(self.current_player)
        opp_token = self._token_for(self._other(self.current_player))

        # Check all possible lines
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

        for r in range(self.rows):
            for c in range(self.cols):
                for dr, dc in directions:
                    line_score = self._evaluate_line(r, c, dr, dc, my_token, opp_token)
                    score += line_score

        return score

    def _evaluate_line(
            self,
            start_r: int,
            start_c: int,
            dr: int,
            dc: int,
            my_token: str,
            opp_token: str
    ) -> float:
        """Evaluate a potential line of 'connect' length"""
        need = self.config.connect

        # Check if line fits on board
        end_r = start_r + (need - 1) * dr
        end_c = start_c + (need - 1) * dc

        if not (0 <= end_r < self.rows and 0 <= end_c < self.cols):
            return 0.0

        my_count = 0
        opp_count = 0
        empty_count = 0

        for i in range(need):
            r = start_r + i * dr
            c = start_c + i * dc
            cell = self.board[r][c]

            if cell == my_token:
                my_count += 1
            elif cell == opp_token:
                opp_count += 1
            else:
                empty_count += 1

        # Mixed line (both players have pieces) = no potential
        if my_count > 0 and opp_count > 0:
            return 0.0

        # Score based on number of pieces in line
        if my_count > 0:
            return 10 ** (my_count - 1)  # 1, 10, 100 for 1, 2, 3 pieces
        elif opp_count > 0:
            return -(10 ** (opp_count - 1))

        return 0.0

    # Internal - Win Detection
    def _has_winning_line(self, token: str) -> bool:
        """Check if the given token has a winning line"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        need = self.config.connect

        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] != token:
                    continue
                for dr, dc in directions:
                    if self._count_in_direction(r, c, dr, dc, token) >= need:
                        return True
        return False

    def _count_in_direction(self, r: int, c: int, dr: int, dc: int, token: str) -> int:
        """Count consecutive tokens in a direction"""
        count = 0
        while 0 <= r < self.rows and 0 <= c < self.cols:
            if self.board[r][c] != token:
                break
            count += 1
            r += dr
            c += dc
        return count

    # Serialization
    def to_dict(self) -> Dict:
        """Convert game to dictionary for serialization"""
        return {
            'game_id': self.id,
            'config': self.config.model_dump(),
            'board': self._copy_board(),
            'current_player': self.current_player.value,
            'status': self.status.value,
            'winner': self.winner.value if self.winner else None,
            'turn_index': self.turn_index,
            'move_history': [m.model_dump() for m in self.move_history],
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ConnectFourGame':
        """Reconstruct game from dictionary"""
        config = GameConfig(**data['config'])
        game = cls(data['game_id'], config)

        game.board = data['board']
        game.current_player = Player(data['current_player'])
        game.status = GameStatus(data['status'])
        game.winner = Player(data['winner']) if data['winner'] else None
        game.turn_index = data['turn_index']
        game.move_history = [MoveInfo(**m) for m in data['move_history']]
        game.created_at = data['created_at']
        game.updated_at = data['updated_at']
        game.started_at = data.get('started_at')
        game.ended_at = data.get('ended_at')

        return game