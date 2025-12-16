import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .dto.request import CreateGameRequest
from .dto.response import GameResponse
from ..domain import Player
from ..service.game_service import GameService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["games"])


def get_game_service(request: Request) -> GameService:
    svc = getattr(request.app.state, "game_service", None)
    if not svc:
        raise RuntimeError("GameService not initialized")
    return svc


@router.post(
    "",
    response_model=GameResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_game(
        dto: CreateGameRequest,
        game_service: GameService = Depends(get_game_service)
):
    try:
        player_one = Player(
            id=dto.player_one.id,
            name=dto.player_one.name
        )

        player_two = Player(
            id=dto.player_two.id,
            name=dto.player_two.name
        )

        game = game_service.create_game(
            player_one=player_one,
            player_two=player_two,
            rows=dto.rows,
            cols=dto.cols
        )

        return GameResponse.from_domain(game)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error creating game", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
