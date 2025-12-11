"""
Connect Four Backend API with comprehensive logging and replay support.
"""

from __future__ import annotations

import uuid

import os

import time

from datetime import datetime, UTC

from typing import Dict, List, Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Body

from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    GameConfig, GameState, MoveRequest, MoveInfo,
    Player, PlayerType, GameStatus, SkillLevel,
    MCTSStatistics, TransitionLogEntry,
    SelfPlayConfig, SelfPlaySession,
    GameReplay, ReplayFrame,
    DatasetExportRequest, DatasetExportResult
)

from app.game import ConnectFourGame

from app.rabbitmq_publisher import RabbitMQPublisher

from app.db_logger import get_db_logger, close_db_logger, DatabaseLogger

from app.player_performance_manager import PlayerPerformance

import logging

logger = logging.getLogger(__name__)

# In-memory game sessions
GAME_SESSIONS: Dict[str, ConnectFourGame] = {}


# DDA HELPER FUNCTIONS
def calculate_adjusted_difficulty(current_skill: SkillLevel, perf: PlayerPerformance) -> SkillLevel:
    """
    Calculate the adjusted difficulty based on performance.

    Args:
        current_skill: Current skill level
        perf: Player performance object

    Returns:
        Adjusted skill level
    """
    skill_progression = [SkillLevel.EASY, SkillLevel.MEDIUM, SkillLevel.HARD, SkillLevel.EXPERT]

    try:
        current_index = skill_progression.index(current_skill)
    except ValueError:
        print(f"Invalid skill level: {current_skill}, keeping current")
        return current_skill

    if perf.should_increase_difficulty():
        new_index = min(current_index + 1, len(skill_progression) - 1)
        new_skill = skill_progression[new_index]
        if new_skill != current_skill:
            print(f"Difficulty increased: {current_skill.value} → {new_skill.value}")
        return new_skill

    elif perf.should_decrease_difficulty():
        new_index = max(current_index - 1, 0)
        new_skill = skill_progression[new_index]
        if new_skill != current_skill:
            print(f"Difficulty decreased: {current_skill.value} → {new_skill.value}")
        return new_skill

    return current_skill


