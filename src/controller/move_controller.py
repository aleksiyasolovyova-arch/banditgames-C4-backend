"""
Move Controller - REST API endpoints for making moves.
- Stateless
- Validates input with Pydantic DTOs
- Delegates move execution to MoveService
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .dto.request import MakeMoveRequest
from .dto.response import GameResponse, ErrorResponse
from ..service.game_service import GameService
from ..service.move_service import MoveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["moves"])


def get_game_service(request: Request) -> GameService:
    svc = getattr(request.app.state, "game_service", None)
    if svc is None:
        raise RuntimeError("GameService not initialized")
    return svc


def get_move_service(request: Request) -> MoveService:
    svc = getattr(request.app.state, "move_service", None)
    if svc is None:
        raise RuntimeError("MoveService not initialized")
    return svc


@router.post(
    "/{game_id}/moves",
    response_model=GameResponse,
    summary="Make a move",
    responses={
        200: {"description": "Move executed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid move"},
        404: {"model": ErrorResponse, "description": "Game not found"}
    }
)
async def make_move(
        game_id: str,
        request_dto: MakeMoveRequest,
        game_service: GameService = Depends(get_game_service),
        move_service: MoveService = Depends(get_move_service)
):
    try:
        # Execute move
        move_service.execute_move(
            game_id=game_id,
            player_id=request_dto.player_id,
            column=request_dto.column
        )

        # Return updated game state
        game = game_service.get_game(game_id)
        return GameResponse.from_domain(game)

    except ValueError as e:
        logger.warning(f"Invalid move in game {game_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error making move in game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
