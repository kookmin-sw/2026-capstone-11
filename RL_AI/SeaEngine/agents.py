"""Agents that operate on C# SeaEngine snapshots and action lists."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
from torch import nn
from torch.distributions import Categorical

from RL_AI.SeaEngine.observation import ACTION_FEATURE_DIM, build_observation


class SeaEngineAgent(ABC):
    def __init__(self, name: str, seed: Optional[int] = None) -> None:
        self.name = name
        self.rng = random.Random(seed)

    @abstractmethod
    def select_action(
        self,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> Tuple[int, Dict[str, Any]]:
        raise NotImplementedError


class SeaEngineRandomAgent(SeaEngineAgent):
    def __init__(self, seed: Optional[int] = None) -> None:
        super().__init__("random", seed=seed)

    def select_action(
        self,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> Tuple[int, Dict[str, Any]]:
        if not legal_actions:
            raise ValueError("No legal actions available.")
        idx = self.rng.randrange(len(legal_actions))
        return idx, legal_actions[idx]


class SeaEngineGreedyAgent(SeaEngineAgent):
    def __init__(self, seed: Optional[int] = None) -> None:
        super().__init__("greedy", seed=seed)

    def select_action(
        self,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> Tuple[int, Dict[str, Any]]:
        if not legal_actions:
            raise ValueError("No legal actions available.")
        scored = [(self._score_action(snapshot, action), idx, action) for idx, action in enumerate(legal_actions)]
        best_score = max(score for score, _, _ in scored)
        best = [(idx, action) for score, idx, action in scored if score == best_score]
        return best[self.rng.randrange(len(best))]

    def _score_action(self, snapshot: Dict[str, Any], action: Dict[str, Any]) -> int:
        effect_id = action.get("effect_id", "")
        target = action.get("target", {})
        target_type = target.get("type", "None")
        target_uid = target.get("guid", "")
        cards = {card["uid"]: card for card in snapshot.get("board", [])}
        target_card = cards.get(target_uid)

        score = 0
        if effect_id == "DefaultAttack":
            score += 80
        elif effect_id == "DeployUnit":
            score += 45
        elif effect_id == "DefaultMove":
            score += 20
        elif effect_id == "TurnEnd":
            score -= 100
        else:
            score += 55

        if target_type == "Unit" and target_card is not None:
            if target_card.get("role") == "Leader":
                score += 100
            score += 10 - min(int(target_card.get("hp", 10)), 10)

        if target_type == "Cell":
            target_x = int(target.get("pos_x", -1))
            target_y = int(target.get("pos_y", -1))
            enemy_leader = next(
                (card for card in snapshot.get("board", []) if card.get("owner") != snapshot.get("active_player") and card.get("role") == "Leader" and card.get("is_placed")),
                None,
            )
            if enemy_leader is not None:
                distance = abs(target_x - int(enemy_leader.get("pos_x", -1))) + abs(target_y - int(enemy_leader.get("pos_y", -1)))
                score += max(0, 8 - distance)

        score += self.rng.randint(0, 3)
        return score


@dataclass
class SeaEngineRLAgentOutput:
    action_index: int
    action: Dict[str, Any]
    state_vector: List[float]
    action_feature_vectors: List[List[float]]
    logits: List[float]
    probabilities: List[float]
    log_prob: float
    value: float


class PPOActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 192) -> None:
        super().__init__()
        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(action_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, state_tensor: torch.Tensor, action_tensor: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        state_hidden = self.state_encoder(state_tensor.unsqueeze(0)).squeeze(0)
        action_hidden = self.action_encoder(action_tensor)
        repeated_state = state_hidden.unsqueeze(0).expand(action_hidden.shape[0], -1)
        logits = self.policy_head(torch.cat([repeated_state, action_hidden], dim=-1)).squeeze(-1)
        value = self.value_head(state_hidden).squeeze(-1)
        return logits, value


class SeaEngineRLAgent(SeaEngineAgent):
    def __init__(
        self,
        *,
        hidden_dim: int = 192,
        learning_rate: float = 3e-4,
        sample_actions: bool = True,
        device: str = "cpu",
        seed: Optional[int] = None,
    ) -> None:
        super().__init__("rl", seed=seed)
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.sample_actions = sample_actions
        self.device = torch.device(device)
        self.state_dim: Optional[int] = None
        self.action_dim = ACTION_FEATURE_DIM
        self.model: Optional[PPOActorCritic] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None
        self.last_output: Optional[SeaEngineRLAgentOutput] = None

    def ensure_model(self, state_dim: int) -> None:
        if self.model is not None:
            return
        self.state_dim = state_dim
        self.model = PPOActorCritic(state_dim, self.action_dim, self.hidden_dim).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)

    def forward_tensors(self, state_vector: Sequence[float], action_vectors: Sequence[Sequence[float]]) -> Tuple[torch.Tensor, torch.Tensor]:
        self.ensure_model(len(state_vector))
        assert self.model is not None
        state_tensor = torch.tensor(state_vector, dtype=torch.float32, device=self.device)
        action_tensor = torch.tensor(action_vectors, dtype=torch.float32, device=self.device)
        return self.model(state_tensor, action_tensor)

    def compute_policy_output(
        self,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> SeaEngineRLAgentOutput:
        observation = build_observation({**snapshot, "actions": list(legal_actions)}, snapshot.get("active_player"))
        logits_tensor, value_tensor = self.forward_tensors(observation.state_vector, observation.action_feature_vectors)
        dist = Categorical(logits=logits_tensor)
        chosen_index = int(dist.sample().item()) if self.sample_actions else int(torch.argmax(logits_tensor).item())
        output = SeaEngineRLAgentOutput(
            action_index=chosen_index,
            action=legal_actions[chosen_index],
            state_vector=observation.state_vector,
            action_feature_vectors=observation.action_feature_vectors,
            logits=logits_tensor.detach().cpu().tolist(),
            probabilities=dist.probs.detach().cpu().tolist(),
            log_prob=float(dist.log_prob(torch.tensor(chosen_index, device=self.device)).item()),
            value=float(value_tensor.item()),
        )
        self.last_output = output
        return output

    def select_action(
        self,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> Tuple[int, Dict[str, Any]]:
        if not legal_actions:
            raise ValueError("No legal actions available.")
        output = self.compute_policy_output(snapshot, legal_actions)
        return output.action_index, output.action

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
