from __future__ import annotations

# PPO 학습에 필요한 rollout 저장 구조를 정의하는 파일
# 한 수마다 state/action/log_prob/value를 쌓고, 에피소드 종료 후 return/advantage를 계산한다.

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class RolloutStep:
    episode_id: int
    player_id: int
    state_vector: List[float]
    action_feature_vectors: List[List[float]]
    chosen_action_index: int
    reward: float
    done: bool
    old_log_prob: float
    old_value: float
    return_value: float = 0.0
    advantage: float = 0.0


class RolloutBuffer:
    def __init__(self) -> None:
        self.steps: List[RolloutStep] = []

    def __len__(self) -> int:
        return len(self.steps)

    def add_step(self, step: RolloutStep) -> None:
        self.steps.append(step)

    def clear(self) -> None:
        self.steps.clear()

    def trajectory_groups(self) -> Dict[Tuple[int, int], List[int]]:
        grouped: Dict[Tuple[int, int], List[int]] = {}
        for index, step in enumerate(self.steps):
            grouped.setdefault((step.episode_id, step.player_id), []).append(index)
        return grouped

    def compute_returns_and_advantages(self, gamma: float, gae_lambda: float) -> None:
        for indices in self.trajectory_groups().values():
            next_value = 0.0
            next_non_terminal = 0.0
            gae = 0.0

            for index in reversed(indices):
                step = self.steps[index]
                non_terminal = 0.0 if step.done else 1.0
                delta = step.reward + gamma * next_value * next_non_terminal - step.old_value
                gae = delta + gamma * gae_lambda * next_non_terminal * gae
                step.advantage = gae
                step.return_value = gae + step.old_value
                next_value = step.old_value
                next_non_terminal = non_terminal

    def normalized_advantages(self) -> List[float]:
        if not self.steps:
            return []
        advantages = [step.advantage for step in self.steps]
        mean = sum(advantages) / len(advantages)
        variance = sum((value - mean) ** 2 for value in advantages) / len(advantages)
        std = (variance + 1e-8) ** 0.5
        return [(value - mean) / std for value in advantages]
