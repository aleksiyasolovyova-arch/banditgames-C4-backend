# app/schemas.py
"""
schema for Connect4 with comprehensive game state tracking.
Designed for: Game analytics, AI training, replay functionality, and ML dataset generation.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
import hashlib
import json


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
    ABANDONED = "abandoned"


class SkillLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"



# Configuration DTOs
class GameConfig(BaseModel):
    """Game configuration with full parameters"""
    rows: int = Field(6, ge=4, description="Number of rows on the board")
    cols: int = Field(7, ge=4, description="Number of columns on the board")
    connect: int = Field(4, ge=3, description="Number of pieces needed to connect for a win")
    empty_token: str = Field(".", description="Token representing empty cell")
    player1_token: str = Field("X", description="Token for player 1")
    player2_token: str = Field("O", description="Token for player 2")
    player1_type: PlayerType = Field(PlayerType.HUMAN, description="Type of player 1")
    player2_type: PlayerType = Field(PlayerType.CPU, description="Type of player 2")
    starting_player: Player = Field(Player.PLAYER1, description="Which player starts")

    # AI configuration
    player1_skill_level: Optional[SkillLevel] = Field(None, description="Skill level for CPU player 1")
    player2_skill_level: Optional[SkillLevel] = Field(SkillLevel.MEDIUM, description="Skill level for CPU player 2")

    # Self-play configuration
    noise_level: float = Field(0.0, ge=0.0, le=1.0, description="Noise level for move selection (0-1)")
    temperature: float = Field(0.0, ge=0.0, description="Temperature for move probability distribution")



# Move Information

class MoveInfo(BaseModel):
    """Detailed move information"""
    move_index: int = Field(..., description="Sequential index of this move (0-based)")
    player: Player = Field(..., description="Player who made this move")
    column: int = Field(..., ge=0, description="Column where piece was placed")
    row: int = Field(..., ge=0, description="Row where piece landed")
    timestamp: Optional[str] = Field(None, description="ISO timestamp when move was made")
    thinking_time_ms: Optional[int] = Field(None, description="Time taken to make this move in milliseconds")


class MoveRequest(BaseModel):
    """Request to make a move"""
    column: int = Field(..., ge=0, description="Column to place piece")
    player: Optional[Player] = Field(None, description="Player making the move (optional, defaults to current player)")
    thinking_time_ms: Optional[int] = Field(None, description="Time taken for this move")
    mcts_stats: Optional[MCTSStatistics] = Field(None, description="MCTS statistics if move was by AI")


# MCTS Statistics (for AI training)

class MCTSMoveStats(BaseModel):
    """Statistics for a single move option from MCTS"""
    column: int
    visit_count: int
    q_value: float
    probability: float


class MCTSStatistics(BaseModel):
    """Comprehensive MCTS search statistics"""
    skill_level: str = Field(..., description="Skill level used for this search")
    base_skill_level: Optional[str] = Field(None, description="Original skill level before DDA adjustment")
    time_limit_seconds: float = Field(..., description="Time limit for search")
    actual_search_time_seconds: float = Field(..., description="Actual time spent searching")
    num_rollouts: int = Field(..., description="Number of rollouts performed")
    nodes_explored: Optional[int] = Field(None, description="Number of nodes explored in tree")

    best_move: int = Field(..., description="Best move selected")
    move_stats: List[MCTSMoveStats] = Field(default_factory=list, description="Statistics for each legal move")

    # DDA metrics
    time_adjustment_factor: Optional[float] = Field(None, description="DDA time adjustment multiplier")
    exploration_constant: Optional[float] = Field(None, description="UCB exploration constant used")

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)



# Game State
class GameState(BaseModel):

    # Identifiers
    game_id: str = Field(..., description="Unique game identifier")

    # Configuration
    config: GameConfig = Field(..., description="Game configuration")

    # Board state (2D array, row 0 is top)
    board: List[List[str]] = Field(..., description="Current board state")

    # Turn information
    current_player: Player = Field(..., description="Player to move next")
    turn_index: int = Field(..., description="Current turn number (0-based)")

    # Legal actions
    legal_actions: List[int] = Field(..., description="List of valid column indices")

    # Game status
    status: GameStatus = Field(..., description="Current game status")
    winner: Optional[Player] = Field(None, description="Winner if game is over")

    # Last move (for replay and analysis)
    last_move: Optional[MoveInfo] = Field(None, description="Information about the last move")

    # Utility/evaluation values
    utilities: Dict[Player, float] = Field(..., description="Utility values for each player")

    # Heuristic evaluation (optional, for training)
    heuristic_score: Optional[float] = Field(None, description="Heuristic evaluation of position")

    # History (optional, for analysis)
    move_history: Optional[List[MoveInfo]] = Field(None, description="Complete move history")

    # Timestamps
    created_at: str = Field(..., description="Game creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

    # State hash for deduplication
    state_hash: Optional[str] = Field(None, description="Hash of board state for deduplication")

    # MCTS statistics (if AI move)
    mcts_stats: Optional[MCTSStatistics] = Field(None, description="MCTS stats if this state resulted from AI move")

    def compute_state_hash(self) -> str:
        """Compute a unique hash for this board state"""
        board_str = json.dumps(self.board, sort_keys=True)
        player_str = self.current_player.value
        hash_input = f"{board_str}:{player_str}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]

    def to_serializable(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary"""
        data = self.model_dump()
        # Ensure enums are converted to strings
        data['current_player'] = self.current_player.value
        data['status'] = self.status.value
        if self.winner:
            data['winner'] = self.winner.value
        data['utilities'] = {k.value: v for k, v in self.utilities.items()}
        return data



