# app/main.py
from __future__ import annotations

import uuid
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.schemas import (
    GameConfig, GameState, MoveRequest, MoveInfo,
    TransitionLogEntry, Player, PlayerType, GameStatus
)
from app.game import ConnectFourGame
from app.logger import TransitionLogger

# Try to import MCTS - check multiple possible locations
AI_AVAILABLE = False
ai_manager = None

# Try different import paths
try:
    # First try: MCTS mounted as volume at /mcts
    sys.path.insert(0, '/mcts')
    from ai_manager import AIManager
    from ConnectState import ConnectState

    AI_AVAILABLE = True
    ai_manager = AIManager()
    print("[OK] MCTS loaded from /mcts")
except ImportError:
    try:
        # Second try: MCTS in sibling directory (development)
        mcts_path = Path(__file__).parent.parent.parent / 'connect4-player' / 'src'
        if mcts_path.exists():
            sys.path.insert(0, str(mcts_path))
            from ai_manager import AIManager
            from ConnectState import ConnectState

            AI_AVAILABLE = True
            ai_manager = AIManager()
            print(f"[OK] MCTS loaded from {mcts_path}")
    except ImportError:
        print("[WARNING] MCTS not available - using random moves")

GAME_SESSIONS: Dict[str, ConnectFourGame] = {}
executor = ThreadPoolExecutor(max_workers=4)


# -------------------------------
# Lifespan (instead of on_event)
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs("logs", exist_ok=True)
    app.state.logger = TransitionLogger("logs/game_transitions.jsonl")
    print("Logger initialized.")
    print(f"AI Available: {AI_AVAILABLE}")

    yield  # Application runs here

    # Shutdown
    print("Shutting down...")
    executor.shutdown(wait=True)


app = FastAPI(
    title="Connect Four Backend with AI",
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


def game_to_connect_state(game: ConnectFourGame) -> Optional['ConnectState']:
    """Convert game state to MCTS format"""
    if not AI_AVAILABLE:
        return None

    current_player = 1 if game.current_player == Player.PLAYER1 else 2

    return ConnectState(
        board=game.board,
        rows=game.rows,
        cols=game.cols,
        connect=game.config.connect,
        current_player=current_player,
        empty_token=game.config.empty_token,
        player1_token=game.config.player1_token,
        player2_token=game.config.player2_token
    )


# -------------------------------
# Endpoints
# -------------------------------
@app.post("/games", response_model=GameState)
def create_game(config: GameConfig):
    game_id = str(uuid.uuid4())
    game = ConnectFourGame(game_id, config)
    GAME_SESSIONS[game_id] = game

    # Initialize AI if vs CPU
    if config.player2_type == PlayerType.CPU and AI_AVAILABLE:
        ai_manager.get_agent(game_id, 'medium')  # Default difficulty

    return game.get_state()


@app.get("/games/{game_id}", response_model=GameState)
def get_state(game_id: str):
    return get_game(game_id).get_state()


@app.get("/games/{game_id}/history", response_model=List[MoveInfo])
def get_history(game_id: str):
    return get_game(game_id).get_history()


@app.post("/games/{game_id}/moves", response_model=GameState)
async def make_move(game_id: str, move: MoveRequest):
    """Make a human move and get automatic AI response if applicable"""
    game = get_game(game_id)
    logger: TransitionLogger = app.state.logger

    prev_state = game.get_state()
    acting = move.player or prev_state.current_player

    if acting != prev_state.current_player:
        raise HTTPException(400, f"It is {prev_state.current_player}'s turn.")

    # Make human move
    next_state = game.play_move(move.column)
    reward = next_state.utilities[acting]

    # Log human move
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

    # Check if game ended after human move
    if next_state.status != GameStatus.IN_PROGRESS:
        # Update difficulty if game ended
        if AI_AVAILABLE:
            player_won = next_state.winner == Player.PLAYER1
            ai_manager.update_performance(game_id, player_won)
        return next_state

    # AUTO AI MOVE: If next player is CPU, make AI move automatically
    if next_state.current_player == Player.PLAYER2 and game.config.player2_type == PlayerType.CPU:
        # Save state before AI move
        ai_prev_state = next_state

        # Get AI move
        if AI_AVAILABLE:
            state = game_to_connect_state(game)
            loop = asyncio.get_event_loop()
            column, stats = await loop.run_in_executor(
                executor,
                ai_manager.get_ai_move,
                game_id,
                state
            )
        else:
            column = game.select_cpu_action()
            stats = {"method": "random"}

        # Make AI move
        next_state = game.play_move(column)

        # Log AI move
        ai_log_entry = TransitionLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            game_id=game_id,
            move_index=next_state.turn_index - 1,
            player=Player.PLAYER2,
            action={"column": column},
            prev_state=ai_prev_state,
            next_state=next_state,
            reward=next_state.utilities[Player.PLAYER2]
        )
        logger.log(ai_log_entry.model_dump(mode="json"))

        # Add AI move info to response
        next_state_dict = next_state.model_dump()
        next_state_dict['ai_move'] = {
            'column': column,
            'stats': stats
        }

        # Check if game ended after AI move
        if AI_AVAILABLE and next_state.status != GameStatus.IN_PROGRESS:
            player_won = next_state.winner == Player.PLAYER1
            ai_manager.update_performance(game_id, player_won)

        # Return the dict with AI info
        return next_state_dict

    return next_state

