"""Observation and action feature builders for the C# SeaEngine snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

BOARD_SIZE = 6
MAX_CARD_SLOTS = 14

ROLE_ORDER = ["Leader", "Bishop", "Knight", "Rook", "Pawn"]
EFFECT_BUCKETS = ["DeployUnit", "DefaultMove", "DefaultAttack", "TurnEnd", "Skill"]
TARGET_BUCKETS = ["None", "Cell", "Unit", "Unit2", "Card"]


@dataclass
class SeaEngineObservation:
    unit_list: List[Dict[str, Any]]
    hand_list: List[Dict[str, Any]]
    global_vector: List[float]
    legal_action_mask: List[int]
    state_vector: List[float]
    action_feature_vectors: List[List[float]]


def _role_one_hot(role: str) -> List[float]:
    return [1.0 if role == name else 0.0 for name in ROLE_ORDER]


def _effect_one_hot(effect_id: str) -> List[float]:
    bucket = effect_id if effect_id in EFFECT_BUCKETS[:-1] else "Skill"
    return [1.0 if bucket == name else 0.0 for name in EFFECT_BUCKETS]


def _target_one_hot(target_type: str) -> List[float]:
    return [1.0 if target_type == name else 0.0 for name in TARGET_BUCKETS]


def _status_summary(card: Dict[str, Any]) -> tuple[float, float, float]:
    attack_mod = 0.0
    has_move_lock = 0.0
    has_attack_lock = 0.0
    for status in card.get("statuses", []):
        status_type = status.get("type", "")
        if status_type == "AttackModifier":
            attack_mod += float(status.get("value", 0.0))
        elif status_type == "MoveLock":
            has_move_lock = 1.0
        elif status_type == "AttackLock":
            has_attack_lock = 1.0
    return attack_mod, has_move_lock, has_attack_lock


def _normalize_pos(value: int) -> float:
    if value < 0:
        return -1.0
    return value / float(BOARD_SIZE - 1)


def _find_card(snapshot: Dict[str, Any], uid: str) -> Optional[Dict[str, Any]]:
    for card in snapshot.get("board", []):
        if card.get("uid") == uid:
            return card
    return None


def _enemy_leader(snapshot: Dict[str, Any], player_id: str) -> Optional[Dict[str, Any]]:
    for card in snapshot.get("board", []):
        if card.get("owner") != player_id and card.get("role") == "Leader" and card.get("is_placed"):
            return card
    return None


def _sort_cards(cards: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    role_rank = {name: idx for idx, name in enumerate(ROLE_ORDER)}
    return sorted(
        cards,
        key=lambda card: (
            card.get("owner", ""),
            role_rank.get(card.get("role", ""), 99),
            card.get("uid", ""),
        ),
    )


def build_fixed_state_vector(snapshot: Dict[str, Any], player_id: Optional[str] = None) -> List[float]:
    active_player = snapshot.get("active_player", "P1")
    player_id = player_id or active_player
    enemy_id = "P2" if player_id == "P1" else "P1"

    players = {player["id"]: player for player in snapshot.get("players", [])}
    own_player = players.get(player_id, {})
    enemy_player = players.get(enemy_id, {})

    own_leader = next(
        (card for card in snapshot.get("board", []) if card.get("owner") == player_id and card.get("role") == "Leader"),
        None,
    )
    enemy_leader = next(
        (card for card in snapshot.get("board", []) if card.get("owner") == enemy_id and card.get("role") == "Leader"),
        None,
    )

    global_vector: List[float] = [
        float(snapshot.get("turn", 1)) / 100.0,
        1.0 if active_player == player_id else 0.0,
        1.0 if snapshot.get("result") == "Ongoing" else 0.0,
        float(own_player.get("hand_count", 0)) / 7.0,
        float(enemy_player.get("hand_count", 0)) / 7.0,
        float(own_player.get("deck_count", 0)) / 7.0,
        float(enemy_player.get("deck_count", 0)) / 7.0,
        float(own_player.get("trash_count", 0)) / 7.0,
        float(enemy_player.get("trash_count", 0)) / 7.0,
        0.0 if own_leader is None else float(own_leader.get("hp", 0)) / max(1.0, float(own_leader.get("max_hp", 1))),
        0.0 if enemy_leader is None else float(enemy_leader.get("hp", 0)) / max(1.0, float(enemy_leader.get("max_hp", 1))),
    ]

    unit_vectors: List[float] = []
    cards = _sort_cards(snapshot.get("board", []))
    for card in cards[:MAX_CARD_SLOTS]:
        attack_mod, has_move_lock, has_attack_lock = _status_summary(card)
        unit_vectors.extend(
            [
                1.0 if card.get("owner") == player_id else -1.0,
                1.0 if card.get("is_placed") else 0.0,
                1.0 if card.get("is_moved") else 0.0,
                1.0 if card.get("is_attacked") else 0.0,
                _normalize_pos(int(card.get("pos_x", -1))),
                _normalize_pos(int(card.get("pos_y", -1))),
                float(card.get("hp", 0)) / max(1.0, float(card.get("max_hp", 1))),
                float(card.get("effective_atk", 0)) / 10.0,
                attack_mod / 5.0,
                has_move_lock,
                has_attack_lock,
                *_role_one_hot(str(card.get("role", ""))),
            ]
        )

    missing_slots = MAX_CARD_SLOTS - min(len(cards), MAX_CARD_SLOTS)
    if missing_slots > 0:
        unit_vectors.extend([0.0] * missing_slots * 16)

    return global_vector + unit_vectors


def encode_action_features(snapshot: Dict[str, Any], action: Dict[str, Any], player_id: Optional[str] = None) -> List[float]:
    player_id = player_id or snapshot.get("active_player", "P1")
    enemy_leader = _enemy_leader(snapshot, player_id)
    source = _find_card(snapshot, action.get("source", ""))
    target = action.get("target", {})
    target_type = str(target.get("type", "None"))
    target_card = _find_card(snapshot, str(target.get("guid", ""))) if target_type in {"Unit", "Card"} else None

    target_x = int(target.get("pos_x", -1))
    target_y = int(target.get("pos_y", -1))
    source_x = int(source.get("pos_x", -1)) if source else -1
    source_y = int(source.get("pos_y", -1)) if source else -1

    distance_to_enemy_leader = 0.0
    if enemy_leader and target_type == "Cell" and target_x >= 0 and target_y >= 0:
        ex = int(enemy_leader.get("pos_x", -1))
        ey = int(enemy_leader.get("pos_y", -1))
        if ex >= 0 and ey >= 0:
            distance_to_enemy_leader = (abs(target_x - ex) + abs(target_y - ey)) / 10.0

    attack_mod, has_move_lock, has_attack_lock = _status_summary(source) if source else (0.0, 0.0, 0.0)

    return [
        *_effect_one_hot(str(action.get("effect_id", ""))),
        *_target_one_hot(target_type),
        0.0 if source is None else (1.0 if source.get("owner") == player_id else -1.0),
        0.0 if source is None else float(source.get("effective_atk", 0)) / 10.0,
        0.0 if source is None else float(source.get("hp", 0)) / max(1.0, float(source.get("max_hp", 1))),
        0.0 if source is None else attack_mod / 5.0,
        has_move_lock,
        has_attack_lock,
        0.0 if source is None else _normalize_pos(source_x),
        0.0 if source is None else _normalize_pos(source_y),
        *_role_one_hot("" if source is None else str(source.get("role", ""))),
        0.0 if target_card is None else (1.0 if target_card.get("owner") != player_id else -1.0),
        0.0 if target_card is None else float(target_card.get("effective_atk", 0)) / 10.0,
        0.0 if target_card is None else float(target_card.get("hp", 0)) / max(1.0, float(target_card.get("max_hp", 1))),
        0.0 if target_card is None else (1.0 if target_card.get("role") == "Leader" else 0.0),
        _normalize_pos(target_x),
        _normalize_pos(target_y),
        distance_to_enemy_leader,
    ]


ACTION_FEATURE_DIM = len(encode_action_features({"board": [], "actions": [], "players": [], "active_player": "P1"}, {"effect_id": "TurnEnd", "target": {"type": "None", "pos_x": -1, "pos_y": -1}}))


def build_observation(snapshot: Dict[str, Any], player_id: Optional[str] = None) -> SeaEngineObservation:
    player_id = player_id or snapshot.get("active_player", "P1")
    players = {player["id"]: player for player in snapshot.get("players", [])}
    own_player = players.get(player_id, {})

    unit_list = _sort_cards(snapshot.get("board", []))
    hand_list = own_player.get("hand", [])
    state_vector = build_fixed_state_vector(snapshot, player_id)
    action_feature_vectors = [encode_action_features(snapshot, action, player_id) for action in snapshot.get("actions", [])]

    return SeaEngineObservation(
        unit_list=unit_list,
        hand_list=hand_list,
        global_vector=state_vector[:11],
        legal_action_mask=[1 for _ in snapshot.get("actions", [])],
        state_vector=state_vector,
        action_feature_vectors=action_feature_vectors,
    )
