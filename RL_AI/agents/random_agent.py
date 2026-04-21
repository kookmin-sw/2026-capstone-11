from __future__ import annotations

# legal action 중 하나를 완전히 무작위로 고르는 baseline 에이전트 파일
# 기존 match_runner 내부의 choose_action_randomly 로직을 독립 에이전트 형태로 분리했다.

from typing import Dict, Optional, Sequence, Tuple

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.cards.card_db import CardDefinition
from RL_AI.game_engine.state import Action, GameState


class RandomAgent(BaseAgent):
    def __init__(self, seed: Optional[int] = None) -> None:
        super().__init__(name="random", seed=seed)

    def select_action(
        self,
        state: GameState,
        legal_actions: Sequence[Action],
        *,
        card_db: Optional[Dict[str, CardDefinition]] = None,
    ) -> Tuple[int, Action]:
        if not legal_actions:
            raise ValueError("RandomAgent cannot select an action from an empty legal action list.")
        action_index = self.rng.randrange(len(legal_actions))
        return action_index, legal_actions[action_index]
