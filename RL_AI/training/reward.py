"""Terminal reward helpers for SeaEngine-backed training."""

from __future__ import annotations

from typing import Any, Dict

from RL_AI.SeaEngine.observation import BOARD_SIZE

DRAW_BASE_PENALTY = -0.08
DRAW_TURN_PENALTY = 0.0006
ONGOING_BASE_PENALTY = -0.12
ONGOING_TURN_PENALTY = 0.0012

# We do not want to punish long games themselves. We only want to punish
# long games that keep repeating without creating decisive advantage.
STAGNATION_TURN_START = 15
STAGNATION_TRANSITION_THRESHOLD = 0.030
STAGNATION_PENALTY = 0.010

OPENING_TURN_LIMIT = 8
UNSUPPORTED_LEADER_PENALTY = 0.020
BAD_PASS_PENALTY = 0.012
DEVELOPMENT_BONUS = 0.010
SUPPORT_BONUS = 0.008
LEADER_PUSH_PENALTY = 0.010


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


def _hand_count(snapshot: Dict[str, Any], owner_id: str) -> int:
    for player in snapshot.get("players", []):
        if str(player.get("id", "")) == owner_id:
            return len(list(player.get("hand", [])))
    return 0


def _own_cards(snapshot: Dict[str, Any], owner_id: str) -> list[Dict[str, Any]]:
    cards: list[Dict[str, Any]] = []
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) == owner_id:
            cards.append(card)
    for player in snapshot.get("players", []):
        if str(player.get("id", "")) != owner_id:
            continue
        for card in player.get("hand", []):
            if isinstance(card, dict):
                cards.append(card)
    return cards


def _leader_card(snapshot: Dict[str, Any], owner_id: str) -> Dict[str, Any] | None:
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) != owner_id:
            continue
        if str(card.get("role", "")) == "Leader":
            return card
    return None


def _card_role(card: Dict[str, Any]) -> str:
    role = str(card.get("role", "")).strip()
    if role:
        return role
    card_id = str(card.get("card_id", card.get("id", "")))
    suffix = card_id.split("_")[-1].strip()[-1:] if card_id else ""
    mapping = {"L": "Leader", "B": "Bishop", "N": "Knight", "R": "Rook", "P": "Pawn"}
    return mapping.get(suffix, "")


def _card_id(card: Dict[str, Any]) -> str:
    return str(card.get("card_id", card.get("id", card.get("name", ""))))


def _move_area_for_card(card: Dict[str, Any]) -> set[tuple[int, int]]:
    x = int(card.get("pos_x", -1))
    y = int(card.get("pos_y", -1))
    if x < 0 or y < 0:
        return set()
    role = _card_role(card)
    cells: set[tuple[int, int]] = set()
    if role == "Leader":
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                    cells.add((nx, ny))
    elif role == "Knight":
        for dx, dy in ((2, -1), (2, 1), (1, -2), (1, 2), (-1, -2), (-1, 2), (-2, -1), (-2, 1)):
            nx = x + dx
            ny = y + dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                cells.add((nx, ny))
    elif role in {"Bishop", "Queen"}:
        for dx, dy in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
            cx, cy = x, y
            while True:
                cx += dx
                cy += dy
                if not (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE):
                    break
                cells.add((cx, cy))
    return cells


def _leader_support_score(snapshot: Dict[str, Any], owner_id: str) -> int:
    leader = _leader_card(snapshot, owner_id)
    if leader is None:
        return 0
    area = _move_area_for_card(leader)
    support = 0
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) != owner_id:
            continue
        if not bool(card.get("is_placed", False)):
            continue
        if _card_role(card) in {"Knight", "Bishop"} and (int(card.get("pos_x", -1)), int(card.get("pos_y", -1))) in area:
            support += 1
    return support


def _leader_forward_progress(snapshot: Dict[str, Any], owner_id: str) -> float:
    leader = _leader_card(snapshot, owner_id)
    if leader is None:
        return 0.0
    x = int(leader.get("pos_x", -1))
    if x < 0:
        return 0.0
    if owner_id == "P1":
        return x / float(BOARD_SIZE - 1)
    return float((BOARD_SIZE - 1) - x) / float(BOARD_SIZE - 1)


def _pawn_last_rank_count(snapshot: Dict[str, Any], owner_id: str) -> int:
    count = 0
    last_rank = 5 if owner_id == "P1" else 0
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) != owner_id:
            continue
        if str(card.get("role", "")) != "Pawn":
            continue
        if bool(card.get("is_placed", False)) and int(card.get("pos_x", -1)) == last_rank:
            count += 1
    return count


def _pawn_progress(snapshot: Dict[str, Any], owner_id: str) -> float:
    """Return normalized forward progress for placed pawns."""
    pawns = 0
    progress_sum = 0.0
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) != owner_id:
            continue
        if str(card.get("role", "")) != "Pawn":
            continue
        if not bool(card.get("is_placed", False)):
            continue
        x = int(card.get("pos_x", -1))
        if x < 0:
            continue
        pawns += 1
        if owner_id == "P1":
            progress_sum += _safe_float(x, 0.0) / 5.0
        else:
            progress_sum += (5.0 - _safe_float(x, 0.0)) / 5.0
    return 0.0 if pawns == 0 else progress_sum / float(pawns)


