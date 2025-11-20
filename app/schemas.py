# app/schemas.py
from __future__ import annotations

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class Player(str, Enum):
    PLAYER1 = "player1"
    PLAYER2 = "player2"


class PlayerType(str, Enum):
    HUMAN = "human"
    CPU = "cpu"


class GameStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    WIN = "win"
    DRAW = "draw"


class GameConfig(BaseModel):
    rows: int = Field(6, ge=4)
    cols: int = Field(7, ge=4)
    connect: int = Field(4, ge=3)
    empty_token: str = "."
    player1_token: str = "X"
    player2_token: str = "O"
    player1_type: PlayerType = PlayerType.HUMAN
    player2_type: PlayerType = PlayerType.CPU
    starting_player: Player = Player.PLAYER1


class MoveInfo(BaseModel):
    move_index: int
    player: Player
    column: int
    row: int


class GameState(BaseModel):
    game_id: str
    config: GameConfig
    board: List[List[str]]
    current_player: Player
    turn_index: int
    legal_actions: List[int]
    status: GameStatus
    winner: Optional[Player] = None
    last_move: Optional[MoveInfo] = None
    utilities: Dict[Player, float]
    created_at: str


class MoveRequest(BaseModel):
    column: int = Field(..., ge=0)
    player: Optional[Player] = None


class TransitionLogEntry(BaseModel):
    timestamp: str
    game_id: str
    move_index: int
    player: Player
    action: Dict[str, Any]
    prev_state: GameState
    next_state: GameState
    reward: float
