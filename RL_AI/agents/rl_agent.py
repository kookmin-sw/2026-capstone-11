from __future__ import annotations

# PPO 기반 강화학습 에이전트 파일
#
# PPO = Proximal Policy Optimization
# 현재 구현은 "부분 관측(Partially Observable) 환경"을 전제로 한 PPO actor-critic 초안이다.
# AlphaZero처럼 숨은 정보를 예측하거나 MCTS를 붙이는 구조가 아니라,
# 공개 정보 observation과 legal action 집합을 입력으로 정책과 가치 함수를 학습하는 구조다.
#
# 현재 특징:
# - policy-based RL
# - actor-critic 구조
# - legal action 개수가 매 턴 달라도 동작하도록 "state vector + action feature vector" 방식 사용
# - PPO 학습 코드와 연결 가능

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import torch
from torch import nn
from torch.distributions import Categorical

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.cards.card_db import CardDefinition
from RL_AI.game_engine.observation import (
    Observation,
    ACTION_FEATURE_DIM,
    build_fixed_state_vector,
    build_observation,
    encode_action_features,
)
from RL_AI.game_engine.state import Action, GameState


@dataclass
class RLAgentOutput:
    action_index: int
    action: Action
    observation: Observation
    state_vector: List[float]
    action_feature_vectors: List[List[float]]
    legal_indices: List[int]
    logits: List[float]
    probabilities: List[float]
    log_prob: float
    value: float


class PPOActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()
        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(action_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
        )
        self.policy_head = nn.Linear(hidden_dim * 2, 1)
        self.value_head = nn.Linear(hidden_dim, 1)

    def forward(self, state_tensor: torch.Tensor, action_tensor: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        state_tensor: [state_dim]
        action_tensor: [num_actions, action_dim]
        returns:
          logits: [num_actions]
          value: scalar tensor
        """
        state_hidden = self.state_encoder(state_tensor.unsqueeze(0)).squeeze(0)
        action_hidden = self.action_encoder(action_tensor)
        repeated_state = state_hidden.unsqueeze(0).expand(action_hidden.shape[0], -1)
        logits = self.policy_head(torch.cat([repeated_state, action_hidden], dim=-1)).squeeze(-1)
        value = self.value_head(state_hidden).squeeze(-1)
        return logits, value


class RLAgent(BaseAgent):
    def __init__(
        self,
        *,
        hidden_dim: int = 128,
        learning_rate: float = 3e-4,
        sample_actions: bool = True,
        device: str = "cpu",
        seed: Optional[int] = None,
    ) -> None:
        super().__init__(name="rl", seed=seed)
        self.algorithm_name = "Proximal Policy Optimization"
        self.algorithm_short_name = "PPO"
        self.algorithm_family = "partially observable policy-based actor-critic"
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.sample_actions = sample_actions
        self.device = torch.device(device)

        self.state_dim: Optional[int] = None
        self.action_dim: int = ACTION_FEATURE_DIM
        self.model: Optional[PPOActorCritic] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None
        self.last_output: Optional[RLAgentOutput] = None

    def select_action(
        self,
        state: GameState,
        legal_actions: Sequence[Action],
        *,
        card_db: Optional[Dict[str, CardDefinition]] = None,
    ) -> Tuple[int, Action]:
        if not legal_actions:
            raise ValueError("RLAgent cannot select an action from an empty legal action list.")

        output = self.compute_policy_output(state, legal_actions, card_db=card_db)
        self.last_output = output
        return output.action_index, output.action

    def compute_policy_output(
        self,
        state: GameState,
        legal_actions: Sequence[Action],
        *,
        card_db: Optional[Dict[str, CardDefinition]] = None,
    ) -> RLAgentOutput:
        observation = build_observation(state, state.active_player, legal_actions, card_db=card_db)
        state_vector = build_fixed_state_vector(state, state.active_player, legal_actions, card_db=card_db)
        action_feature_vectors = [
            encode_action_features(state, state.active_player, action, card_db=card_db)
            for action in legal_actions
        ]

        self.ensure_model(state_dim=len(state_vector))

        logits_tensor, value_tensor = self.forward_tensors(state_vector, action_feature_vectors)
        dist = Categorical(logits=logits_tensor)
        chosen_index = int(dist.sample().item()) if self.sample_actions else int(torch.argmax(logits_tensor).item())
        probabilities = dist.probs.detach().cpu().tolist()
        logits = logits_tensor.detach().cpu().tolist()
        log_prob = float(dist.log_prob(torch.tensor(chosen_index, device=self.device)).item())
        value = float(value_tensor.item())

        return RLAgentOutput(
            action_index=chosen_index,
            action=legal_actions[chosen_index],
            observation=observation,
            state_vector=state_vector,
            action_feature_vectors=action_feature_vectors,
            legal_indices=list(range(len(legal_actions))),
            logits=logits,
            probabilities=probabilities,
            log_prob=log_prob,
            value=value,
        )

    def ensure_model(self, state_dim: int) -> None:
        if self.model is not None:
            return
        self.state_dim = state_dim
        self.model = PPOActorCritic(state_dim=state_dim, action_dim=self.action_dim, hidden_dim=self.hidden_dim).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)

    def forward_tensors(
        self,
        state_vector: Sequence[float],
        action_feature_vectors: Sequence[Sequence[float]],
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        self.ensure_model(state_dim=len(state_vector))
        assert self.model is not None
        state_tensor = torch.tensor(state_vector, dtype=torch.float32, device=self.device)
        action_tensor = torch.tensor(action_feature_vectors, dtype=torch.float32, device=self.device)
        return self.model(state_tensor, action_tensor)

    def evaluate_action_set(
        self,
        state_vector: Sequence[float],
        action_feature_vectors: Sequence[Sequence[float]],
        chosen_action_index: int,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        logits, value = self.forward_tensors(state_vector, action_feature_vectors)
        dist = Categorical(logits=logits)
        action_index_tensor = torch.tensor(chosen_action_index, dtype=torch.long, device=self.device)
        log_prob = dist.log_prob(action_index_tensor)
        entropy = dist.entropy()
        return log_prob, entropy, value
