"""Agents that operate on C# SeaEngine snapshots and action lists."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
from torch import nn
from torch.distributions import Categorical

from RL_AI.SeaEngine.observation import (
    ACTION_FEATURE_DIM,
    BOARD_TOKEN_DIM,
    GLOBAL_FEATURE_DIM,
    HAND_TOKEN_DIM,
    SeaEngineObservation,
    build_observation,
)


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
    """Transformer-based Actor-Critic for SeaEngine."""
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()
        # State vector components (matching observation.py)
        self.global_dim = GLOBAL_FEATURE_DIM
        self.num_units = 14
        self.unit_dim = BOARD_TOKEN_DIM
        self.num_hand = 7
        self.hand_dim = HAND_TOKEN_DIM
        
        # Projections to hidden_dim
        self.global_proj = nn.Linear(self.global_dim, hidden_dim)
        self.unit_proj = nn.Linear(self.unit_dim, hidden_dim)
        self.hand_proj = nn.Linear(self.hand_dim, hidden_dim)
        
        # Type embeddings
        self.type_emb = nn.Parameter(torch.randn(3, hidden_dim))
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim, 
            nhead=4, 
            dim_feedforward=hidden_dim * 4, 
            batch_first=True, 
            activation='gelu'
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=1)
        
        # Action Encoder
        self.action_encoder = nn.Sequential(
            nn.Linear(action_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        
        # Heads
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
        is_batched = state_tensor.dim() > 1
        if not is_batched:
            state_tensor = state_tensor.unsqueeze(0)
        
        batch_size = state_tensor.shape[0]
        
        # Split tokens
        global_part = state_tensor[:, :self.global_dim]
        board_part = state_tensor[:, self.global_dim : self.global_dim + self.num_units * self.unit_dim].reshape(batch_size, self.num_units, self.unit_dim)
        hand_part = state_tensor[:, self.global_dim + self.num_units * self.unit_dim :].reshape(batch_size, self.num_hand, self.hand_dim)
        
        # Project and embed
        g_token = self.global_proj(global_part).unsqueeze(1) + self.type_emb[0]
        u_tokens = self.unit_proj(board_part) + self.type_emb[1]
        h_tokens = self.hand_proj(hand_part) + self.type_emb[2]
        
        all_tokens = torch.cat([g_token, u_tokens, h_tokens], dim=1)
        attended = self.transformer(all_tokens)
        
        state_context = attended[:, 0]
        action_hidden = self.action_encoder(action_tensor)
        
        if not is_batched:
            repeated_state = state_context.expand(action_hidden.shape[0], -1)
            logits = self.policy_head(torch.cat([repeated_state, action_hidden], dim=-1)).squeeze(-1)
            value = self.value_head(state_context).squeeze(-1)
        else:
            logits = self.policy_head(torch.cat([state_context.unsqueeze(1).expand(-1, action_hidden.shape[1], -1), action_hidden], dim=-1)).squeeze(-1)
            value = self.value_head(state_context).squeeze(-1)
            
        return logits, value


class SeaEngineRLAgent(SeaEngineAgent):
    def __init__(
        self,
        *,
        hidden_dim: int = 128,
        learning_rate: float = 3e-4,
        sample_actions: bool = True,
        device: str = "auto",
        seed: Optional[int] = None,
    ) -> None:
        super().__init__("rl", seed=seed)
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.sample_actions = sample_actions
        device_name = str(device).strip().lower()
        if device_name in {"", "auto"}:
            device_name = "cuda" if torch.cuda.is_available() else "cpu"
        if device_name in {"gpu", "cuda"} and not torch.cuda.is_available():
            device_name = "cpu"
        self.device = torch.device(device_name)
        self.state_dim: Optional[int] = None
        self.action_dim = ACTION_FEATURE_DIM
        self.model: Optional[PPOActorCritic] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None
        self.last_output: Optional[SeaEngineRLAgentOutput] = None

    @contextmanager
    def sampling_mode(self, enabled: bool):
        previous = self.sample_actions
        self.sample_actions = enabled
        try:
            yield
        finally:
            self.sample_actions = previous

    def ensure_model(self, state_dim: int) -> None:
        if self.model is not None:
            return
        self.state_dim = state_dim
        self.model = PPOActorCritic(state_dim, self.action_dim, self.hidden_dim).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)

    def forward_tensors(self, state_vector: Sequence[float], action_vectors: Sequence[Sequence[float]]) -> Tuple[torch.Tensor, torch.Tensor]:
        self.ensure_model(len(state_vector))
        assert self.model is not None
        state_tensor = torch.as_tensor(state_vector, dtype=torch.float32, device=self.device)
        action_tensor = torch.as_tensor(action_vectors, dtype=torch.float32, device=self.device)
        return self.model(state_tensor, action_tensor)

    def compute_policy_output(
        self,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> SeaEngineRLAgentOutput:
        if snapshot.get("state_vector") is not None and snapshot.get("action_feature_vectors") is not None:
            observation = SeaEngineObservation(
                unit_list=[],
                hand_list=[],
                global_vector=list(snapshot.get("global_vector", [])),
                legal_action_mask=[1 for _ in legal_actions],
                state_vector=list(snapshot["state_vector"]),
                action_feature_vectors=[list(a) for a in snapshot["action_feature_vectors"]],
            )
        else:
            observation = build_observation({**snapshot, "actions": list(legal_actions)}, snapshot.get("active_player"))
        
        with torch.no_grad():
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

    def compute_policy_output_batch(
        self,
        state_vectors: List[Sequence[float]],
        action_feature_vectors_list: List[Sequence[Sequence[float]]],
        legal_actions_list: List[Sequence[Dict[str, Any]]],
    ) -> List[SeaEngineRLAgentOutput]:
        if not state_vectors:
            return []
        self.ensure_model(len(state_vectors[0]))
        batch_size = len(state_vectors)
        state_tensor = torch.as_tensor(state_vectors, dtype=torch.float32, device=self.device)
        
        max_actions = max((len(a) for a in action_feature_vectors_list), default=1)
        if max_actions == 0: max_actions = 1
        
        action_dim = len(action_feature_vectors_list[0][0]) if len(action_feature_vectors_list[0]) > 0 else self.action_dim
        padded_actions = torch.zeros((batch_size, max_actions, action_dim), dtype=torch.float32, device=self.device)
        mask = torch.zeros((batch_size, max_actions), dtype=torch.bool, device=self.device)
        
        for i, a_vecs in enumerate(action_feature_vectors_list):
            num_a = len(a_vecs)
            if num_a > 0:
                padded_actions[i, :num_a, :] = torch.as_tensor(a_vecs, dtype=torch.float32, device=self.device)
                mask[i, :num_a] = True
        with torch.no_grad():
            logits_tensor, value_tensor = self.model(state_tensor, padded_actions)
            logits_tensor = logits_tensor.masked_fill(~mask, float('-inf'))
        dist = Categorical(logits=logits_tensor)
        if self.sample_actions:
            chosen_indices = dist.sample()
        else:
            chosen_indices = torch.argmax(logits_tensor, dim=1)
            
        log_probs = dist.log_prob(chosen_indices)
        probs = dist.probs
            
        outputs = []
        for i in range(batch_size):
            idx = int(chosen_indices[i].item())
            outputs.append(SeaEngineRLAgentOutput(
                action_index=idx,
                action=legal_actions_list[i][idx],
                state_vector=state_vectors[i],
                action_feature_vectors=action_feature_vectors_list[i],
                logits=logits_tensor[i].detach().cpu().tolist(),
                probabilities=probs[i].detach().cpu().tolist(),
                log_prob=float(log_probs[i].item()),
                value=float(value_tensor[i].item()),
            ))
        return outputs

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

    def evaluate_action_batch(
        self,
        state_vectors: List[Sequence[float]],
        action_feature_vectors_list: List[Sequence[Sequence[float]]],
        chosen_action_indices: List[int],
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch_size = len(state_vectors)
        state_tensor = torch.as_tensor(state_vectors, dtype=torch.float32, device=self.device)
        
        # Pad action features to form a batched tensor
        max_actions = max(len(a) for a in action_feature_vectors_list)
        # fallback for empty action list:
        if max_actions == 0:
            max_actions = 1
            action_dim = 1
            from RL_AI.SeaEngine.observation import ACTION_FEATURE_DIM
            action_dim = ACTION_FEATURE_DIM
        else:
            action_dim = len(action_feature_vectors_list[0][0])
            for a in action_feature_vectors_list:
                if len(a) > 0:
                    action_dim = len(a[0])
                    break
        
        padded_actions = torch.zeros((batch_size, max_actions, action_dim), dtype=torch.float32, device=self.device)
        mask = torch.zeros((batch_size, max_actions), dtype=torch.bool, device=self.device)
        
        for i, a_vecs in enumerate(action_feature_vectors_list):
            num_a = len(a_vecs)
            if num_a > 0:
                padded_actions[i, :num_a, :] = torch.as_tensor(a_vecs, dtype=torch.float32, device=self.device)
                mask[i, :num_a] = True
        # Forward pass on batched inputs
        logits, value = self.model(state_tensor, padded_actions)
        # Mask out padded actions by setting their logits to negative infinity
        logits = logits.masked_fill(~mask, float('-inf'))
        dist = Categorical(logits=logits)
        action_index_tensor = torch.tensor(chosen_action_indices, dtype=torch.long, device=self.device)
        log_prob = dist.log_prob(action_index_tensor)
        entropy = dist.entropy()
        return log_prob, entropy, value
def load_state_dict_flexible(model: nn.Module, state_dict: Dict[str, torch.Tensor]) -> None:
    """Load a checkpoint while tolerating expanded input projections.

    When the observation layout grows, only the first linear projections on the
    state tokens change shape. We preserve the overlapping columns so older
    checkpoints remain useful as warm starts.
    """
    current_state = model.state_dict()
    compatible_state: Dict[str, torch.Tensor] = {}
    for key, current_tensor in current_state.items():
        source_tensor = state_dict.get(key)
        if source_tensor is None:
            continue
        if tuple(source_tensor.shape) == tuple(current_tensor.shape):
            compatible_state[key] = source_tensor
            continue
        if (
            key in {"global_proj.weight", "unit_proj.weight"}
            and source_tensor.ndim == 2
            and current_tensor.ndim == 2
        ):
            merged = current_tensor.clone()
            rows = min(merged.shape[0], source_tensor.shape[0])
            cols = min(merged.shape[1], source_tensor.shape[1])
            merged[:rows, :cols] = source_tensor[:rows, :cols]
            compatible_state[key] = merged
            continue
    model.load_state_dict(compatible_state, strict=False)
