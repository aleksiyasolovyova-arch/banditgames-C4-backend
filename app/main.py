# app/main.py - Updated with RabbitMQ Publisher
from __future__ import annotations

import uuid
import os
from datetime import datetime
from typing import Dict, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    GameConfig, GameState, MoveRequest, MoveInfo,
    Player, PlayerType, GameStatus
)
from app.game import ConnectFourGame
from app.rabbitmq_publisher import RabbitMQPublisher

GAME_SESSIONS: Dict[str, ConnectFourGame] = {}


# -------------------------------
# Lifespan with RabbitMQ
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize RabbitMQ publisher
    try:
        app.state.rabbitmq = RabbitMQPublisher()
    except Exception as e:
        app.state.rabbitmq = None

    yield  # Application runs here

    # Shutdown
    if app.state.rabbitmq:
        app.state.rabbitmq.close()


app = FastAPI(
    title="Connect Four Backend",
    lifespan=lifespan
)

# -------------------------------
# Middleware
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# Helpers
# -------------------------------
def get_game(game_id: str) -> ConnectFourGame:
    if game_id not in GAME_SESSIONS:
        raise HTTPException(404, "Game not found.")
    return GAME_SESSIONS[game_id]


# -------------------------------
# Endpoints
# -------------------------------
@app.post("/games", response_model=GameState)
def create_game(config: GameConfig):
    """Create a new game"""
    game_id = str(uuid.uuid4())
    game = ConnectFourGame(game_id, config)
    GAME_SESSIONS[game_id] = game

    # Publish game created event if RabbitMQ is available
    if app.state.rabbitmq:
        app.state.rabbitmq.publish_game_created(
            game_id=game_id,
            config=config.model_dump()
        )

    return game.get_state()


@app.get("/games/{game_id}", response_model=GameState)
def get_state(game_id: str):
    """Get current game state"""
    return get_game(game_id).get_state()


@app.get("/games/{game_id}/history", response_model=List[MoveInfo])
def get_history(game_id: str):
    """Get game history"""
    return get_game(game_id).get_history()


@app.post("/games/{game_id}/moves", response_model=GameState)
def make_move(game_id: str, move: MoveRequest):
    """Make a move (human or AI via API call from MCTS)"""
    game = get_game(game_id)

    prev_state = game.get_state()
    acting = move.player or prev_state.current_player

    if acting != prev_state.current_player:
        raise HTTPException(400, f"It is {prev_state.current_player}'s turn.")

    # Make the move
    next_state = game.play_move(move.column)
    reward = next_state.utilities[acting]

    # Publish events based on move type and game state
    if app.state.rabbitmq:
        if acting == Player.PLAYER1:
            # Human move was made
            app.state.rabbitmq.publish_human_move(
                game_id=game_id,
                player=acting.value,
                column=move.column,
                board=next_state.board,
                current_player=next_state.current_player.value,
                status=next_state.status.value
            )

            # If next player is CPU and game not over, publish AI needed event
            if (next_state.current_player == Player.PLAYER2 and
                    game.config.player2_type == PlayerType.CPU and
                    next_state.status == GameStatus.IN_PROGRESS):
                app.state.rabbitmq.publish_ai_move_needed(
                    game_id=game_id,
                    board=next_state.board,
                    current_player=2
                )

        # Check if game ended
        if next_state.status != GameStatus.IN_PROGRESS:
            winner = next_state.winner.value if next_state.winner else "draw"
            app.state.rabbitmq.publish_game_ended(
                game_id=game_id,
                winner=winner,
                final_board=next_state.board
            )

    return next_state

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "games_active": len(GAME_SESSIONS),
        "rabbitmq_connected": app.state.rabbitmq is not None
    }


@app.delete("/games/{game_id}")
def delete_game(game_id: str):
    """Delete a game"""
    if game_id not in GAME_SESSIONS:
        raise HTTPException(404, "Game not found")

    del GAME_SESSIONS[game_id]
    return {"message": "Game deleted"}


@app.post("/games/ai-vs-ai")
async def create_ai_vs_ai_game():
    """Create and run an AI vs AI game"""

    # Create game with both players as CPU
    config = GameConfig(
        player1_type=PlayerType.CPU,
        player2_type=PlayerType.CPU
    )
    game_id = str(uuid.uuid4())
    game = ConnectFourGame(game_id, config)
    GAME_SESSIONS[game_id] = game

    # Publish event for MCTS to handle both players
    if app.state.rabbitmq:
        app.state.rabbitmq.publish_event('game.ai_vs_ai.created', {
            'event_id': str(uuid.uuid4()),
            'event_type': 'ai_vs_ai.created',
            'game_id': game_id,
            'skill_level_p1': 'medium',
            'skill_level_p2': 'expert'
        })

    return {"game_id": game_id, "message": "AI vs AI game started"}