def _development_score(snapshot: Dict[str, Any], owner_id: str) -> float:
    """Small opening-shape score: placed minor pieces plus leader cover."""
    score = 0.0
    for card in snapshot.get("board", []):
        if str(card.get("owner", "")) != owner_id:
            continue
        if not bool(card.get("is_placed", False)):
            continue
        role = _card_role(card)
        if role in {"Knight", "Bishop"}:
            score += 1.0
        elif role == "Pawn":
            score += 0.35
    score += 0.75 * float(_leader_support_score(snapshot, owner_id))
    return score


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


def _advantage_score(snapshot: Dict[str, Any], ai_id: str) -> float:
    enemy_id = _find_enemy_id(snapshot, ai_id)
    ai_hp = _leader_hp(snapshot, ai_id)
    enemy_hp = _leader_hp(snapshot, enemy_id) if enemy_id else 0.0
    ai_units = float(_placed_units(snapshot, ai_id))
    enemy_units = float(_placed_units(snapshot, enemy_id)) if enemy_id else 0.0
    ai_hand = float(_hand_count(snapshot, ai_id))
    enemy_hand = float(_hand_count(snapshot, enemy_id)) if enemy_id else 0.0
    return (
        0.12 * (ai_hp - enemy_hp)
        + 0.06 * (ai_units - enemy_units)
        + 0.03 * (ai_hand - enemy_hand)
    )


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

    prev_advantage = _advantage_score(prev_snapshot, ai_id)
    next_advantage = _advantage_score(next_snapshot, ai_id)
    if prev_advantage < 0.0:
        improvement = next_advantage - prev_advantage
        reward += _clip(0.04 * improvement, -0.04, 0.05)
        if next_advantage > prev_advantage:
            reward += 0.01
        if prev_advantage < -1.0 and next_advantage >= 0.0:
            reward += 0.04
    elif next_advantage < prev_advantage:
        reward -= _clip(0.01 * (prev_advantage - next_advantage), 0.0, 0.02)

    prev_support = _leader_support_score(prev_snapshot, ai_id)
    next_support = _leader_support_score(next_snapshot, ai_id)
    support_delta = next_support - prev_support
    reward += _clip(SUPPORT_BONUS * float(support_delta), -0.02, 0.02)

    prev_progress = _leader_forward_progress(prev_snapshot, ai_id)
    next_progress = _leader_forward_progress(next_snapshot, ai_id)
    if int(next_snapshot.get("turn", 0)) <= OPENING_TURN_LIMIT:
        prev_development = _development_score(prev_snapshot, ai_id)
        next_development = _development_score(next_snapshot, ai_id)
        reward += _clip(
            DEVELOPMENT_BONUS * float(next_development - prev_development),
            -0.015,
            0.025,
        )

        if next_support == 0 and next_progress > max(0.45, prev_progress + 0.08):
            reward -= UNSUPPORTED_LEADER_PENALTY

        if action_effect_id == "TurnEnd":
            has_non_end = any(str(action.get("effect_id", "")) != "TurnEnd" for action in prev_snapshot.get("actions", []))
            if has_non_end:
                reward -= BAD_PASS_PENALTY

        if next_progress > prev_progress and next_support == 0:
            reward -= LEADER_PUSH_PENALTY

    prev_pawn_last_rank = _pawn_last_rank_count(prev_snapshot, ai_id)
    next_pawn_last_rank = _pawn_last_rank_count(next_snapshot, ai_id)
    if next_pawn_last_rank > prev_pawn_last_rank:
        reward += _clip(0.01 * float(next_pawn_last_rank - prev_pawn_last_rank), 0.0, 0.03)

    progress_signal = (
        abs(0.08 * enemy_leader_delta)
        + abs(0.10 * ai_leader_delta)
        + abs(0.02 * board_delta)
    )
    if int(next_snapshot.get("turn", 0)) > STAGNATION_TURN_START and progress_signal < STAGNATION_TRANSITION_THRESHOLD:
        reward -= STAGNATION_PENALTY

    return _clip(reward, -0.25, 0.25)


def terminal_reward_for_player(result: str, player_id: str, *, final_turn: int | None = None) -> float:
    if result == "Draw":
        penalty = DRAW_BASE_PENALTY
        if final_turn is not None and final_turn > 0:
            penalty -= DRAW_TURN_PENALTY * float(final_turn)
        return penalty
    if result == "Ongoing":
        penalty = ONGOING_BASE_PENALTY
        if final_turn is not None and final_turn > 0:
            penalty -= ONGOING_TURN_PENALTY * float(final_turn)
        return penalty
    if result == "Player1Win":
        return 1.0 if player_id == "P1" else -1.0
    if result == "Player2Win":
        return 1.0 if player_id == "P2" else -1.0
    return 0.0
