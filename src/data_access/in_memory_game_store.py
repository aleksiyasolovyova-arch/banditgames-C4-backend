"""
In-memory runtime store for active games.

"""
from __future__ import annotations

from typing import Dict, Optional, List

from ..domain import Game


class InMemoryGameStore:
    """Stores active games in memory for the lifetime of the process."""

    def __init__(self):
        self._games: Dict[str, Game] = {}

    def save(self, game: Game) -> None:
        self._games[game.id] = game

    def get(self, game_id: str) -> Optional[Game]:
        return self._games.get(game_id)

    def delete(self, game_id: str) -> None:
        self._games.pop(game_id, None)

    def list_games(self) -> List[Game]:
        return list(self._games.values())
