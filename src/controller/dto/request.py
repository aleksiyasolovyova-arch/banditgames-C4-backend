"""
Request Data Transfer Objects.
"""
from pydantic import BaseModel, Field


class PlayerRequest(BaseModel):
    id: str
    name: str


class CreateGameRequest(BaseModel):
    game_id: str = Field(..., alias="gameId")

    rows: int = Field(default=6, ge=4, le=10)
    cols: int = Field(default=7, ge=4, le=10)

    player_one: PlayerRequest = Field(..., alias="playerOne")
    player_two: PlayerRequest = Field(..., alias="playerTwo")

    class Config:
        populate_by_name = True


class MakeMoveRequest(BaseModel):
    player_id: str = Field(..., alias="playerId")
    column: int = Field(..., ge=0)

    class Config:
        populate_by_name = True
