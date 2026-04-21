from __future__ import annotations

# PPO 기반 강화학습 에이전트 파일 (Transformer 아키텍처 적용)

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Any

import torch
from torch import nn
from torch.distributions import Categorical

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.cards.card_db import CardDefinition
# 이 파일은 레거시 또는 일반 에이전트용이므로 Observation 임포트 경로가 다를 수 있음
# 하지만 구조는 SeaEngine/agents.py와 동일하게 맞춤

@dataclass
class RLAgentOutput:
    action_index: int
    action: Any
    state_vector: List[float]
    action_feature_vectors: List[List[float]]
    logits: List[float]
    probabilities: List[float]
    log_prob: float
    value: float


class PPOActorCritic(nn.Module):
    """Transformer-based Actor-Critic."""
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256) -> None:
        super().__init__()
        # State vector components (Standard SeaEngine Layout)
        self.global_dim = 39
        self.num_units = 14
        self.unit_dim = 29
        self.num_hand = 7
        self.hand_dim = 10
        
        self.global_proj = nn.Linear(self.global_dim, hidden_dim)
        self.unit_proj = nn.Linear(self.unit_dim, hidden_dim)
        self.hand_proj = nn.Linear(self.hand_dim, hidden_dim)
        
        self.type_emb = nn.Parameter(torch.randn(3, hidden_dim))
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim, 
            nhead=8, 
            dim_feedforward=hidden_dim * 4, 
            batch_first=True, 
            activation='gelu'
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=3)
        
        self.action_encoder = nn.Sequential(
            nn.Linear(action_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
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
        is_batched = state_tensor.dim() > 1
        if not is_batched:
            state_tensor = state_tensor.unsqueeze(0)
        
        batch_size = state_tensor.shape[0]
        
        global_part = state_tensor[:, :self.global_dim]
        board_part = state_tensor[:, self.global_dim : self.global_dim + self.num_units * self.unit_dim].reshape(batch_size, self.num_units, self.unit_dim)
        hand_part = state_tensor[:, self.global_dim + self.num_units * self.unit_dim :].reshape(batch_size, self.num_hand, self.hand_dim)
        
        g_token = self.global_proj(global_part).unsqueeze(1)
        u_tokens = self.unit_proj(board_part)
        h_tokens = self.hand_proj(hand_part)
        
        g_token = g_token + self.type_emb[0]
        u_tokens = u_tokens + self.type_emb[1]
        h_tokens = h_tokens + self.type_emb[2]
        
        all_tokens = torch.cat([g_token, u_tokens, h_tokens], dim=1)
        attended = self.transformer(all_tokens)
        
        state_context = attended[:, 0]
        action_hidden = self.action_encoder(action_tensor)
        
        if not is_batched:
            repeated_state = state_context.expand(action_hidden.shape[0], -1)
            logits = self.policy_head(torch.cat([repeated_state, action_hidden], dim=-1)).squeeze(-1)
            value = self.value_head(state_context).squeeze(-1)
        else:
            # Batch inference for training
            logits = self.policy_head(torch.cat([state_context.unsqueeze(1).expand(-1, action_hidden.shape[1], -1), action_hidden], dim=-1)).squeeze(-1)
            value = self.value_head(state_context).squeeze(-1)
            
        return logits, value


class RLAgent(BaseAgent):
    def __init__(
        self,
        *,
        hidden_dim: int = 256,
        learning_rate: float = 3e-4,
        sample_actions: bool = True,
        device: str = "cpu",
        seed: Optional[int] = None,
    ) -> None:
        super().__init__(name="rl", seed=seed)
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.sample_actions = sample_actions
        self.device = torch.device(device)

        self.state_dim: Optional[int] = None
        # We need to import ACTION_FEATURE_DIM carefully
        from RL_AI.SeaEngine.observation import ACTION_FEATURE_DIM
        self.action_dim: int = ACTION_FEATURE_DIM
        self.model: Optional[PPOActorCritic] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None
        self.last_output: Optional[RLAgentOutput] = None

    def select_action(
        self,
        state: Any, # Can be snapshot or GameState
        legal_actions: Sequence[Any],
        *,
        card_db: Optional[Dict[str, CardDefinition]] = None,
    ) -> Tuple[int, Any]:
        if not legal_actions:
            raise ValueError("RLAgent cannot select an action from an empty legal action list.")

        output = self.compute_policy_output(state, legal_actions)
        self.last_output = output
        return output.action_index, output.action

    def compute_policy_output(
        self,
        state: Any,
        legal_actions: Sequence[Any],
    ) -> RLAgentOutput:
        # Use SeaEngine observation builders
        from RL_AI.SeaEngine.observation import build_observation
        # Check if state is a snapshot (dict) or legacy GameState
        if isinstance(state, dict):
            snapshot = state
        else:
            # Conversion logic if needed, but here we assume SeaEngine snapshot
            snapshot = state 

        observation = build_observation({**snapshot, "actions": list(legal_actions)}, snapshot.get("active_player"))
        
        self.ensure_model(state_dim=len(observation.state_vector))

        logits_tensor, value_tensor = self.forward_tensors(observation.state_vector, observation.action_feature_vectors)
        dist = Categorical(logits=logits_tensor)
        chosen_index = int(dist.sample().item()) if self.sample_actions else int(torch.argmax(logits_tensor).item())
        
        return RLAgentOutput(
            action_index=chosen_index,
            action=legal_actions[chosen_index],
            state_vector=observation.state_vector,
            action_feature_vectors=observation.action_feature_vectors,
            logits=logits_tensor.detach().cpu().tolist(),
            probabilities=dist.probs.detach().cpu().tolist(),
            log_prob=float(dist.log_prob(torch.tensor(chosen_index, device=self.device)).item()),
            value=float(value_tensor.item()),
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
        self.ensure_model(len(state_vector))
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
