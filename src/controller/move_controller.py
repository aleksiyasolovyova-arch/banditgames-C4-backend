"""
Move Controller - REST API endpoints for making moves.
Updated to include achievement checking dependencies.

Location: src/controller/move_controller.py
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .dto.request import MakeMoveRequest
from .dto.response import GameResponse, ErrorResponse
from ..service.game_service import GameService
from ..service.move_service import MoveService
from ..service.player_statistics_calculator import PlayerStatisticsCalculator
from ..service.achievement_checker import AchievementChecker
from ..data_access.database import DatabaseConfig
from ..data_access.postgres_game_repository import PostgresGameRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["moves"])


def get_db_session() -> Session:
    """Dependency to get database session."""
    session_factory = DatabaseConfig.get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_game_service(
    request: Request,
    session: Session = Depends(get_db_session)
) -> GameService:
    """Dependency to get GameService with PostgreSQL repository."""
    repository = PostgresGameRepository(session)
    event_publisher = getattr(request.app.state, "event_publisher", None)
    if not event_publisher:
        raise RuntimeError("EventPublisher not initialized")
    return GameService(repository, event_publisher)


def get_move_service(
    request: Request,
    session: Session = Depends(get_db_session)
) -> MoveService:
    """Dependency to get MoveService with achievement checking."""
    repository = PostgresGameRepository(session)
    event_publisher = getattr(request.app.state, "event_publisher", None)
    if not event_publisher:
        raise RuntimeError("EventPublisher not initialized")

    # Create statistics calculator and achievement checker
    stats_calculator = PlayerStatisticsCalculator(repository)
    achievement_checker = AchievementChecker(event_publisher)

    return MoveService(repository, event_publisher, stats_calculator, achievement_checker)


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
        # Execute move (includes achievement checking if game finishes)
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