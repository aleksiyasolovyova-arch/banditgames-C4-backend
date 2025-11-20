# app/main.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    GameConfig, GameState, MoveRequest, MoveInfo,
    TransitionLogEntry, Player, PlayerType
)
from .game import ConnectFourGame
from .logger import TransitionLogger


app = FastAPI(title="Connect Four Backend")

GAME_SESSIONS: Dict[str, ConnectFourGame] = {}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    app.state.logger = TransitionLogger("logs/game_transitions.jsonl")


def get_game(game_id: str) -> ConnectFourGame:
    if game_id not in GAME_SESSIONS:
        raise HTTPException(404, "Game not found.")
    return GAME_SESSIONS[game_id]


@app.post("/games", response_model=GameState)
def create_game(config: GameConfig):
    game_id = str(uuid.uuid4())
    game = ConnectFourGame(game_id, config)
    GAME_SESSIONS[game_id] = game
    return game.get_state()


@app.get("/games/{game_id}", response_model=GameState)
def get_state(game_id: str):
    return get_game(game_id).get_state()


@app.get("/games/{game_id}/history", response_model=List[MoveInfo])
def get_history(game_id: str):
    return get_game(game_id).get_history()


@app.post("/games/{game_id}/moves", response_model=GameState)
def make_move(game_id: str, move: MoveRequest):
    game = get_game(game_id)
    logger: TransitionLogger = app.state.logger

    prev_state = game.get_state()
    acting = move.player or prev_state.current_player

    if acting != prev_state.current_player:
        raise HTTPException(400, f"It is {prev_state.current_player}'s turn.")

    next_state = game.play_move(move.column)
    reward = next_state.utilities[acting]

    log_entry = TransitionLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        game_id=game_id,
        move_index=next_state.turn_index - 1,
        player=acting,
        action={"column": move.column},
        prev_state=prev_state,
        next_state=next_state,
        reward=reward,
    )

    logger.log(log_entry.model_dump(mode="json"))
    return next_state


@app.post("/games/{game_id}/moves/auto", response_model=GameState)
def auto_move(game_id: str):
    game = get_game(game_id)
    logger: TransitionLogger = app.state.logger

    prev = game.get_state()

    if game.config.player2_type != PlayerType.CPU:
        raise HTTPException(400, "Game is not vs CPU.")

    if prev.current_player != Player.PLAYER2:
        raise HTTPException(400, "Not CPU's turn.")

    column = game.select_cpu_action()
    next_state = game.play_move(column)
    reward = next_state.utilities[Player.PLAYER2]

    log_entry = TransitionLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        game_id=game_id,
        move_index=next_state.turn_index - 1,
        player=Player.PLAYER2,
        action={"column": column},
        prev_state=prev,
        next_state=next_state,
        reward=reward,
    )

    logger.log(log_entry.model_dump(mode="json"))
    return next_state