@app.post("/games/{game_id}/moves/auto", response_model=GameState)
async def auto_move(game_id: str):
    game = get_game(game_id)
    logger: TransitionLogger = app.state.logger

    prev = game.get_state()

    if game.config.player2_type != PlayerType.CPU:
        raise HTTPException(400, "Game is not vs CPU.")

    if prev.current_player != Player.PLAYER2:
        raise HTTPException(400, "Not CPU's turn.")

    # Get AI move using MCTS or fallback to random
    if AI_AVAILABLE:
        state = game_to_connect_state(game)
        loop = asyncio.get_event_loop()
        column, stats = await loop.run_in_executor(
            executor,
            ai_manager.get_ai_move,
            game_id,
            state
        )
    else:
        # Fallback to random if MCTS not available
        column = game.select_cpu_action()
        stats = {"method": "random"}

    next_state = game.play_move(column)
    reward = next_state.utilities[Player.PLAYER2]

    log_entry = TransitionLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        game_id=game_id,
        move_index=next_state.turn_index - 1,
        player=Player.PLAYER2,
        action={"column": column, "ai_stats": stats},
        prev_state=prev,
        next_state=next_state,
        reward=reward,
    )

    logger.log(log_entry.model_dump(mode="json"))

    # Add AI statistics to response
    response = next_state.model_dump()
    response['ai_stats'] = stats

    return response


# -------------------------------
# AI-specific endpoints
# -------------------------------
@app.post("/games/{game_id}/difficulty")
def set_difficulty(game_id: str, skill: str):
    """Manually set AI difficulty level"""
    if not AI_AVAILABLE:
        raise HTTPException(400, "AI not available")

    if skill not in ['easy', 'medium', 'hard', 'expert']:
        raise HTTPException(400, "Invalid skill level. Choose: easy, medium, hard, expert")

    game = get_game(game_id)
    if game.config.player2_type != PlayerType.CPU:
        raise HTTPException(400, "Not a CPU game")

    ai_manager.get_agent(game_id, skill)
    return {"message": f"Difficulty set to {skill}"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "ai_available": AI_AVAILABLE,
        "games_active": len(GAME_SESSIONS)
    }


@app.get("/ai/status")
def ai_status():
    """Check AI system status"""
    if AI_AVAILABLE:
        return {
            "available": True,
            "skill_levels": ['easy', 'medium', 'hard', 'expert'],
            "features": ["dynamic_difficulty", "concurrent_games", "tournaments"]
        }
    else:
        return {
            "available": False,
            "message": "MCTS not found. Using random moves for CPU players."
        }


@app.post("/ai/tournament")
async def run_tournament(games: int = 10, skills: List[str] = None):
    """Run AI vs AI tournament for testing skill levels"""
    if not AI_AVAILABLE:
        raise HTTPException(400, "AI not available")

    if skills is None:
        skills = ['easy', 'medium', 'hard', 'expert']

    results = []

    for i in range(games):
        import random
        skill1 = random.choice(skills)
        skill2 = random.choice(skills)

        # Create game with both players as CPU
        game_id = str(uuid.uuid4())
        config = GameConfig(
            player1_type=PlayerType.CPU,
            player2_type=PlayerType.CPU
        )
        game = ConnectFourGame(game_id, config)
        GAME_SESSIONS[game_id] = game

        # Create AI agents
        agent1 = ai_manager.get_agent(f"{game_id}_p1", skill1)
        agent2 = ai_manager.get_agent(f"{game_id}_p2", skill2)

        # Play game
        moves = 0
        while game.status == GameStatus.IN_PROGRESS and moves < 42:
            state = game_to_connect_state(game)

            if game.current_player == Player.PLAYER1:
                move = agent1.get_move(state)
            else:
                move = agent2.get_move(state)

            game.play_move(move)
            moves += 1

        # Record result
        results.append({
            'game': i + 1,
            'player1_skill': skill1,
            'player2_skill': skill2,
            'winner': game.winner.value if game.winner else 'draw',
            'moves': moves
        })

        # Cleanup
        ai_manager.cleanup(f"{game_id}_p1")
        ai_manager.cleanup(f"{game_id}_p2")
        del GAME_SESSIONS[game_id]

    return {
        'tournament_complete': True,
        'total_games': games,
        'results': results
    }


@app.delete("/games/{game_id}")
def delete_game(game_id: str):
    """Delete game and cleanup resources"""
    if game_id not in GAME_SESSIONS:
        raise HTTPException(404, "Game not found")

    if AI_AVAILABLE:
        ai_manager.cleanup(game_id)

    del GAME_SESSIONS[game_id]
    return {"message": "Game deleted"}