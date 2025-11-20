# app/game.py
from __future__ import annotations

from typing import List, Optional, Dict
import random

from schemas import (
    GameConfig, Player, PlayerType, GameStatus,
    GameState, MoveInfo
)


class ConnectFourGame:
    def __init__(self, game_id: str, config: Optional[GameConfig] = None):
        self.id = game_id
        self.config = config or GameConfig()

        self.rows = self.config.rows
        self.cols = self.config.cols

        self.board: List[List[str]] = [
            [self.config.empty_token for _ in range(self.cols)]
            for _ in range(self.rows)
        ]

        self.current_player = self.config.starting_player
        self.status = GameStatus.IN_PROGRESS
        self.winner: Optional[Player] = None
        self.turn_index = 0
        self.move_history: List[MoveInfo] = []

    # ---------------- Utility ----------------

    def _token_for(self, player: Player) -> str:
        return (
            self.config.player1_token if player == Player.PLAYER1
            else self.config.player2_token
        )

    def _other(self, player: Player) -> Player:
        return Player.PLAYER2 if player == Player.PLAYER1 else Player.PLAYER1

    def _copy_board(self):
        return [row[:] for row in self.board]

    # ---------------- Public API ----------------

    def legal_actions(self) -> List[int]:
        if self.status != GameStatus.IN_PROGRESS:
            return []
        return [
            c for c in range(self.cols)
            if self.board[0][c] == self.config.empty_token
        ]

    def is_valid_action(self, column: int) -> bool:
        return column in self.legal_actions()

    def play_move(self, column: int) -> GameState:
        if self.status != GameStatus.IN_PROGRESS:
            raise ValueError("Game finished.")

        if not self.is_valid_action(column):
            raise ValueError("Invalid move.")

        player = self.current_player
        token = self._token_for(player)

        row = self._drop_piece(column, token)

        move = MoveInfo(
            move_index=self.turn_index,
            player=player,
            column=column,
            row=row
        )

        self.move_history.append(move)
        self.turn_index += 1

        if self._has_winning_line(token):
            self.status = GameStatus.WWIN
            self.winner = player
        elif not self.legal_actions():
            self.status = GameStatus.DRAW
        else:
            self.current_player = self._other(player)

        return self.get_state()

    def select_cpu_action(self) -> int:
        legal = self.legal_actions()
        if not legal:
            raise ValueError("No legal actions.")
        return random.choice(legal)

    def get_state(self) -> GameState:
        legal = self.legal_actions()
        utilities = self._utilities()
        last_move = self.move_history[-1] if self.move_history else None

        return GameState(
            game_id=self.id,
            config=self.config,
            board=self._copy_board(),
            current_player=self.current_player,
            turn_index=self.turn_index,
            legal_actions=legal,
            status=self.status,
            winner=self.winner,
            last_move=last_move,
            utilities=utilities,
        )

    def get_history(self) -> List[MoveInfo]:
        return list(self.move_history)

    # ---------------- Internal ----------------

    def _drop_piece(self, column: int, token: str) -> int:
        for r in range(self.rows - 1, -1, -1):
            if self.board[r][column] == self.config.empty_token:
                self.board[r][column] = token
                return r
        raise RuntimeError("No space in column.")

    def _utilities(self) -> Dict[Player, float]:
        if self.status == GameStatus.IN_PROGRESS:
            return {Player.PLAYER1: 0, Player.PLAYER2: 0}

        if self.status == GameStatus.DRAW:
            return {Player.PLAYER1: 0, Player.PLAYER2: 0}

        win = 1.0
        lose = -1.0
        return {
            Player.PLAYER1: win if self.winner == Player.PLAYER1 else lose,
            Player.PLAYER2: win if self.winner == Player.PLAYER2 else lose,
        }

    def _has_winning_line(self, token: str) -> bool:
        dirs = [(0,1), (1,0), (1,1), (1,-1)]
        need = self.config.connect

        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] != token:
                    continue
                for dr, dc in dirs:
                    if self._count(r, c, dr, dc, token) >= need:
                        return True
        return False

    def _count(self, r, c, dr, dc, token):
        cnt = 0
        rows, cols = self.rows, self.cols
        while 0 <= r < rows and 0 <= c < cols:
            if self.board[r][c] != token:
                break
            cnt += 1
            r += dr
            c += dc
        return cnt
