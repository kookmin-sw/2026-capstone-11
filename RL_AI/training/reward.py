from __future__ import annotations

# 현재 프로젝트의 terminal reward 규칙을 정의하는 파일
# 승리 +1, 패배 -1, 무승부 0 규칙을 플레이어 관점 reward로 변환한다.

from RL_AI.game_engine.state import GameResult, PlayerID


def terminal_reward_for_player(result: GameResult, player_id: PlayerID) -> float:
    if result == GameResult.DRAW or result == GameResult.ONGOING:
        return 0.0
    if result == GameResult.P1_WIN:
        return 1.0 if player_id == PlayerID.P1 else -1.0
    if result == GameResult.P2_WIN:
        return 1.0 if player_id == PlayerID.P2 else -1.0
    return 0.0
