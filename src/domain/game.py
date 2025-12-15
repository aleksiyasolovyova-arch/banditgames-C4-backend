class Game(BaseModel):
    
    columns: int
    rows: int

    game_id: str = Field(..., description="Unique game identifier")

    player1_id: str 

    player2_id: str 

    game_states: List[GameState]

    status: GameStatus = Field(..., description="Current game status")

    created_at: str = Field(..., description="Game creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

class GameState(BaseModel):

    game_state_index: int
    move_index: int
    
    # 2d array of tokens for how the board actually looks for easy access
    creation_time
    move_time

class GameStatus(Enum):
    IN_PROGRESS,
    PLAYER1_WINNER, 
    PLAYER2_WINNER,
    DRAW,
    ABANDONED 

class Token(enum)
    PLAYER1,
    PLAYER2,
    EMPTY
