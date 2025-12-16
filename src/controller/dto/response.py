"""
Response Data Transfer Objects.
Presentation layer models.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from ...domain import Game


class PlayerResponse(BaseModel):
    id: str
    name: str

    class Config:
        populate_by_name = True


class MoveResponse(BaseModel):
    move_index: int = Field(..., alias="moveIndex")
    column: int
    landed_at: Dict[str, int] = Field(..., alias="landedAt")
    token: str
    player_id: str = Field(..., alias="playerId")
    timestamp: str

    class Config:
        populate_by_name = True


class BoardResponse(BaseModel):
    rows: int
    cols: int
    grid: List[List[str]]
    available_columns: List[int] = Field(..., alias="availableColumns")

    class Config:
        populate_by_name = True


class GameResponse(BaseModel):
    id: str
    board: BoardResponse
    player_one: Optional[PlayerResponse] = Field(None, alias="playerOne")
    player_two: Optional[PlayerResponse] = Field(None, alias="playerTwo")
    current_token: str = Field(..., alias="currentToken")
    current_player: Optional[PlayerResponse] = Field(None, alias="currentPlayer")
    status: str
    winner: Optional[PlayerResponse] = None
    move_count: int = Field(..., alias="moveCount")
    last_move: Optional[MoveResponse] = Field(None, alias="lastMove")
    available_columns: List[int] = Field(..., alias="availableColumns")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    started_at: Optional[str] = Field(None, alias="startedAt")
    finished_at: Optional[str] = Field(None, alias="finishedAt")
    duration_seconds: Optional[float] = Field(None, alias="durationSeconds")

    class Config:
        populate_by_name = True

    @classmethod
    def from_domain(cls, game: "Game") -> "GameResponse":
        game_dict = game.to_dict()

        if game_dict["board"]:
            game_dict["board"] = BoardResponse(**game_dict["board"])

        if game_dict["playerOne"]:
            game_dict["playerOne"] = PlayerResponse(**game_dict["playerOne"])

        if game_dict["playerTwo"]:
            game_dict["playerTwo"] = PlayerResponse(**game_dict["playerTwo"])

        if game_dict["currentPlayer"]:
            game_dict["currentPlayer"] = PlayerResponse(**game_dict["currentPlayer"])

        if game_dict["winner"]:
            game_dict["winner"] = PlayerResponse(**game_dict["winner"])

        if game_dict["lastMove"]:
            game_dict["lastMove"] = MoveResponse(**game_dict["lastMove"])

        return cls(**game_dict)


class GameListResponse(BaseModel):
    games: List[GameResponse]
    total: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = Field(None, alias="errorCode")

    class Config:
        populate_by_name = True
