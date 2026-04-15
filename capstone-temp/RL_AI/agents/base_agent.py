from __future__ import annotations

# 모든 에이전트가 공통으로 따르는 최소 인터페이스를 정의하는 파일
# 현재 단계에서는 legal action 목록 중 하나를 고르는 역할만 표준화한다.

from abc import ABC, abstractmethod
import random
from typing import Dict, Optional, Sequence, Tuple

from RL_AI.cards.card_db import CardDefinition
from RL_AI.game_engine.state import Action, GameState


class BaseAgent(ABC):
    def __init__(self, name: str, seed: Optional[int] = None) -> None:
        self.name = name
        self.rng = random.Random(seed)

    @abstractmethod
    def select_action(
        self,
        state: GameState,
        legal_actions: Sequence[Action],
        *,
        card_db: Optional[Dict[str, CardDefinition]] = None,
    ) -> Tuple[int, Action]:
        """
        Return `(action_index, action)` from the provided legal action list.
        """
        raise NotImplementedError