# Logging DTOs
class TransitionLogEntry(BaseModel):
    """
    Comprehensive log entry for each game transition.
    Designed for ML training and analytics.
    """
    # Identifiers
    log_id: Optional[str] = Field(None, description="Unique log entry ID")
    timestamp: str = Field(..., description="ISO timestamp of this transition")
    game_id: str = Field(..., description="Game ID")

    # Move information
    move_index: int = Field(..., description="Move number")
    player: Player = Field(..., description="Player who made the move")
    action: int = Field(..., description="Column played")

    # States
    prev_state: GameState = Field(..., description="State before the move")
    next_state: GameState = Field(..., description="State after the move")

    # Evaluation
    reward: float = Field(..., description="Immediate reward for this move")
    utility_before: Dict[Player, float] = Field(..., description="Utilities before move")
    utility_after: Dict[Player, float] = Field(..., description="Utilities after move")

    # MCTS statistics (if AI move)
    mcts_stats: Optional[MCTSStatistics] = Field(None, description="MCTS search statistics")

    # Timing
    thinking_time_ms: Optional[int] = Field(None, description="Time taken to make move")

    # Game outcome (filled in retrospectively for training)
    game_outcome: Optional[str] = Field(None, description="Final game outcome (win/loss/draw)")
    outcome_reward: Optional[float] = Field(None, description="Reward based on game outcome")


class GameLogEntry(BaseModel):
    """Complete game log for export and replay"""
    game_id: str
    config: GameConfig

    # Participants
    player1_type: PlayerType
    player2_type: PlayerType
    player1_skill: Optional[SkillLevel] = None
    player2_skill: Optional[SkillLevel] = None

    # Outcome
    status: GameStatus
    winner: Optional[Player] = None
    total_moves: int

    # Complete history
    transitions: List[TransitionLogEntry]

    # Timestamps
    started_at: str
    ended_at: str
    duration_seconds: float

    # Final state
    final_board: List[List[str]]
    final_utilities: Dict[Player, float]


# Self-Play Configuration
class SelfPlayConfig(BaseModel):
    """Configuration for self-play dataset generation"""
    num_games: int = Field(100, ge=1, description="Number of games to play")

    # Agent configurations
    agent1_skill: SkillLevel = Field(SkillLevel.MEDIUM)
    agent2_skill: SkillLevel = Field(SkillLevel.MEDIUM)

    # Randomness for variety
    noise_level: float = Field(0.1, ge=0.0, le=1.0, description="Probability of random move")
    temperature: float = Field(0.5, ge=0.0, description="Softmax temperature for move selection")

    # Skill variation
    vary_skills: bool = Field(True, description="Vary skill levels across games")
    skill_levels: List[SkillLevel] = Field(
        default=[SkillLevel.EASY, SkillLevel.MEDIUM, SkillLevel.HARD, SkillLevel.EXPERT]
    )

    # Export configuration
    export_to_parquet: bool = Field(True)
    dataset_version: Optional[str] = Field(None, description="Version tag for DVC")


class SelfPlaySession(BaseModel):
    """Self-play session status and results"""
    session_id: str
    config: SelfPlayConfig

    # Progress
    games_completed: int = 0
    games_remaining: int

    # Results
    agent1_wins: int = 0
    agent2_wins: int = 0
    draws: int = 0

    # Timing
    started_at: str
    estimated_completion: Optional[str] = None

    # Export status
    exported: bool = False
    parquet_path: Optional[str] = None
    dvc_version: Optional[str] = None


# Replay DTOs
class ReplayFrame(BaseModel):
    """Single frame in a game replay"""
    move_index: int
    player: Player
    column: int
    row: int
    board: List[List[str]]
    thinking_time_ms: Optional[int] = None
    timestamp: str


class GameReplay(BaseModel):
    """Complete game replay data"""
    game_id: str
    config: GameConfig
    status: GameStatus
    winner: Optional[Player]
    total_moves: int
    frames: List[ReplayFrame]
    duration_seconds: float

# Dataset Export DTOs
class DatasetExportRequest(BaseModel):
    """Request to export dataset"""
    version: str = Field(..., description="Dataset version (e.g., 'v1', 'v2')")
    num_games: Optional[int] = Field(None, description="Limit number of games to export")
    skill_levels: Optional[List[SkillLevel]] = Field(None, description="Filter by skill levels")
    date_from: Optional[str] = Field(None, description="Start date filter (ISO format)")
    date_to: Optional[str] = Field(None, description="End date filter (ISO format)")
    include_mcts_stats: bool = Field(True, description="Include MCTS statistics in export")


class DatasetExportResult(BaseModel):
    """Result of dataset export"""
    export_id: str
    version: str
    num_games: int
    num_moves: int
    file_path: str
    file_size_bytes: int
    checksum: str
    dvc_tracked: bool = False
    minio_uploaded: bool = False
    created_at: str


class OracleLogRequest(BaseModel):
    game_id: str
    move_index: int
    state_hash: Optional[str] = None
    board_state: Optional[List[List[str]]] = None
    current_player: Optional[str] = None
    best_move: int
    move_ranking: List[int]
    visit_counts: Dict[str, int]
    q_values: Dict[str, float]
    probabilities: Dict[str, float]
    num_rollouts: int
    search_time: float
    exploration_constant: Optional[float] = 0.5
    actual_move: Optional[int] = None
    move_id: Optional[str] = None