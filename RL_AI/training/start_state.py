from __future__ import annotations

"""Helpers for curriculum warm-start states and deficit classification."""

from typing import Any, Dict, Optional, Tuple

from RL_AI.SeaEngine.action_adapter import choose_action_with_agent

_DEFICIT_ORDER = {"normal": 0, "slight": 1, "heavy": 2}


def _player_map(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(player.get("id", "")): player for player in snapshot.get("players", [])}


def _find_leader(snapshot: Dict[str, Any], player_id: str) -> Optional[Dict[str, Any]]:
    for card in snapshot.get("board", []):
        if not card.get("is_placed"):
            continue
        if str(card.get("owner", "")) != player_id:
            continue
        if str(card.get("role", "")) == "Leader":
            return card
    return None


def compute_deficit_metrics(snapshot: Dict[str, Any], player_id: str) -> Dict[str, int]:
    players = _player_map(snapshot)
    own_player = players.get(player_id, {})
    enemy_player = next((player for pid, player in players.items() if pid != player_id), {})
    own_leader = _find_leader(snapshot, player_id)
    enemy_id = next((pid for pid in players.keys() if pid != player_id), "")
    enemy_leader = _find_leader(snapshot, enemy_id) if enemy_id else None

    own_hp = int(own_leader.get("hp", 0)) if own_leader else 0
    enemy_hp = int(enemy_leader.get("hp", 0)) if enemy_leader else 0
    own_board = sum(1 for card in snapshot.get("board", []) if card.get("is_placed") and str(card.get("owner", "")) == player_id)
    enemy_board = sum(1 for card in snapshot.get("board", []) if card.get("is_placed") and str(card.get("owner", "")) != player_id)
    own_hand = len(list(own_player.get("hand", [])))
    enemy_hand = len(list(enemy_player.get("hand", [])))

    return {
        "hp_diff": own_hp - enemy_hp,
        "board_diff": own_board - enemy_board,
        "hand_diff": own_hand - enemy_hand,
        "own_hp": own_hp,
        "enemy_hp": enemy_hp,
        "own_board": own_board,
        "enemy_board": enemy_board,
        "own_hand": own_hand,
        "enemy_hand": enemy_hand,
    }


def classify_deficit_mode(snapshot: Dict[str, Any], player_id: str) -> str:
    metrics = compute_deficit_metrics(snapshot, player_id)
    hp_diff = int(metrics["hp_diff"])
    board_diff = int(metrics["board_diff"])
    hand_diff = int(metrics["hand_diff"])

    if hp_diff >= -1 and board_diff >= -1 and hand_diff >= -1:
        return "normal"
    if hp_diff <= -5 or board_diff <= -3 or (hp_diff <= -3 and board_diff <= -2):
        return "heavy"
    if hp_diff <= -2 or board_diff <= -1 or hand_diff <= -1:
        return "slight"
    return "slight"


def _mode_rank(mode: str) -> int:
    return _DEFICIT_ORDER.get(str(mode).strip().lower(), 0)


def meets_deficit_target(actual_mode: str, target_mode: str) -> bool:
    return _mode_rank(actual_mode) >= _mode_rank(target_mode)


def burn_in_to_deficit_mode(
    session,
    *,
    focus_player_id: str,
    target_mode: str,
    focus_agent,
    enemy_agent,
    max_actions: int = 48,
    max_turn_ends: int = 4,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    target_mode_normalized = str(target_mode or "normal").strip().lower()
    if target_mode_normalized not in _DEFICIT_ORDER:
        target_mode_normalized = "normal"

    snapshot = session.snapshot()
    if target_mode_normalized == "normal":
        return snapshot, {
            "requested_mode": target_mode_normalized,
            "actual_mode": classify_deficit_mode(snapshot, focus_player_id),
            "burnin_actions": 0,
            "burnin_turn_ends": 0,
        }

    burnin_actions = 0
    burnin_turn_ends = 0
    while snapshot.get("result") == "Ongoing" and burnin_actions < max_actions and burnin_turn_ends < max_turn_ends:
        actual_mode = classify_deficit_mode(snapshot, focus_player_id)
        if meets_deficit_target(actual_mode, target_mode_normalized) and burnin_actions > 0:
            break

        active_player = str(snapshot.get("active_player", ""))
        acting_agent = focus_agent if active_player == focus_player_id else enemy_agent
        _, action = choose_action_with_agent(acting_agent, snapshot)
        snapshot = session.apply_action(str(action.get("uid", "")))
        burnin_actions += 1
        if str(action.get("effect_id", "")) == "TurnEnd":
            burnin_turn_ends += 1

    return snapshot, {
        "requested_mode": target_mode_normalized,
        "actual_mode": classify_deficit_mode(snapshot, focus_player_id),
        "burnin_actions": burnin_actions,
        "burnin_turn_ends": burnin_turn_ends,
    }