def load_adjusted_difficulty_for_player(player1_id: str, current_skill: SkillLevel, db: DatabaseLogger) -> SkillLevel:
    """
    Load the adjusted difficulty from the database for this player.

    Args:
        player1_id: Player ID
        current_skill: Current skill level to use as default
        db: Database logger

    Returns:
        Adjusted skill level from database, or current_skill if none found
    """
    if not db:
        return current_skill

    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT current_opponent_skill FROM player_performance
                    WHERE player_id = %s
                    ORDER BY updated_at DESC LIMIT 1
                """, (player1_id,))
                row = cur.fetchone()

                if row and row[0]:
                    adjusted_skill_str = row[0]
                    try:
                        adjusted_skill = SkillLevel(adjusted_skill_str)
                        if adjusted_skill != current_skill:
                            print(f"Loaded adjusted difficulty from DB: {adjusted_skill.value} (was {current_skill.value})")
                        return adjusted_skill
                    except ValueError:
                        print(f"Invalid skill level in DB: {adjusted_skill_str}, using {current_skill.value}")
                        return current_skill
    except Exception as e:
        print(f"Failed to load adjusted difficulty: {e}")
        return current_skill

    return current_skill


def connect_rabbitmq_with_retry(max_retries: int = 5, retry_delay: float = 2.0) -> Optional[RabbitMQPublisher]:
    """Connect to RabbitMQ with retry logic"""
    for attempt in range(max_retries):
        try:
            publisher = RabbitMQPublisher()
            print(f"RabbitMQ connected successfully on attempt {attempt + 1}")
            return publisher
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"RabbitMQ connection attempt {attempt + 1} failed: {e}")
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"RabbitMQ connection failed after {max_retries} attempts: {e}")
                return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    app.state.rabbitmq = connect_rabbitmq_with_retry(max_retries=10, retry_delay=3.0)
    if not app.state.rabbitmq:
        print("WARNING: RabbitMQ not available - AI moves will not work")

    try:
        app.state.db_logger = get_db_logger()
        if app.state.db_logger:
            print("Database logger initialized successfully")
    except Exception as e:
        print(f"Database logger not available: {e}")
        app.state.db_logger = None

    # Initialize Player Performance Manager for DDA
    try:
        from app.player_performance_manager import PlayerPerformanceManager
        app.state.performance_manager = PlayerPerformanceManager()
        print("Player Performance Manager initialized for DDA")
    except Exception as e:
        print(f"Player Performance Manager initialization FAILED: {e}")
        app.state.performance_manager = None

    yield # Application runs here

    # Shutdown
    if app.state.rabbitmq:
        app.state.rabbitmq.close()
    close_db_logger()

app = FastAPI(title="Connect Four Backend", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_game(game_id: str) -> ConnectFourGame:
    """Get game by ID or raise 404"""
    if game_id not in GAME_SESSIONS:
        raise HTTPException(404, "Game not found.")
    return GAME_SESSIONS[game_id]

def get_db() -> Optional[DatabaseLogger]:
    """Get database logger if available"""
    return getattr(app.state, 'db_logger', None)

# ============================================================================
# GAME ENDPOINTS
# ============================================================================

@app.post("/games", response_model=GameState)
def create_game(config: GameConfig):
    """Create a new game with specified configuration"""
    game_id = str(uuid.uuid4())
    game = ConnectFourGame(game_id, config)
    GAME_SESSIONS[game_id] = game

    db = get_db()
    if db:
        try:
            # Get or create player IDs
            player1_id = db.get_or_create_player(
                config.player1_type,
                config.player1_skill_level
            )
            player2_id = db.get_or_create_player(
                config.player2_type,
                config.player2_skill_level
            )

            db.log_game_created(game_id, config)

            # Register player for DDA tracking
            perf_manager = getattr(app.state, 'performance_manager', None)
            if perf_manager and config.player1_type == PlayerType.HUMAN:
                print(f"Registering player {player1_id} for game {game_id}")

                # Register player and load their history from database
                perf_manager.register_player(game_id, player1_id, db)
                print(f"Player {player1_id} registered, mapping: {perf_manager.player_mapping}")

                if config.player2_type == PlayerType.CPU and config.player2_skill_level:
                    adjusted_skill = load_adjusted_difficulty_for_player(
                        player1_id,
                        config.player2_skill_level,
                        db
                    )
                    if adjusted_skill != config.player2_skill_level:
                        print(f" Updating game config AI difficulty: {config.player2_skill_level.value} → {adjusted_skill.value}")
                        config.player2_skill_level = adjusted_skill
                        game.config.player2_skill_level = adjusted_skill

        except Exception as e:
            print(f"DB logging error: {e}")
            import traceback
            traceback.print_exc()

    # Publish game created event
    if app.state.rabbitmq:
        app.state.rabbitmq.publish_game_created(
            game_id=game_id,
            config=config.model_dump()
        )

    return game.get_state()

@app.get("/games/{game_id}", response_model=GameState)
def get_state(game_id: str, include_history: bool = False):
    """Get current game state"""
    game = get_game(game_id)
    return game.get_state(include_history=include_history)

@app.get("/games/{game_id}/history", response_model=List[MoveInfo])
def get_history(game_id: str):
    """Get complete move history for a game"""
    return get_game(game_id).get_history()

@app.delete("/games/{game_id}")
def delete_game(game_id: str):
    """Delete a game"""
    if game_id not in GAME_SESSIONS:
        raise HTTPException(404, "Game not found")
    del GAME_SESSIONS[game_id]
    return {"message": "Game deleted", "game_id": game_id}

@app.post("/games/{game_id}/moves", response_model=GameState)
def make_move(game_id: str, request: MoveRequest):
    """Make a move in the game"""
    game = get_game(game_id)
    prev_state = game.get_state()
    acting = request.player or prev_state.current_player

    if acting != prev_state.current_player:
        raise HTTPException(400, f"It is {prev_state.current_player.value}'s turn.")

    next_state = game.play_move(
        request.column,
        thinking_time_ms=request.thinking_time_ms,
        mcts_stats=request.mcts_stats
    )

    # RECORD HUMAN MOVE TIME FOR IN-GAME DDA (IMMEDIATELY AFTER MOVE)
    if next_state.status == GameStatus.IN_PROGRESS and acting == Player.PLAYER1:
        perf_manager = getattr(app.state, 'performance_manager', None)
        if perf_manager:
            # Record the move time
            perf_manager.record_human_move_time(game_id, request.thinking_time_ms)
            print(f" Recorded move time: {request.thinking_time_ms}ms for game {game_id}")

            # Log current in-game adjustment for debugging
            player_id = perf_manager.player_mapping.get(game_id)
            if player_id:
                adjustment = perf_manager.get_in_game_adjustment(player_id)
                logger.info(f"Current in-game DDA after move: {adjustment:.2f}x for player {player_id}")

    # Calculate reward
    reward = next_state.utilities.get(acting, 0.0)

    # Log to database
    db = get_db()
    if db:
        try:
            if prev_state.turn_index == 0:
                db.log_game_started(game_id)

            entry = TransitionLogEntry(
                timestamp=datetime.now(UTC).isoformat(),
                game_id=game_id,
                move_index=prev_state.turn_index,
                player=acting,
                action=request.column,
                prev_state=prev_state,
                next_state=next_state,
                reward=reward,
                utility_before=prev_state.utilities,
                utility_after=next_state.utilities,
                mcts_stats=request.mcts_stats,
                thinking_time_ms=request.thinking_time_ms
            )

            db.log_transition(entry)

            # HANDLE GAME END WITH DATABASE PERSISTENCE
            if next_state.status in (GameStatus.WIN, GameStatus.DRAW):
                db.log_game_ended(
                    game_id=game_id,
                    status=next_state.status,
                    winner=next_state.winner,
                    total_moves=next_state.turn_index,
                    final_board=next_state.board,
                    final_utilities=next_state.utilities
                )

                print(f"Game {game_id} ended: {next_state.status.value}, winner: {next_state.winner}")


                perf_manager = getattr(app.state, 'performance_manager', None)
                print(f" perf_manager exists: {perf_manager is not None}")

                if perf_manager and prev_state.config.player1_type == PlayerType.HUMAN:
                    # Get player_id from game mapping
                    player_id = perf_manager.player_mapping.get(game_id)
                    print(f"game_id={game_id}")
                    print(f"player_id={player_id}")
                    print(f"player_mapping={perf_manager.player_mapping}")

                    if player_id:
                        # Determine if human player won
                        player_won = next_state.winner == Player.PLAYER1
                        print(f" player_won={player_won}")

                        # Update in-memory performance
                        perf_manager.update_performance(game_id, player_won)

                        # PERSIST TO DATABASE FOR CROSS-GAME DDA
                        perf = perf_manager.get_performance(player_id)
                        if perf:
                            print(f" consecutive_wins={perf.consecutive_wins}")
                            print(f"consecutive_losses={perf.consecutive_losses}")
                            print(f"recent_win_rate={perf.get_win_rate():.2%}")


                            current_ai_skill = next_state.config.player2_skill_level if next_state.config.player2_skill_level else SkillLevel.MEDIUM
                            adjusted_skill = calculate_adjusted_difficulty(current_ai_skill, perf)

                            # Save to database
                            print(f" Calling db.update_player_performance()...")
                            try:
                                db.update_player_performance(
                                    player_id=player_id,
                                    game_id=game_id,
                                    won=player_won,
                                    consecutive_wins=perf.consecutive_wins,
                                    consecutive_losses=perf.consecutive_losses,
                                    recent_win_rate=perf.get_win_rate(),
                                    opponent_skill=adjusted_skill.value
                                )
                                print(f"Database updated with adjusted_skill={adjusted_skill.value}")
                            except Exception as db_err:
                                print(f"Failed to update player performance: {db_err}")
                                import traceback
                                traceback.print_exc()

                            # Log DDA status
                            if player_won:
                                print(f" Player {player_id} won game {game_id} (Streak: {perf.consecutive_wins}W, Win rate: {perf.get_win_rate():.1%})")
                                if adjusted_skill != current_ai_skill:
                                    print(f"   → Next game difficulty will be: {adjusted_skill.value}")
                            else:
                                print(f" Player {player_id} lost game {game_id} (Streak: {perf.consecutive_losses}L, Win rate: {perf.get_win_rate():.1%})")
                                if adjusted_skill != current_ai_skill:
                                    print(f"   → Next game difficulty will be: {adjusted_skill.value}")
                        else:
                            print(f"Could not get performance for player {player_id}")
                    else:
                        print(f"No player_id found in player_mapping for game {game_id}")

        except Exception as e:
            print(f"DB logging error: {e}")
            import traceback
            traceback.print_exc()

    # Publish AI move request
    if app.state.rabbitmq:
        if (next_state.status == GameStatus.IN_PROGRESS and
                next_state.current_player == Player.PLAYER2 and
                next_state.config.player2_type == PlayerType.CPU):

            current_player_int = 2
            skill_level = next_state.config.player2_skill_level.value if next_state.config.player2_skill_level else 'medium'

            # ✅ CALCULATE IN-GAME DDA ADJUSTMENT (COPY THIS)
            dda_adjustment = 1.0
            perf_manager = getattr(app.state, 'performance_manager', None)
            if perf_manager and prev_state.config.player1_type == PlayerType.HUMAN:
                player_id = perf_manager.player_mapping.get(game_id)
                if player_id:
                    adjustment = perf_manager.get_in_game_adjustment(player_id)
                    dda_adjustment = adjustment
                    logger.info(f" Publishing AI move with in-game DDA: {adjustment:.2f}x "
                                f"(Player {player_id}, Game {game_id})")

            # Publish with dynamic DDA adjustment
            app.state.rabbitmq.publish_ai_move_needed(
                game_id=game_id,
                board=next_state.board,
                current_player=current_player_int,
                skill_level=skill_level,
                dda_adjustment=dda_adjustment
            )

        # Publish generic move event
        app.state.rabbitmq.publish_event('game.move.made', {
            'event_id': str(uuid.uuid4()),
            'event_type': 'game.move.made',
            'game_id': game_id,
            'player': acting.value,
            'column': request.column,
            'turn_index': prev_state.turn_index
        })

    return next_state

@app.get("/games/{game_id}/replay", response_model=GameReplay)
def get_game_replay(game_id: str):
    """
    Get complete game replay data.
    Returns all frames needed to replay the game visually.
    """
    # First try in-memory
    if game_id in GAME_SESSIONS:
        game = GAME_SESSIONS[game_id]
        frames = []
        for move in game.move_history:
            # Get state at this move
            state_at_move = game.get_state_at_move(move.move_index + 1)
            if state_at_move:
                frames.append(ReplayFrame(
                    move_index=move.move_index,
                    player=move.player,
                    column=move.column,
                    row=move.row,
                    board=state_at_move.board,
                    thinking_time_ms=move.thinking_time_ms,
                    timestamp=move.timestamp or ""
                ))

        return GameReplay(
            game_id=game_id,
            config=game.config,
            status=game.status,
            winner=game.winner,
            total_moves=game.turn_index,
            frames=frames,
            duration_seconds=game.get_duration_seconds() or 0.0
        )

    # Try database
    db = get_db()
    if db:
        try:
            replay_data = db.get_game_replay(game_id)
            if replay_data:
                game_info = replay_data['game']
                moves = replay_data['moves']

                # Reconstruct config
                config = GameConfig(
                    rows=game_info['rows'],
                    cols=game_info['cols'],
                    connect=game_info['connect'],
                    empty_token=game_info['empty_token'],
                    player1_token=game_info['player1_token'],
                    player2_token=game_info['player2_token'],
                    player1_type=PlayerType(game_info['player1_type']),
                    player2_type=PlayerType(game_info['player2_type']),
                    starting_player=Player(game_info['starting_player'])
                )

                # Build frames
                frames = []
                for m in moves:
                    frames.append(ReplayFrame(
                        move_index=m['move_index'],
                        player=Player(m['player']),
                        column=m['column_played'],
                        row=m['row_placed'],
                        board=m['board_after'],
                        thinking_time_ms=m['thinking_time_ms'],
                        timestamp=m['timestamp'].isoformat() if m['timestamp'] else ""
                    ))

                return GameReplay(
                    game_id=game_id,
                    config=config,
                    status=GameStatus(game_info['status']),
                    winner=Player(game_info['winner']) if game_info['winner'] else None,
                    total_moves=game_info['total_moves'],
                    frames=frames,
                    duration_seconds=game_info['duration_seconds'] or 0.0
                )

        except Exception as e:
            print(f"Error fetching replay from DB: {e}")

    raise HTTPException(404, "Game not found")

@app.get("/games/{game_id}/state/{move_index}", response_model=GameState)
def get_state_at_move(game_id: str, move_index: int):
    """Get game state at a specific move index for replay"""
    game = get_game(game_id)
    state = game.get_state_at_move(move_index)
    if state is None:
        raise HTTPException(400, f"Invalid move index: {move_index}")
    return state

# ============================================================================
# SELF-PLAY / DATASET GENERATION
# ============================================================================

@app.post("/games/self-play", response_model=SelfPlaySession)
def start_self_play_session(config: SelfPlayConfig):
    """
    Start a self-play session for dataset generation.
    Creates multiple games between AI agents with specified skill levels.
    """
    session_id = str(uuid.uuid4())
    db = get_db()
    if db:
        try:
            db.log_self_play_session_start(
                session_id=session_id,
                agent1_skill=config.agent1_skill.value,
                agent2_skill=config.agent2_skill.value,
                noise_level=config.noise_level,
                temperature=config.temperature
            )
        except Exception as e:
            print(f"DB logging error: {e}")

    # Publish self-play started event
    if app.state.rabbitmq:
        app.state.rabbitmq.publish_self_play_started(
            session_id=session_id,
            config=config.model_dump(),
            num_games=config.num_games
        )

    return SelfPlaySession(
        session_id=session_id,
        config=config,
        games_completed=0,
        games_remaining=config.num_games,
        started_at=datetime.now(UTC).isoformat()
    )

@app.post("/games/ai-vs-ai")
def create_ai_vs_ai_game(
    skill_p1: SkillLevel = SkillLevel.MEDIUM,
    skill_p2: SkillLevel = SkillLevel.EXPERT
):
    """Create and run a single AI vs AI game"""
    config = GameConfig(
        player1_type=PlayerType.CPU,
        player2_type=PlayerType.CPU,
        player1_skill_level=skill_p1,
        player2_skill_level=skill_p2
    )

    game_id = str(uuid.uuid4())
    game = ConnectFourGame(game_id, config)
    GAME_SESSIONS[game_id] = game

    db = get_db()
    if db:
        try:
            db.log_game_created(game_id, config)
        except Exception as e:
            print(f"DB logging error: {e}")

    # Publish event for MCTS to handle
    if app.state.rabbitmq:
        app.state.rabbitmq.publish_event('game.aivsai.created', {
            'event_id': str(uuid.uuid4()),
            'event_type': 'aivsai.created',
            'game_id': game_id,
            'skill_level_p1': skill_p1.value,
            'skill_level_p2': skill_p2.value
        })

    return {
        "game_id": game_id,
        "message": "AI vs AI game started",
        "skill_p1": skill_p1.value,
        "skill_p2": skill_p2.value
    }

@app.post("/datasets/export", response_model=DatasetExportResult)
def export_dataset(request: DatasetExportRequest):
    """
    Export training dataset to Parquet format.
    The exported data includes game states, moves, and MCTS statistics
    suitable for training ML models.
    """
    db = get_db()
    if not db:
        raise HTTPException(500, "Database not available")

    export_id = str(uuid.uuid4())

    # maybe better to make it async ?
    if app.state.rabbitmq:
        app.state.rabbitmq.publish_event('dataset.export.requested', {
            'event_id': str(uuid.uuid4()),
            'event_type': 'dataset.export.requested',
            'export_id': export_id,
            'version': request.version,
            'num_games': request.num_games,
            'skill_levels': [s.value for s in request.skill_levels] if request.skill_levels else None,
            'date_from': request.date_from,
            'date_to': request.date_to,
            'include_mcts_stats': request.include_mcts_stats
        })

    return DatasetExportResult(
        export_id=export_id,
        version=request.version,
        num_games=0, # Will be updated when export completes
        num_moves=0,
        file_path=f"data/datasets/connect4_{request.version}.parquet",
        file_size_bytes=0,
        checksum="",
        created_at=datetime.now(UTC).isoformat()
    )

# ============================================================================
# HEALTH / STATS
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    db_status = "connected" if get_db() else "not connected"
    rmq_status = "connected" if app.state.rabbitmq else "not connected"
    return {
        "status": "healthy",
        "games_active": len(GAME_SESSIONS),
        "database": db_status,
        "rabbitmq": rmq_status
    }

@app.get("/stats")
def get_stats():
    """Get system statistics"""
    db = get_db()
    stats = {
        "active_games": len(GAME_SESSIONS),
        "database_connected": db is not None
    }

    if db:
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM games")
                    stats['total_games_logged'] = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM moves")
                    stats['total_moves_logged'] = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM games WHERE status = 'win'")
                    stats['completed_games'] = cur.fetchone()[0]
        except Exception as e:
            stats['db_error'] = str(e)

    return stats
