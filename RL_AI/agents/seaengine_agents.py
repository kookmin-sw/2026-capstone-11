"""Agents that operate on C# SeaEngine snapshots and action lists."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
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


BOARD_SIZE = 6
DEFAULT_MODEL_HIDDEN_DIM = 192


def default_model_hidden_dim() -> int:
    raw_value = os.getenv("SEAENGINE_MODEL_HIDDEN_DIM")
    if raw_value is None or str(raw_value).strip() == "":
        return DEFAULT_MODEL_HIDDEN_DIM
    try:
        value = int(str(raw_value).strip())
    except ValueError:
        print(f"[!] ignored invalid SEAENGINE_MODEL_HIDDEN_DIM={raw_value!r}")
        return DEFAULT_MODEL_HIDDEN_DIM
    return max(32, value)


def infer_hidden_dim_from_state_dict(state_dict: Dict[str, torch.Tensor], fallback: Optional[int] = None) -> int:
    """Infer model width from a checkpoint so old 128-wide models still load cleanly."""
    for key in ("global_proj.weight", "policy_head.0.weight", "value_head.0.weight"):
        tensor = state_dict.get(key)
        if tensor is not None and getattr(tensor, "ndim", 0) >= 1:
            return int(tensor.shape[0])
    return default_model_hidden_dim() if fallback is None else int(fallback)


def _card_id(card: Dict[str, Any] | None) -> str:
    if not card:
        return ""
    return str(card.get("card_id", card.get("id", card.get("name", ""))))


def _role(card: Dict[str, Any] | None) -> str:
    if not card:
        return ""
    role = str(card.get("role", ""))
    if role:
        return role
    card_id = _card_id(card)
    suffix = card_id.split("_")[-1][-1:] if card_id else ""
    return {"L": "Leader", "B": "Bishop", "N": "Knight", "R": "Rook", "P": "Pawn"}.get(suffix, "")


def _players(snapshot: Dict[str, Any]) -> tuple[str, str]:
    active = str(snapshot.get("active_player", ""))
    ids = [str(player.get("id", "")) for player in snapshot.get("players", []) if str(player.get("id", ""))]
    enemy = next((pid for pid in ids if pid != active), "")
    return active, enemy


def _leader(snapshot: Dict[str, Any], owner: str) -> Optional[Dict[str, Any]]:
    for card in snapshot.get("board", []):
        if card.get("owner") == owner and card.get("is_placed") and _role(card) == "Leader":
            return card
    return None


def _distance_xy(x1: int, y1: int, x2: int, y2: int) -> int:
    if min(x1, y1, x2, y2) < 0:
        return 99
    return abs(x1 - x2) + abs(y1 - y2)


def _target_card(snapshot: Dict[str, Any], action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    target = action.get("target", {}) or {}
    target_uid = str(target.get("guid", ""))
    if not target_uid:
        return None
    return next((card for card in snapshot.get("board", []) if str(card.get("uid", "")) == target_uid), None)


def _source_card(snapshot: Dict[str, Any], action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    source_uid = str(action.get("source", ""))
    if not source_uid:
        return None
    for card in snapshot.get("board", []):
        if str(card.get("uid", "")) == source_uid:
            return card
    for player in snapshot.get("players", []):
        for card in player.get("hand", []):
            if str(card.get("uid", "")) == source_uid:
                return card
    return None


def _cell_after_action(action: Dict[str, Any], source: Optional[Dict[str, Any]]) -> tuple[int, int]:
    target = action.get("target", {}) or {}
    if str(target.get("type", "")) == "Cell":
        return int(target.get("pos_x", -1)), int(target.get("pos_y", -1))
    if source:
        return int(source.get("pos_x", -1)), int(source.get("pos_y", -1))
    return -1, -1


def _attackers_on(snapshot: Dict[str, Any], target: Optional[Dict[str, Any]], *, by_owner: str) -> int:
    if not target or not target.get("is_placed"):
        return 0
    tx = int(target.get("pos_x", -1))
    ty = int(target.get("pos_y", -1))
    count = 0
    for card in snapshot.get("board", []):
        if card.get("owner") != by_owner or not card.get("is_placed"):
            continue
        cx = int(card.get("pos_x", -1))
        cy = int(card.get("pos_y", -1))
        if _distance_xy(cx, cy, tx, ty) <= 2:
            count += 1
    return count


class SeaEngineAgent(ABC):
    def __init__(self, name: str, seed: Optional[int] = None) -> None:
        self.name = name
        self.seed = seed
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
        target_card = _target_card(snapshot, action)
        source = _source_card(snapshot, action)
        active, enemy = _players(snapshot)
        enemy_leader = _leader(snapshot, enemy)

        score = 0
        if effect_id == "DefaultAttack":
            score += 95
        elif effect_id == "DeployUnit":
            score += 55
        elif effect_id == "DefaultMove":
            score += 25
        elif effect_id == "TurnEnd":
            score -= 100
        else:
            score += 65

        if target_type == "Unit" and target_card is not None:
            target_hp = int(target_card.get("hp", 10))
            source_atk = int((source or {}).get("effective_atk", (source or {}).get("atk", 0)))
            if _role(target_card) == "Leader":
                score += 150
            if source_atk >= target_hp > 0:
                score += 45
            score += 15 - min(target_hp, 15)

        if target_type == "Cell":
            target_x = int(target.get("pos_x", -1))
            target_y = int(target.get("pos_y", -1))
            if enemy_leader is not None:
                distance = _distance_xy(target_x, target_y, int(enemy_leader.get("pos_x", -1)), int(enemy_leader.get("pos_y", -1)))
                score += max(0, 12 - distance * 2)
            if 2 <= target_x <= 3 and 2 <= target_y <= 3:
                score += 8

        if source is not None:
            card_id = _card_id(source)
            role = _role(source)
            if effect_id == "DeployUnit":
                score += {"Leader": 12, "Knight": 10, "Bishop": 8, "Rook": 8, "Pawn": 5}.get(role, 0)
            if card_id in {"Or_N", "Cl_B", "Cl_N"}:
                score += 4

        score += self.rng.randint(0, 3)
        return score


class SeaEngineRuleBasedAgent(SeaEngineAgent):
    """A stronger tactical baseline without search or engine replay support."""

    def __init__(self, seed: Optional[int] = None) -> None:
        super().__init__("rule_based", seed=seed)

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

    def _score_action(self, snapshot: Dict[str, Any], action: Dict[str, Any]) -> float:
        active, enemy = _players(snapshot)
        own_leader = _leader(snapshot, active)
        enemy_leader = _leader(snapshot, enemy)
        source = _source_card(snapshot, action)
        target_card = _target_card(snapshot, action)
        effect_id = str(action.get("effect_id", ""))
        target = action.get("target", {}) or {}
        target_type = str(target.get("type", "None"))
        source_role = _role(source)
        source_id = _card_id(source)
        source_atk = float((source or {}).get("effective_atk", (source or {}).get("atk", 0.0)))

        score = 0.0
        if effect_id == "TurnEnd":
            non_end_actions = [a for a in snapshot.get("actions", []) if str(a.get("effect_id", "")) != "TurnEnd"]
            return -200.0 - len(non_end_actions)
        if effect_id == "DefaultAttack":
            score += 110.0
        elif effect_id == "DeployUnit":
            score += 58.0
        elif effect_id == "DefaultMove":
            score += 28.0
        else:
            score += 72.0

        if target_card is not None:
            target_role = _role(target_card)
            target_hp = float(target_card.get("hp", 0.0))
            target_atk = float(target_card.get("effective_atk", target_card.get("atk", 0.0)))
            if target_role == "Leader":
                score += 190.0
                score += max(0.0, 40.0 - target_hp * 4.0)
            if source_atk >= target_hp > 0:
                score += 55.0 + target_atk * 3.0
                if target_role in {"Bishop", "Knight", "Rook"}:
                    score += 12.0
            if source is not None and target_atk >= float(source.get("hp", 0.0)) > 0:
                score -= 18.0
            score += max(0.0, 16.0 - target_hp)
            score += _attackers_on(snapshot, target_card, by_owner=active) * 3.0

        tx, ty = _cell_after_action(action, source)
        if target_type == "Cell" and tx >= 0 and ty >= 0:
            if 2 <= tx <= 3 and 2 <= ty <= 3:
                score += 12.0
            if enemy_leader is not None:
                before = _distance_xy(
                    int((source or {}).get("pos_x", -1)),
                    int((source or {}).get("pos_y", -1)),
                    int(enemy_leader.get("pos_x", -1)),
                    int(enemy_leader.get("pos_y", -1)),
                )
                after = _distance_xy(tx, ty, int(enemy_leader.get("pos_x", -1)), int(enemy_leader.get("pos_y", -1)))
                score += max(-10.0, float(before - after) * 8.0)
                if after <= 2:
                    score += 18.0
            if own_leader is not None:
                own_after = _distance_xy(tx, ty, int(own_leader.get("pos_x", -1)), int(own_leader.get("pos_y", -1)))
                if source_role != "Leader" and own_after <= 2:
                    score += 4.0

        if effect_id == "DeployUnit":
            score += {"Leader": 14.0, "Knight": 13.0, "Bishop": 11.0, "Rook": 10.0, "Pawn": 7.0}.get(source_role, 0.0)
            if source_id in {"Cl_B", "Or_N"}:
                score += 6.0
        if source_id == "Or_N" and target_card is not None:
            score += 8.0
        if source_id in {"Cl_B", "Cl_N", "Cl_R"} and effect_id not in {"TurnEnd", "DefaultMove"}:
            score += 5.0

        own_board = [c for c in snapshot.get("board", []) if c.get("owner") == active and c.get("is_placed")]
        enemy_board = [c for c in snapshot.get("board", []) if c.get("owner") == enemy and c.get("is_placed")]
        score += min(len(own_board), 7) * 1.2
        score -= min(len(enemy_board), 7) * 0.6
        score += self.rng.random() * 0.01
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
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: Optional[int] = None) -> None:
        super().__init__()
        hidden_dim = default_model_hidden_dim() if hidden_dim is None else int(hidden_dim)
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
        
        # Type embeddings:
        # 0 = global, 1 = board/unit, 2 = hand, 3 = legal action
        self.type_emb = nn.Parameter(torch.randn(4, hidden_dim))
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim, 
            nhead=4, 
            dim_feedforward=hidden_dim * 4, 
            batch_first=True, 
            activation='gelu'
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=1)
        
        # Action token projection
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

        # Split state tokens
        global_part = state_tensor[:, :self.global_dim]
        board_part = state_tensor[
            :,
            self.global_dim : self.global_dim + self.num_units * self.unit_dim,
        ].reshape(batch_size, self.num_units, self.unit_dim)
        hand_part = state_tensor[
            :,
            self.global_dim + self.num_units * self.unit_dim :,
        ].reshape(batch_size, self.num_hand, self.hand_dim)

        # Project state tokens
        g_token = self.global_proj(global_part).unsqueeze(1) + self.type_emb[0]
        u_tokens = self.unit_proj(board_part) + self.type_emb[1]
        h_tokens = self.hand_proj(hand_part) + self.type_emb[2]

        state_tokens = torch.cat([g_token, u_tokens, h_tokens], dim=1)
        state_token_count = state_tokens.shape[1]

        # Project legal actions as Transformer tokens.
        # Unbatched: action_tensor = [A, action_dim]
        # Batched:   action_tensor = [B, A, action_dim]
        if action_tensor.dim() == 2:
            action_hidden = self.action_encoder(action_tensor).unsqueeze(0)
            action_pad_mask = torch.zeros(
                (batch_size, action_hidden.shape[1]),
                dtype=torch.bool,
                device=action_hidden.device,
            )
        else:
            action_hidden = self.action_encoder(action_tensor)

            # Padded action rows are all-zero vectors in batch inference/training.
            # Mask them so padded action tokens do not affect state/action attention.
            action_pad_mask = action_tensor.abs().sum(dim=-1).eq(0.0)

        a_tokens = action_hidden + self.type_emb[3]
        all_tokens = torch.cat([state_tokens, a_tokens], dim=1)

        # Only action padding is masked. State padding remains as before because
        # fixed zero-filled board/hand slots were already part of the model.
        state_pad_mask = torch.zeros(
            (batch_size, state_token_count),
            dtype=torch.bool,
            device=all_tokens.device,
        )
        transformer_pad_mask = torch.cat([state_pad_mask, action_pad_mask], dim=1)

        attended = self.transformer(
            all_tokens,
            src_key_padding_mask=transformer_pad_mask,
        )

        state_context = attended[:, 0]
        action_context = attended[:, state_token_count:]

        if not is_batched:
            action_context = action_context.squeeze(0)
            repeated_state = state_context.expand(action_context.shape[0], -1)
            logits = self.policy_head(torch.cat([repeated_state, action_context], dim=-1)).squeeze(-1)
            value = self.value_head(state_context).squeeze(-1)
        else:
            repeated_state = state_context.unsqueeze(1).expand(-1, action_context.shape[1], -1)
            logits = self.policy_head(torch.cat([repeated_state, action_context], dim=-1)).squeeze(-1)
            value = self.value_head(state_context).squeeze(-1)

        return logits, value


class SeaEngineRLAgent(SeaEngineAgent):
    def __init__(
        self,
        *,
        hidden_dim: Optional[int] = None,
        learning_rate: float = 3e-4,
        sample_actions: bool = True,
        device: str = "auto",
        seed: Optional[int] = None,
    ) -> None:
        super().__init__("rl", seed=seed)
        if seed is not None:
            torch.manual_seed(int(seed))
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(int(seed))
        self.hidden_dim = default_model_hidden_dim() if hidden_dim is None else int(hidden_dim)
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
        if self.seed is not None:
            torch.manual_seed(int(self.seed))
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(int(self.seed))
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
            state_vector = list(snapshot.get("state_vector") or [])
            action_feature_vectors = [list(a) for a in snapshot.get("action_feature_vectors") or []]
        else:
            observation = build_observation({**snapshot, "actions": list(legal_actions)}, snapshot.get("active_player"))
            state_vector = list(observation.state_vector)
            action_feature_vectors = [list(a) for a in observation.action_feature_vectors]
        
        with torch.no_grad():
            logits_tensor, value_tensor = self.forward_tensors(state_vector, action_feature_vectors)

        dist = Categorical(logits=logits_tensor)
        chosen_index = int(dist.sample().item()) if self.sample_actions else int(torch.argmax(logits_tensor).item())
        output = SeaEngineRLAgentOutput(
            action_index=chosen_index,
            action=legal_actions[chosen_index],
            state_vector=state_vector,
            action_feature_vectors=action_feature_vectors,
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


class SeaEngineBeliefMCTSAgent(SeaEngineAgent):
    """Lightweight belief-search wrapper for an RL policy.

    Restore-based search is the only search mode now. It replays from the
    captured engine state and keeps the search budget intentionally shallow so
    it remains usable in large evaluation sweeps.
    """

    def __init__(
        self,
        base_agent: SeaEngineRLAgent,
        *,
        simulations: int = 1,
        top_k: int = 3,
        rollout_steps: int = 1,
        mode: str = "restore",
        c_puct: float = 1.25,
        noise: float = 0.02,
        value_weight: float = 0.05,
        candidate_mixing_strategy: str = "policy_prior_plus_heuristic_topk",
        seed: Optional[int] = None,
    ) -> None:
        super().__init__("belief_mcts", seed=seed)
        self.base_agent = base_agent
        self.simulations = max(1, int(simulations))
        self.top_k = max(1, int(top_k))
        self.rollout_steps = max(1, int(rollout_steps))
        self.mode = "restore"
        self.c_puct = max(0.0, float(c_puct))
        self.noise = max(0.0, float(noise))
        self.value_weight = max(0.0, float(value_weight))
        self.candidate_mixing_strategy = str(candidate_mixing_strategy or "policy_prior_plus_heuristic_topk").strip().lower()
        self.heuristic_agent = SeaEngineRuleBasedAgent(seed=seed)
        self.player1_deck = ""
        self.player2_deck = ""
        self.card_data_path: Optional[str] = None
        self._history: list[Dict[str, Any]] = []
        self._replay_available = True
        self.last_output: Optional[SeaEngineRLAgentOutput] = None
        self.last_search: Dict[str, Any] = {}
        self._search_stats: Dict[str, int] = {}
        self._search_session = None
        self._reset_search_stats()

    @property
    def device(self):
        return self.base_agent.device

    @property
    def model(self):
        return self.base_agent.model

    @property
    def sample_actions(self) -> bool:
        return self.base_agent.sample_actions

    @sample_actions.setter
    def sample_actions(self, enabled: bool) -> None:
        self.base_agent.sample_actions = enabled

    @contextmanager
    def sampling_mode(self, enabled: bool):
        with self.base_agent.sampling_mode(enabled):
            yield

    @classmethod
    def from_env(cls, base_agent: SeaEngineRLAgent, *, seed: Optional[int] = None) -> "SeaEngineBeliefMCTSAgent":
        import os

        def _env_int(name: str, default: int) -> int:
            try:
                return int(str(os.environ.get(name, default)).strip())
            except Exception:
                return default

        def _env_float(name: str, default: float) -> float:
            try:
                return float(str(os.environ.get(name, default)).strip())
            except Exception:
                return default

        def _env_str(name: str, default: str) -> str:
            raw = str(os.environ.get(name, default)).strip()
            return raw or default

        return cls(
            base_agent,
            simulations=_env_int("SEAENGINE_BELIEF_MCTS_SIMS", 1),
            top_k=_env_int("SEAENGINE_BELIEF_MCTS_TOP_K", 2),
            rollout_steps=_env_int("SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS", 1),
            mode="restore",
            c_puct=_env_float("SEAENGINE_BELIEF_MCTS_C_PUCT", 1.25),
            noise=_env_float("SEAENGINE_BELIEF_MCTS_NOISE", 0.02),
            value_weight=_env_float("SEAENGINE_BELIEF_MCTS_VALUE_WEIGHT", 0.05),
            candidate_mixing_strategy=_env_str(
                "SEAENGINE_BELIEF_MCTS_CANDIDATE_MIXING_STRATEGY",
                "policy_prior_plus_heuristic_topk",
            ),
            seed=seed,
        )

    def reset_search_history(
        self,
        *,
        player1_deck: str = "",
        player2_deck: str = "",
        card_data_path: Optional[str] = None,
        replay_available: bool = True,
    ) -> None:
        self.player1_deck = str(player1_deck or "")
        self.player2_deck = str(player2_deck or "")
        self.card_data_path = card_data_path
        self._history = []
        self._replay_available = bool(replay_available)
        self._reset_search_stats()
        if self._search_session is not None and card_data_path is not None:
            self._search_session.close()
            self._search_session = None

    def set_replay_available(self, enabled: bool) -> None:
        self._replay_available = bool(enabled)

    def _reset_search_stats(self) -> None:
        self._search_stats = {
            "total_searches": 0,
            "single_action": 0,
            "restore_mcts": 0,
            "policy_fallback": 0,
            "engine_state_unavailable": 0,
            "replay_failed": 0,
            "failures_total": 0,
            "changed_count": 0,
        }

    def get_search_summary(self) -> Dict[str, Any]:
        total = int(self._search_stats.get("total_searches", 0))
        changed = int(self._search_stats.get("changed_count", 0))
        failures_total = int(self._search_stats.get("failures_total", 0))
        summary = dict(self._search_stats)
        summary["changed_rate"] = 0.0 if total <= 0 else changed / total
        summary["avg_failures_per_search"] = 0.0 if total <= 0 else failures_total / total
        summary["policy_fallback_rate"] = 0.0 if total <= 0 else float(summary.get("policy_fallback", 0)) / total
        summary["restore_mcts_rate"] = 0.0 if total <= 0 else float(summary.get("restore_mcts", 0)) / total
        return summary

    def _record_search_stats(self, *, mode: str, reason: str = "", failures: int = 0, policy_choice: Any = None, chosen_index: Any = None) -> None:
        stats = self._search_stats
        stats["total_searches"] = int(stats.get("total_searches", 0)) + 1
        if mode in stats:
            stats[mode] = int(stats.get(mode, 0)) + 1
        if reason in stats:
            stats[reason] = int(stats.get(reason, 0)) + 1
        stats["failures_total"] = int(stats.get("failures_total", 0)) + max(0, int(failures))
        if policy_choice is not None and chosen_index is not None and int(policy_choice) != int(chosen_index):
            stats["changed_count"] = int(stats.get("changed_count", 0)) + 1

    def requires_engine_state(self) -> bool:
        return True

    def observe_transition(self, snapshot: Dict[str, Any], action: Dict[str, Any]) -> None:
        if self._replay_available:
            self._history.append(self._action_signature(snapshot, action))

    def compute_policy_output(
        self,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> SeaEngineRLAgentOutput:
        idx, action = self.select_action(snapshot, legal_actions)
        base_output = self.base_agent.last_output
        if base_output is None:
            raise RuntimeError("belief MCTS did not produce a base policy output")
        output = SeaEngineRLAgentOutput(
            action_index=idx,
            action=action,
            state_vector=base_output.state_vector,
            action_feature_vectors=base_output.action_feature_vectors,
            logits=base_output.logits,
            probabilities=base_output.probabilities,
            log_prob=base_output.log_prob,
            value=base_output.value,
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
        with self.base_agent.sampling_mode(False):
            policy_output = self.base_agent.compute_policy_output(snapshot, legal_actions)
        self.last_output = policy_output
        if len(legal_actions) == 1:
            self.last_search = {
                "mode": "single_action",
                "reason": "only_one_legal_action",
                "policy_choice": policy_output.action_index,
                "chosen_index": policy_output.action_index,
            }
            self._record_search_stats(mode="single_action", reason="only_one_legal_action", policy_choice=policy_output.action_index, chosen_index=policy_output.action_index)
            self._log_last_search()
            return policy_output.action_index, policy_output.action

        state_json = str(snapshot.get("_engine_state", ""))
        state_game = snapshot.get("_engine_game")
        if not state_json and state_game is None:
            self.last_search = {
                "mode": "policy_fallback",
                "reason": "engine_state_unavailable",
                "failures": 0,
                "policy_choice": policy_output.action_index,
                "chosen_index": policy_output.action_index,
            }
            self._record_search_stats(mode="policy_fallback", reason="engine_state_unavailable", failures=0, policy_choice=policy_output.action_index, chosen_index=policy_output.action_index)
            self._log_last_search()
            return policy_output.action_index, policy_output.action

        candidates = self._candidate_indices(policy_output, snapshot, legal_actions)
        root_player = str(snapshot.get("active_player", ""))
        scores = {idx: [] for idx in candidates}
        failures = 0
        session = self._search_session
        if session is None:
            from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession

            session = PythonNetSession(card_data_path=self.card_data_path)
            session.start()
            self._search_session = session

        for idx in candidates:
            candidate_signature = self._action_signature(snapshot, legal_actions[idx])
            with session.muted_native_output():
                for _ in range(self.simulations):
                    try:
                        score = self._simulate_candidate(
                            session,
                            candidate_signature,
                            root_player=root_player,
                            state_json=state_json,
                            state_game=state_game,
                        )
                    except Exception:
                        failures += 1
                        score = None
                    if score is not None:
                        scores[idx].append(float(score))

        averaged = {idx: (sum(values) / len(values) if values else -999.0) for idx, values in scores.items()}
        if all(value <= -999.0 for value in averaged.values()):
            self.last_search = {
                "mode": "policy_fallback",
                "reason": "replay_failed",
                "failures": failures,
                "policy_choice": policy_output.action_index,
                "chosen_index": policy_output.action_index,
            }
            self._record_search_stats(mode="policy_fallback", reason="replay_failed", failures=failures, policy_choice=policy_output.action_index, chosen_index=policy_output.action_index)
            self._log_last_search()
            return policy_output.action_index, policy_output.action

        chosen_index = max(candidates, key=lambda idx: (averaged[idx], float(policy_output.probabilities[idx])))
        self.last_search = {
            "mode": "restore_mcts",
            "simulations": self.simulations,
            "rollout_steps": self.rollout_steps,
            "candidates": candidates,
            "mean_values": averaged,
            "failures": failures,
            "policy_choice": policy_output.action_index,
            "chosen_index": chosen_index,
        }
        self._record_search_stats(mode="restore_mcts", failures=failures, policy_choice=policy_output.action_index, chosen_index=chosen_index)
        self._log_last_search()
        return chosen_index, legal_actions[chosen_index]

    def _log_last_search(self) -> None:
        if os.environ.get("SEAENGINE_BELIEF_MCTS_DEBUG", "0") != "1":
            return
        search = self.last_search or {}
        mode = search.get("mode", "")
        reason = search.get("reason", "")
        failures = search.get("failures", "")
        policy_choice = search.get("policy_choice", "")
        chosen_index = search.get("chosen_index", "")
        simulations = search.get("simulations", "")
        rollout_steps = search.get("rollout_steps", "")
        print(
            "[belief_mcts] "
            f"mode={mode} "
            f"reason={reason} "
            f"failures={failures} "
            f"policy_choice={policy_choice} "
            f"chosen_index={chosen_index} "
            f"sims={simulations} "
            f"rollout_steps={rollout_steps}"
        )

    def _candidate_indices(
        self,
        policy_output: SeaEngineRLAgentOutput,
        snapshot: Dict[str, Any],
        legal_actions: Sequence[Dict[str, Any]],
    ) -> list[int]:
        by_prior = sorted(range(len(legal_actions)), key=lambda idx: float(policy_output.probabilities[idx]), reverse=True)
        by_heuristic = sorted(
            range(len(legal_actions)),
            key=lambda idx: self.heuristic_agent._score_action(snapshot, legal_actions[idx]),
            reverse=True,
        )
        if self.candidate_mixing_strategy == "policy_prior_only":
            return by_prior[: min(len(legal_actions), max(self.top_k, 1))]
        if self.candidate_mixing_strategy == "heuristic_only":
            return by_heuristic[: min(len(legal_actions), max(self.top_k, 1))]
        selected: list[int] = []
        for rows in (by_prior, by_heuristic):
            for idx in rows:
                if idx not in selected:
                    selected.append(idx)
                if len(selected) >= self.top_k:
                    break
            if len(selected) >= self.top_k:
                break
        return selected[: min(len(legal_actions), max(self.top_k, 1))]

    def _can_replay(self) -> bool:
        return self._replay_available and bool(self.player1_deck) and bool(self.player2_deck)

    def _simulate_candidate(
        self,
        session: Any,
        candidate_signature: Dict[str, Any],
        *,
        root_player: str,
        state_json: str = "",
        state_game: Any = None,
        player1_id: str = "P1",
        player2_id: str = "P2",
    ) -> float:
        if state_json:
            snapshot = session.restore_state(state_json, logger_mode="silent")
        elif state_game is not None:
            from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession

            clone_fn = getattr(state_game, "Clone", None)
            if not callable(clone_fn):
                clone_fn = getattr(state_game, "Fork", None)
            if not callable(clone_fn):
                raise RuntimeError("SeaEngine.Game.Clone/Fork is not available")
            cloned_game = clone_fn()
            session = PythonNetSession.wrap_game(
                cloned_game,
                card_data_path=self.card_data_path,
            )
            snapshot = session.snapshot()
        else:
            raise RuntimeError("No usable engine state available for belief search")

        candidate = self._find_matching_action(snapshot, candidate_signature)
        if candidate is None:
            return -999.0

        snapshot = session.apply_action(str(candidate["uid"]))
        with self.base_agent.sampling_mode(False):
            for _ in range(self.rollout_steps):
                if snapshot.get("result") != "Ongoing":
                    break
                actions = list(snapshot.get("actions", []))
                if not actions:
                    break
                _idx, rollout_action = self.heuristic_agent.select_action(snapshot, actions)
                snapshot = session.apply_action(str(rollout_action["uid"]))
            value_bias = self._estimate_value_bias(snapshot)
        return self._score_snapshot(snapshot, root_player=root_player) + (self.value_weight * value_bias)

    def _estimate_value_bias(self, snapshot: Dict[str, Any]) -> float:
        actions = list(snapshot.get("actions", []))
        if not actions:
            return 0.0
        with self.base_agent.sampling_mode(False):
            output = self.base_agent.compute_policy_output(snapshot, actions)
        value = float(output.value)
        return max(-1.0, min(1.0, value))

    def _score_snapshot(self, snapshot: Dict[str, Any], *, root_player: str) -> float:
        winner = str(snapshot.get("winner_id", ""))
        if str(snapshot.get("result", "Ongoing")) != "Ongoing":
            if winner == root_player:
                return 1.0
            if winner:
                return -1.0
            return 0.0
        enemy = next((p for p in ["P1", "P2"] if p != root_player), "")
        own_leader = _leader(snapshot, root_player)
        enemy_leader = _leader(snapshot, enemy)
        own_hp = float((own_leader or {}).get("hp", 0.0))
        enemy_hp = float((enemy_leader or {}).get("hp", 0.0))
        own_board = sum(1 for c in snapshot.get("board", []) if c.get("owner") == root_player and c.get("is_placed"))
        enemy_board = sum(1 for c in snapshot.get("board", []) if c.get("owner") == enemy and c.get("is_placed"))
        return math.tanh(((own_hp - enemy_hp) / 10.0) + ((own_board - enemy_board) * 0.08))

    def _action_signature(self, snapshot: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        source = _source_card(snapshot, action)
        target_card = _target_card(snapshot, action)
        target = action.get("target", {}) or {}
        return {
            "active_player": str(snapshot.get("active_player", "")),
            "effect_id": str(action.get("effect_id", "")),
            "source_card_id": _card_id(source),
            "source_role": _role(source),
            "source_owner": str((source or {}).get("owner", "")),
            "source_pos": (int((source or {}).get("pos_x", -1)), int((source or {}).get("pos_y", -1))),
            "target_type": str(target.get("type", "None")),
            "target_card_id": _card_id(target_card),
            "target_owner": str((target_card or {}).get("owner", "")),
            "target_pos": (int(target.get("pos_x", -1)), int(target.get("pos_y", -1))),
        }

    def _action_signature_key(self, snapshot: Dict[str, Any], action: Dict[str, Any]) -> tuple[Any, ...]:
        sig = self._action_signature(snapshot, action)
        return (
            sig["active_player"],
            sig["effect_id"],
            sig["source_card_id"],
            sig["source_role"],
            sig["source_owner"],
            sig["source_pos"],
            sig["target_type"],
            sig["target_card_id"],
            sig["target_owner"],
            sig["target_pos"],
        )

    def _signature_key(self, signature: Dict[str, Any]) -> tuple[Any, ...]:
        return (
            str(signature.get("active_player", "")),
            str(signature.get("effect_id", "")),
            str(signature.get("source_card_id", "")),
            str(signature.get("source_role", "")),
            str(signature.get("source_owner", "")),
            tuple(signature.get("source_pos", (-1, -1))),
            str(signature.get("target_type", "")),
            str(signature.get("target_card_id", "")),
            str(signature.get("target_owner", "")),
            tuple(signature.get("target_pos", (-1, -1))),
        )

    def _find_matching_action(self, snapshot: Dict[str, Any], signature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        target_key = self._signature_key(signature)
        action_map = {
            self._action_signature_key(snapshot, action): action
            for action in snapshot.get("actions", [])
        }
        action = action_map.get(target_key)
        if action is not None:
            return action

        scored: list[tuple[int, Dict[str, Any]]] = []
        for current_key, current_action in action_map.items():
            score = 0
            for idx in range(8):
                if current_key[idx] == target_key[idx]:
                    score += 2
            if current_key[5] == target_key[5]:
                score += 1
            if current_key[9] == target_key[9]:
                score += 2
            if score >= 8:
                scored.append((score, current_action))
        if not scored:
            return None
        scored.sort(key=lambda row: row[0], reverse=True)
        return scored[0][1]


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
            key in {"global_proj.weight", "unit_proj.weight", "hand_proj.weight", "action_encoder.0.weight"}
            and source_tensor.ndim == 2
            and current_tensor.ndim == 2
        ):
            merged = current_tensor.clone()
            rows = min(merged.shape[0], source_tensor.shape[0])
            cols = min(merged.shape[1], source_tensor.shape[1])
            merged[:rows, :cols] = source_tensor[:rows, :cols]
            compatible_state[key] = merged
            continue
        if key == "type_emb" and source_tensor.ndim == 2 and current_tensor.ndim == 2:
            merged = current_tensor.clone()
            rows = min(merged.shape[0], source_tensor.shape[0])
            cols = min(merged.shape[1], source_tensor.shape[1])
            merged[:rows, :cols] = source_tensor[:rows, :cols]
            compatible_state[key] = merged
            continue
    model.load_state_dict(compatible_state, strict=False)
