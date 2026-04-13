from __future__ import annotations

# 강화학습 시작 전 비교 기준으로 쓰기 위한 얇은 비랜덤 baseline 에이전트 파일
# 즉시 킬, 리더 압박, 공격, 소환을 우선하고 같은 점수면 무작위로 고른다.

from typing import Dict, Optional, Sequence, Tuple

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.cards.card_db import CardDefinition, Role
from RL_AI.game_engine.state import Action, ActionType, GameState


class GreedyAgent(BaseAgent):
    def __init__(self, seed: Optional[int] = None) -> None:
        super().__init__(name="greedy", seed=seed)

    def select_action(
        self,
        state: GameState,
        legal_actions: Sequence[Action],
        *,
        card_db: Optional[Dict[str, CardDefinition]] = None,
    ) -> Tuple[int, Action]:
        if not legal_actions:
            raise ValueError("GreedyAgent cannot select an action from an empty legal action list.")

        scored = [(self._score_action(state, action), idx, action) for idx, action in enumerate(legal_actions)]
        best_score = max(score for score, _, _ in scored)
        best = [(idx, action) for score, idx, action in scored if score == best_score]
        return best[self.rng.randrange(len(best))]

    def _score_action(self, state: GameState, action: Action) -> int:
        score = 0

        if action.action_type == ActionType.UNIT_ATTACK:
            score += 70
            if action.target_unit_ids:
                target = state.get_unit(action.target_unit_ids[0])
                score += 100 if target.role == Role.LEADER else 0
                score += 40 if target.current_life <= state.get_unit(action.source_unit_id).attack else 0
                score += 10 - min(target.current_life, 10)

        elif action.action_type == ActionType.USE_CARD:
            if action.target_positions and not action.target_unit_ids:
                score += 45
            else:
                score += 55
                if action.target_unit_ids:
                    targets = [state.get_unit(unit_id) for unit_id in action.target_unit_ids]
                    score += sum(12 for target in targets if target.owner != state.active_player)
                    score += sum(50 for target in targets if target.role == Role.LEADER)

        elif action.action_type == ActionType.MOVE_UNIT:
            score += 20
            if action.target_positions:
                dst = action.target_positions[0]
                enemy_leader = state.get_leader_runtime_unit(state.active_player.opponent())
                if enemy_leader is not None and enemy_leader.position is not None:
                    distance = abs(dst.row - enemy_leader.position.row) + abs(dst.col - enemy_leader.position.col)
                    score += max(0, 8 - distance)

        elif action.action_type == ActionType.END_TURN:
            score -= 100

        score += self.rng.randint(0, 3)
        return score
