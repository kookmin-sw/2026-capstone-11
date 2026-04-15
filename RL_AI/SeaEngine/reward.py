"""Terminal reward helpers for SeaEngine-backed training."""

from __future__ import annotations

from typing import Any, Dict


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _leader_hp(snapshot: Dict[str, Any], owner_id: str) -> float:
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) != owner_id:
            continue
        if str(card.get("role", "")) != "Leader":
            continue
        return _safe_float(card.get("hp", 0.0), 0.0)
    return 0.0


def _placed_units(snapshot: Dict[str, Any], owner_id: str) -> int:
    count = 0
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) != owner_id:
            continue
        if bool(card.get("is_placed", False)):
            count += 1
    return count


def _find_enemy_id(snapshot: Dict[str, Any], ai_id: str) -> str:
    for player in snapshot.get("players", []):
        pid = str(player.get("id", ""))
        if pid and pid != ai_id:
            return pid
    owners = {str(card.get("owner", "")) for card in snapshot.get("board", []) if str(card.get("owner", ""))}
    for owner in owners:
        if owner != ai_id:
            return owner
    return ""


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def dense_reward_from_transition(
    prev_snapshot: Dict[str, Any],
    next_snapshot: Dict[str, Any],
    *,
    ai_id: str,
    action_effect_id: str = "",
) -> float:
    enemy_id = _find_enemy_id(next_snapshot, ai_id) or _find_enemy_id(prev_snapshot, ai_id)

    prev_ai_leader_hp = _leader_hp(prev_snapshot, ai_id)
    next_ai_leader_hp = _leader_hp(next_snapshot, ai_id)
    prev_enemy_leader_hp = _leader_hp(prev_snapshot, enemy_id) if enemy_id else 0.0
    next_enemy_leader_hp = _leader_hp(next_snapshot, enemy_id) if enemy_id else 0.0

    prev_ai_units = _placed_units(prev_snapshot, ai_id)
    next_ai_units = _placed_units(next_snapshot, ai_id)
    prev_enemy_units = _placed_units(prev_snapshot, enemy_id) if enemy_id else 0
    next_enemy_units = _placed_units(next_snapshot, enemy_id) if enemy_id else 0

    # Leader pressure matters the most.
    enemy_leader_delta = prev_enemy_leader_hp - next_enemy_leader_hp
    ai_leader_delta = prev_ai_leader_hp - next_ai_leader_hp

    # Board control and tempo.
    board_delta = (next_ai_units - prev_ai_units) - (next_enemy_units - prev_enemy_units)

    reward = 0.0
    reward += 0.08 * enemy_leader_delta
    reward -= 0.10 * ai_leader_delta
    reward += 0.02 * board_delta

    if action_effect_id == "DefaultAttack":
        reward += 0.01
    elif action_effect_id == "DeployUnit":
        reward += 0.005
    elif action_effect_id == "TurnEnd":
        reward -= 0.005

    return _clip(reward, -0.25, 0.25)


def terminal_reward_for_player(result: str, player_id: str) -> float:
    if result in {"Draw", "Ongoing"}:
        return 0.0
    if result == "Player1Win":
        return 1.0 if player_id == "P1" else -1.0
    if result == "Player2Win":
        return 1.0 if player_id == "P2" else -1.0
    return 0.0
