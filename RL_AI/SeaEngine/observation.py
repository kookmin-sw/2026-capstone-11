"""Observation and action feature builders for the C# SeaEngine snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

BOARD_SIZE = 6
MAX_BOARD_CARDS = 14
MAX_HAND_CARDS = 7
GLOBAL_FEATURE_DIM = 43
BOARD_TOKEN_DIM = 31
HAND_TOKEN_DIM = 10

ROLE_ORDER = ["Leader", "Bishop", "Knight", "Rook", "Pawn"]
ROLE_BY_SUFFIX = {
    "L": "Leader",
    "B": "Bishop",
    "N": "Knight",
    "R": "Rook",
    "P": "Pawn",
}
EFFECT_BUCKETS = ["DeployUnit", "DefaultMove", "DefaultAttack", "TurnEnd", "Skill"]
TARGET_BUCKETS = ["None", "Cell", "Unit", "Unit2", "Card"]
RESULT_BUCKETS = ["Ongoing", "Player1Win", "Player2Win", "Draw"]


@dataclass
class SeaEngineObservation:
    unit_list: List[Dict[str, Any]]
    hand_list: List[Dict[str, Any]]
    global_vector: List[float]
    legal_action_mask: List[int]
    state_vector: List[float]
    action_feature_vectors: List[List[float]]


@dataclass
class _SnapshotContext:
    snapshot: Dict[str, Any]
    player_id: str
    enemy_id: str
    mirror_view: bool
    own_player: Dict[str, Any]
    enemy_player: Dict[str, Any]
    board: List[Dict[str, Any]]
    own_board: List[Dict[str, Any]]
    enemy_board: List[Dict[str, Any]]
    own_hand: List[Dict[str, Any]]
    own_leader: Optional[Dict[str, Any]]
    enemy_leader: Optional[Dict[str, Any]]
    board_by_uid: Dict[str, Dict[str, Any]]
    action_map: Dict[str, List[Dict[str, Any]]]
    actions: List[Dict[str, Any]]


def _normalize_ratio(value: float, scale: float) -> float:
    return 0.0 if scale == 0 else value / scale


def _normalize_pos(value: int) -> float:
    if value < 0:
        return -1.0
    return value / float(BOARD_SIZE - 1)


def _view_x(value: int, mirror_view: bool) -> int:
    if value < 0:
        return value
    return (BOARD_SIZE - 1 - value) if mirror_view else value


def _view_y(value: int) -> int:
    return value


def _should_mirror_view(own_leader: Optional[Dict[str, Any]], enemy_leader: Optional[Dict[str, Any]]) -> bool:
    if own_leader is None or enemy_leader is None:
        return False
    own_x = int(own_leader.get("pos_x", -1))
    enemy_x = int(enemy_leader.get("pos_x", -1))
    if own_x < 0 or enemy_x < 0:
        return False
    return own_x > enemy_x


def _distance(x1: int, y1: int, x2: int, y2: int) -> float:
    if min(x1, y1, x2, y2) < 0:
        return -1.0
    return (abs(x1 - x2) + abs(y1 - y2)) / float((BOARD_SIZE - 1) * 2)


def _role_one_hot(role: str) -> List[float]:
    return [1.0 if role == name else 0.0 for name in ROLE_ORDER]


def _effect_one_hot(effect_id: str) -> List[float]:
    bucket = effect_id if effect_id in EFFECT_BUCKETS[:-1] else "Skill"
    return [1.0 if bucket == name else 0.0 for name in EFFECT_BUCKETS]


def _target_one_hot(target_type: str) -> List[float]:
    return [1.0 if target_type == name else 0.0 for name in TARGET_BUCKETS]


def _result_one_hot(result: str) -> List[float]:
    return [1.0 if result == name else 0.0 for name in RESULT_BUCKETS]


def _role_from_card(card: Dict[str, Any]) -> str:
    role = str(card.get("role", ""))
    if role:
        return role
    return _role_from_card_id(str(card.get("card_id", "")))


def _role_from_card_id(card_id: str) -> str:
    suffix = card_id.split("_")[-1].strip()[-1:] if card_id else ""
    return ROLE_BY_SUFFIX.get(suffix, "")


def _status_summary(card: Dict[str, Any]) -> tuple[float, float, float, float]:
    attack_mod = 0.0
    has_move_lock = 0.0
    has_attack_lock = 0.0
    timed_status_count = 0.0
    for status in card.get("statuses", []):
        timed_status_count += 1.0
        status_type = status.get("type", "")
        if status_type == "AttackModifier":
            attack_mod += float(status.get("value", 0.0))
        elif status_type == "MoveLock":
            has_move_lock = 1.0
        elif status_type == "AttackLock":
            has_attack_lock = 1.0
    return attack_mod, has_move_lock, has_attack_lock, timed_status_count


def _find_card(snapshot: Dict[str, Any], uid: str) -> Optional[Dict[str, Any]]:
    for card in snapshot.get("board", []):
        if card.get("uid") == uid:
            return card
    return None


def _actions_by_source(snapshot: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    mapping: Dict[str, List[Dict[str, Any]]] = {}
    for action in snapshot.get("actions", []):
        source_uid = str(action.get("source", ""))
        mapping.setdefault(source_uid, []).append(action)
    return mapping


def _build_context(snapshot: Dict[str, Any], player_id: str) -> _SnapshotContext:
    own_player, enemy_player, enemy_id = _get_players(snapshot, player_id)
    board = list(snapshot.get("board", []))
    actions = list(snapshot.get("actions", []))
    own_board = [card for card in board if card.get("owner") == player_id and card.get("is_placed")]
    enemy_board = [card for card in board if card.get("owner") == enemy_id and card.get("is_placed")]
    own_hand = list(own_player.get("hand", []))

    own_leader = None
    enemy_leader = None
    for card in board:
        if not card.get("is_placed"):
            continue
        if _role_from_card(card) != "Leader":
            continue
        if card.get("owner") == player_id:
            own_leader = card
        elif card.get("owner") == enemy_id:
            enemy_leader = card

    mirror_view = _should_mirror_view(own_leader, enemy_leader)

    board_by_uid = {str(card.get("uid", "")): card for card in board}
    action_map: Dict[str, List[Dict[str, Any]]] = {}
    for action in actions:
        source_uid = str(action.get("source", ""))
        action_map.setdefault(source_uid, []).append(action)

    return _SnapshotContext(
        snapshot=snapshot,
        player_id=player_id,
        enemy_id=enemy_id,
        mirror_view=mirror_view,
        own_player=own_player,
        enemy_player=enemy_player,
        board=board,
        own_board=own_board,
        enemy_board=enemy_board,
        own_hand=own_hand,
        own_leader=own_leader,
        enemy_leader=enemy_leader,
        board_by_uid=board_by_uid,
        action_map=action_map,
        actions=actions,
    )


def _get_players(snapshot: Dict[str, Any], player_id: str) -> tuple[Dict[str, Any], Dict[str, Any], str]:
    players = {str(player.get("id", "")): player for player in snapshot.get("players", [])}
    own_player = players.get(player_id, {})
    enemy_id = next((pid for pid in players.keys() if pid != player_id), "")
    enemy_player = players.get(enemy_id, {})
    return own_player, enemy_player, enemy_id


def _get_leaders(snapshot: Dict[str, Any], player_id: str, enemy_id: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    own = None
    enemy = None
    for card in snapshot.get("board", []):
        if not card.get("is_placed"):
            continue
        if _role_from_card(card) != "Leader":
            continue
        if card.get("owner") == player_id:
            own = card
        elif card.get("owner") == enemy_id:
            enemy = card
    return own, enemy


def _sorted_board_cards(snapshot: Dict[str, Any], player_id: str, mirror_view: bool) -> List[Dict[str, Any]]:
    role_rank = {name: idx for idx, name in enumerate(ROLE_ORDER)}
    return sorted(
        snapshot.get("board", []),
        key=lambda card: (
            0 if card.get("owner") == player_id else 1,
            role_rank.get(_role_from_card(card), 99),
            _view_x(int(card.get("pos_x", -1)), mirror_view),
            _view_y(int(card.get("pos_y", -1))),
            card.get("uid", ""),
        ),
    )


def _count_ready_attack_targets(snapshot: Dict[str, Any], card: Dict[str, Any]) -> float:
    if not card.get("is_placed"):
        return 0.0
    source_owner = card.get("owner")
    sx = int(card.get("pos_x", -1))
    sy = int(card.get("pos_y", -1))
    if sx < 0 or sy < 0:
        return 0.0

    reachable = 0.0
    for other in snapshot.get("board", []):
        if not other.get("is_placed") or other.get("owner") == source_owner:
            continue
        ox = int(other.get("pos_x", -1))
        oy = int(other.get("pos_y", -1))
        if ox < 0 or oy < 0:
            continue
        if abs(sx - ox) <= 1 and abs(sy - oy) <= 1:
            reachable += 1.0
    return reachable


def _count_enemy_neighbors(snapshot: Dict[str, Any], card: Dict[str, Any]) -> float:
    if not card.get("is_placed"):
        return 0.0
    source_owner = card.get("owner")
    sx = int(card.get("pos_x", -1))
    sy = int(card.get("pos_y", -1))
    if sx < 0 or sy < 0:
        return 0.0

    neighbors = 0.0
    for other in snapshot.get("board", []):
        if not other.get("is_placed") or other.get("owner") == source_owner:
            continue
        ox = int(other.get("pos_x", -1))
        oy = int(other.get("pos_y", -1))
        if ox < 0 or oy < 0:
            continue
        if abs(sx - ox) <= 1 and abs(sy - oy) <= 1:
            neighbors += 1.0
    return neighbors


def _count_attackers_of_card(snapshot: Dict[str, Any], target_card: Dict[str, Any]) -> float:
    if not target_card.get("is_placed"):
        return 0.0
    tx = int(target_card.get("pos_x", -1))
    ty = int(target_card.get("pos_y", -1))
    target_owner = target_card.get("owner")
    if tx < 0 or ty < 0:
        return 0.0

    attackers = 0.0
    for other in snapshot.get("board", []):
        if not other.get("is_placed") or other.get("owner") == target_owner:
            continue
        ox = int(other.get("pos_x", -1))
        oy = int(other.get("pos_y", -1))
        if ox < 0 or oy < 0:
            continue
        if abs(ox - tx) <= 1 and abs(oy - ty) <= 1:
            attackers += 1.0
    return attackers


def _count_deployable_cards(snapshot: Dict[str, Any], player_id: str) -> float:
    own_player, _, _ = _get_players(snapshot, player_id)
    deployable = 0.0
    for card in own_player.get("hand", []):
        uid = str(card.get("uid", ""))
        if any(str(action.get("effect_id", "")) == "DeployUnit" and str(action.get("source", "")) == uid for action in snapshot.get("actions", [])):
            deployable += 1.0
    return deployable


def _count_skill_actions(snapshot: Dict[str, Any], player_id: str) -> float:
    own_player, _, _ = _get_players(snapshot, player_id)
    hand_uids = {str(card.get("uid", "")) for card in own_player.get("hand", [])}
    count = 0.0
    for action in snapshot.get("actions", []):
        effect_id = str(action.get("effect_id", ""))
        source_uid = str(action.get("source", ""))
        if effect_id not in {"DeployUnit", "DefaultMove", "DefaultAttack", "TurnEnd"} and source_uid in hand_uids:
            count += 1.0
    return count


def _count_actions(snapshot: Dict[str, Any], player_id: str, effect_id: str) -> float:
    count = 0.0
    for action in snapshot.get("actions", []):
        source_uid = str(action.get("source", ""))
        source_card = _find_card(snapshot, source_uid)
        if source_card is not None and source_card.get("owner") != player_id:
            continue
        if str(action.get("effect_id", "")) == effect_id:
            count += 1.0
    return count


def _build_global_vector(snapshot: Dict[str, Any], player_id: str) -> List[float]:
    own_player, enemy_player, enemy_id = _get_players(snapshot, player_id)
    own_leader, enemy_leader = _get_leaders(snapshot, player_id, enemy_id)

    own_board = [card for card in snapshot.get("board", []) if card.get("owner") == player_id and card.get("is_placed")]
    enemy_board = [card for card in snapshot.get("board", []) if card.get("owner") == enemy_id and card.get("is_placed")]

    own_attack_total = sum(float(card.get("effective_atk", 0.0)) for card in own_board)
    enemy_attack_total = sum(float(card.get("effective_atk", 0.0)) for card in enemy_board)
    own_hp_total = sum(float(card.get("hp", 0.0)) for card in own_board)
    enemy_hp_total = sum(float(card.get("hp", 0.0)) for card in enemy_board)
    own_ready_move = sum(1.0 for card in own_board if not card.get("is_moved"))
    own_ready_attack = sum(1.0 for card in own_board if not card.get("is_attacked"))
    enemy_ready_attack = sum(1.0 for card in enemy_board if not card.get("is_attacked"))
    own_deployable = _count_deployable_cards(snapshot, player_id)
    own_skill_actions = _count_skill_actions(snapshot, player_id)
    own_attack_actions = _count_actions(snapshot, player_id, "DefaultAttack")
    own_move_actions = _count_actions(snapshot, player_id, "DefaultMove")
    enemy_attackers_on_leader = 0.0 if own_leader is None else _count_attackers_of_card(snapshot, own_leader)
    own_attackers_on_enemy_leader = 0.0 if enemy_leader is None else _count_attackers_of_card(snapshot, enemy_leader)
    center_control_own = sum(
        1.0
        for card in own_board
        if 2 <= int(card.get("pos_x", -1)) <= 3 and 2 <= int(card.get("pos_y", -1)) <= 3
    )
    center_control_enemy = sum(
        1.0
        for card in enemy_board
        if 2 <= int(card.get("pos_x", -1)) <= 3 and 2 <= int(card.get("pos_y", -1)) <= 3
    )

    action_counts = {bucket: 0.0 for bucket in EFFECT_BUCKETS}
    actions = snapshot.get("actions", [])
    for action in actions:
        effect_id = str(action.get("effect_id", ""))
        bucket = effect_id if effect_id in EFFECT_BUCKETS[:-1] else "Skill"
        action_counts[bucket] += 1.0
    action_total = max(1.0, float(len(actions)))

    return [
        _normalize_ratio(float(snapshot.get("turn", 1)), 100.0),
        1.0 if snapshot.get("active_player") == player_id else 0.0,
        *_result_one_hot(str(snapshot.get("result", "Ongoing"))),
        _normalize_ratio(float(own_player.get("hand_count", 0)), MAX_HAND_CARDS),
        _normalize_ratio(float(enemy_player.get("hand_count", 0)), MAX_HAND_CARDS),
        _normalize_ratio(float(own_player.get("deck_count", 0)), MAX_BOARD_CARDS),
        _normalize_ratio(float(enemy_player.get("deck_count", 0)), MAX_BOARD_CARDS),
        _normalize_ratio(float(own_player.get("trash_count", 0)), MAX_BOARD_CARDS),
        _normalize_ratio(float(enemy_player.get("trash_count", 0)), MAX_BOARD_CARDS),
        0.0 if own_leader is None else _normalize_ratio(float(own_leader.get("hp", 0)), max(1.0, float(own_leader.get("max_hp", 1)))),
        0.0 if enemy_leader is None else _normalize_ratio(float(enemy_leader.get("hp", 0)), max(1.0, float(enemy_leader.get("max_hp", 1)))),
        0.0 if own_leader is None or enemy_leader is None else _normalize_ratio(
            float(own_leader.get("hp", 0)) - float(enemy_leader.get("hp", 0)),
            max(1.0, float(own_leader.get("max_hp", 1))),
        ),
        _normalize_ratio(float(len(own_board)), MAX_BOARD_CARDS),
        _normalize_ratio(float(len(enemy_board)), MAX_BOARD_CARDS),
        _normalize_ratio(float(len(own_board) - len(enemy_board)), MAX_BOARD_CARDS),
        _normalize_ratio(own_attack_total, 40.0),
        _normalize_ratio(enemy_attack_total, 40.0),
        _normalize_ratio(own_attack_total - enemy_attack_total, 40.0),
        _normalize_ratio(own_hp_total, 40.0),
        _normalize_ratio(enemy_hp_total, 40.0),
        _normalize_ratio(own_ready_move, MAX_BOARD_CARDS),
        _normalize_ratio(own_ready_attack, MAX_BOARD_CARDS),
        _normalize_ratio(enemy_ready_attack, MAX_BOARD_CARDS),
        _normalize_ratio(own_deployable, MAX_HAND_CARDS),
        _normalize_ratio(own_skill_actions, MAX_HAND_CARDS),
        _normalize_ratio(own_attack_actions, 20.0),
        _normalize_ratio(own_move_actions, 20.0),
        _normalize_ratio(enemy_attackers_on_leader, 6.0),
        _normalize_ratio(own_attackers_on_enemy_leader, 6.0),
        _normalize_ratio(center_control_own, 4.0),
        _normalize_ratio(center_control_enemy, 4.0),
        *[_normalize_ratio(action_counts[bucket], action_total) for bucket in EFFECT_BUCKETS],
    ]


def _count_deployable_cards_ctx(ctx: _SnapshotContext) -> float:
    deployable = 0.0
    for card in ctx.own_hand:
        uid = str(card.get("uid", ""))
        if any(str(action.get("effect_id", "")) == "DeployUnit" and str(action.get("source", "")) == uid for action in ctx.actions):
            deployable += 1.0
    return deployable


def _count_skill_actions_ctx(ctx: _SnapshotContext) -> float:
    hand_uids = {str(card.get("uid", "")) for card in ctx.own_hand}
    count = 0.0
    for action in ctx.actions:
        effect_id = str(action.get("effect_id", ""))
        source_uid = str(action.get("source", ""))
        if effect_id not in {"DeployUnit", "DefaultMove", "DefaultAttack", "TurnEnd"} and source_uid in hand_uids:
            count += 1.0
    return count


def _count_actions_ctx(ctx: _SnapshotContext, effect_id: str) -> float:
    count = 0.0
    for action in ctx.actions:
        source_uid = str(action.get("source", ""))
        source_card = ctx.board_by_uid.get(source_uid)
        if source_card is not None and source_card.get("owner") != ctx.player_id:
            continue
        if str(action.get("effect_id", "")) == effect_id:
            count += 1.0
    return count


def _count_attackers_of_card_ctx(ctx: _SnapshotContext, target_card: Optional[Dict[str, Any]]) -> float:
    if not target_card or not target_card.get("is_placed"):
        return 0.0
    tx = int(target_card.get("pos_x", -1))
    ty = int(target_card.get("pos_y", -1))
    target_owner = target_card.get("owner")
    if tx < 0 or ty < 0:
        return 0.0
    attackers = 0.0
    for other in ctx.board:
        if not other.get("is_placed") or other.get("owner") == target_owner:
            continue
        ox = int(other.get("pos_x", -1))
        oy = int(other.get("pos_y", -1))
        if ox < 0 or oy < 0:
            continue
        if abs(ox - tx) <= 1 and abs(oy - ty) <= 1:
            attackers += 1.0
    return attackers


def _pawn_progress_ctx(ctx: _SnapshotContext, owner_id: str) -> float:
    pawns = 0
    progress_sum = 0.0
    for card in ctx.board:
        if card.get("owner") != owner_id:
            continue
        if _role_from_card(card) != "Pawn" or not card.get("is_placed"):
            continue
        cx = _view_x(int(card.get("pos_x", -1)), ctx.mirror_view)
        if cx < 0:
            continue
        pawns += 1
        if owner_id == ctx.player_id:
            progress_sum += _normalize_ratio(float(cx), BOARD_SIZE - 1)
        else:
            progress_sum += _normalize_ratio(float((BOARD_SIZE - 1) - cx), BOARD_SIZE - 1)
    return 0.0 if pawns == 0 else progress_sum / float(pawns)


def _pawn_last_rank_count_ctx(ctx: _SnapshotContext, owner_id: str) -> int:
    count = 0
    last_rank = BOARD_SIZE - 1 if owner_id == ctx.player_id else 0
    for card in ctx.board:
        if card.get("owner") != owner_id:
            continue
        if _role_from_card(card) != "Pawn" or not card.get("is_placed"):
            continue
        cx = _view_x(int(card.get("pos_x", -1)), ctx.mirror_view)
        if cx == last_rank:
            count += 1
    return count


def _pawn_promotion_ready(card: Dict[str, Any], *, mirror_view: bool, owner_is_self: bool) -> float:
    if _role_from_card(card) != "Pawn" or not card.get("is_placed"):
        return 0.0
    cx = _view_x(int(card.get("pos_x", -1)), mirror_view)
    if cx < 0:
        return 0.0
    ready_rank = BOARD_SIZE - 1 if owner_is_self else 0
    return 1.0 if cx == ready_rank else 0.0


def _pawn_promotion_distance(card: Dict[str, Any], *, mirror_view: bool, owner_is_self: bool) -> float:
    if _role_from_card(card) != "Pawn" or not card.get("is_placed"):
        return 0.0
    cx = _view_x(int(card.get("pos_x", -1)), mirror_view)
    if cx < 0:
        return 0.0
    if owner_is_self:
        remaining = (BOARD_SIZE - 1) - cx
    else:
        remaining = cx
    return _normalize_ratio(float(max(0, remaining)), BOARD_SIZE - 1)


def _count_ready_attack_targets_ctx(ctx: _SnapshotContext, card: Dict[str, Any]) -> float:
    if not card.get("is_placed"):
        return 0.0
    source_owner = card.get("owner")
    sx = int(card.get("pos_x", -1))
    sy = int(card.get("pos_y", -1))
    if sx < 0 or sy < 0:
        return 0.0
    reachable = 0.0
    for other in ctx.board:
        if not other.get("is_placed") or other.get("owner") == source_owner:
            continue
        ox = int(other.get("pos_x", -1))
        oy = int(other.get("pos_y", -1))
        if ox < 0 or oy < 0:
            continue
        if abs(sx - ox) <= 1 and abs(sy - oy) <= 1:
            reachable += 1.0
    return reachable


def _count_enemy_neighbors_ctx(ctx: _SnapshotContext, card: Dict[str, Any]) -> float:
    return _count_ready_attack_targets_ctx(ctx, card)


def _status_summary_ctx(card: Dict[str, Any]) -> tuple[float, float, float, float]:
    return _status_summary(card)


def _build_global_vector_ctx(ctx: _SnapshotContext) -> List[float]:
    own_player = ctx.own_player
    enemy_player = ctx.enemy_player
    own_leader = ctx.own_leader
    enemy_leader = ctx.enemy_leader
    player_id = ctx.player_id
    own_board = ctx.own_board
    enemy_board = ctx.enemy_board

    own_attack_total = sum(float(card.get("effective_atk", 0.0)) for card in own_board)
    enemy_attack_total = sum(float(card.get("effective_atk", 0.0)) for card in enemy_board)
    own_hp_total = sum(float(card.get("hp", 0.0)) for card in own_board)
    enemy_hp_total = sum(float(card.get("hp", 0.0)) for card in enemy_board)
    own_ready_move = sum(1.0 for card in own_board if not card.get("is_moved"))
    own_ready_attack = sum(1.0 for card in own_board if not card.get("is_attacked"))
    enemy_ready_attack = sum(1.0 for card in enemy_board if not card.get("is_attacked"))
    own_deployable = _count_deployable_cards_ctx(ctx)
    own_skill_actions = _count_skill_actions_ctx(ctx)
    own_attack_actions = _count_actions_ctx(ctx, "DefaultAttack")
    own_move_actions = _count_actions_ctx(ctx, "DefaultMove")
    enemy_attackers_on_leader = 0.0 if own_leader is None else _count_attackers_of_card_ctx(ctx, own_leader)
    own_attackers_on_enemy_leader = 0.0 if enemy_leader is None else _count_attackers_of_card_ctx(ctx, enemy_leader)
    center_control_own = sum(
        1.0
        for card in own_board
        if 2 <= int(card.get("pos_x", -1)) <= 3 and 2 <= int(card.get("pos_y", -1)) <= 3
    )
    center_control_enemy = sum(
        1.0
        for card in enemy_board
        if 2 <= int(card.get("pos_x", -1)) <= 3 and 2 <= int(card.get("pos_y", -1)) <= 3
    )
    own_pawn_progress = _pawn_progress_ctx(ctx, ctx.player_id)
    enemy_pawn_progress = _pawn_progress_ctx(ctx, ctx.enemy_id)
    own_pawn_last_rank = float(_pawn_last_rank_count_ctx(ctx, ctx.player_id))
    enemy_pawn_last_rank = float(_pawn_last_rank_count_ctx(ctx, ctx.enemy_id))

    action_counts = {bucket: 0.0 for bucket in EFFECT_BUCKETS}
    for action in ctx.actions:
        effect_id = str(action.get("effect_id", ""))
        bucket = effect_id if effect_id in EFFECT_BUCKETS[:-1] else "Skill"
        action_counts[bucket] += 1.0
    action_total = max(1.0, float(len(ctx.actions)))

    return [
        _normalize_ratio(float(ctx.snapshot.get("turn", 1)), 100.0),
        1.0 if ctx.snapshot.get("active_player") == player_id else 0.0,
        *_result_one_hot(str(ctx.snapshot.get("result", "Ongoing"))),
        _normalize_ratio(float(own_player.get("hand_count", 0)), MAX_HAND_CARDS),
        _normalize_ratio(float(enemy_player.get("hand_count", 0)), MAX_HAND_CARDS),
        _normalize_ratio(float(own_player.get("deck_count", 0)), MAX_BOARD_CARDS),
        _normalize_ratio(float(enemy_player.get("deck_count", 0)), MAX_BOARD_CARDS),
        _normalize_ratio(float(own_player.get("trash_count", 0)), MAX_BOARD_CARDS),
        _normalize_ratio(float(enemy_player.get("trash_count", 0)), MAX_BOARD_CARDS),
        0.0 if own_leader is None else _normalize_ratio(float(own_leader.get("hp", 0)), max(1.0, float(own_leader.get("max_hp", 1)))),
        0.0 if enemy_leader is None else _normalize_ratio(float(enemy_leader.get("hp", 0)), max(1.0, float(enemy_leader.get("max_hp", 1)))),
        0.0 if own_leader is None or enemy_leader is None else _normalize_ratio(
            float(own_leader.get("hp", 0)) - float(enemy_leader.get("hp", 0)),
            max(1.0, float(own_leader.get("max_hp", 1))),
        ),
        _normalize_ratio(float(len(own_board)), MAX_BOARD_CARDS),
        _normalize_ratio(float(len(enemy_board)), MAX_BOARD_CARDS),
        _normalize_ratio(float(len(own_board) - len(enemy_board)), MAX_BOARD_CARDS),
        _normalize_ratio(own_attack_total, 40.0),
        _normalize_ratio(enemy_attack_total, 40.0),
        _normalize_ratio(own_attack_total - enemy_attack_total, 40.0),
        _normalize_ratio(own_hp_total, 40.0),
        _normalize_ratio(enemy_hp_total, 40.0),
        _normalize_ratio(own_ready_move, MAX_BOARD_CARDS),
        _normalize_ratio(own_ready_attack, MAX_BOARD_CARDS),
        _normalize_ratio(enemy_ready_attack, MAX_BOARD_CARDS),
        _normalize_ratio(own_deployable, MAX_HAND_CARDS),
        _normalize_ratio(own_skill_actions, MAX_HAND_CARDS),
        _normalize_ratio(own_attack_actions, 20.0),
        _normalize_ratio(own_move_actions, 20.0),
        _normalize_ratio(enemy_attackers_on_leader, 6.0),
        _normalize_ratio(own_attackers_on_enemy_leader, 6.0),
        _normalize_ratio(center_control_own, 4.0),
        _normalize_ratio(center_control_enemy, 4.0),
        _normalize_ratio(own_pawn_progress, 1.0),
        _normalize_ratio(enemy_pawn_progress, 1.0),
        _normalize_ratio(own_pawn_last_rank, 7.0),
        _normalize_ratio(enemy_pawn_last_rank, 7.0),
        *[_normalize_ratio(action_counts[bucket], action_total) for bucket in EFFECT_BUCKETS],
    ]


def _build_board_vector_ctx(ctx: _SnapshotContext) -> List[float]:
    own_leader = ctx.own_leader
    enemy_leader = ctx.enemy_leader
    own_lx = _view_x(int(own_leader.get("pos_x", -1)), ctx.mirror_view) if own_leader else -1
    own_ly = _view_y(int(own_leader.get("pos_y", -1))) if own_leader else -1
    enemy_lx = _view_x(int(enemy_leader.get("pos_x", -1)), ctx.mirror_view) if enemy_leader else -1
    enemy_ly = _view_y(int(enemy_leader.get("pos_y", -1))) if enemy_leader else -1

    vectors: List[float] = []
    cards = _sorted_board_cards(ctx.snapshot, ctx.player_id, ctx.mirror_view)
    for card in cards[:MAX_BOARD_CARDS]:
        attack_mod, has_move_lock, has_attack_lock, timed_status_count = _status_summary_ctx(card)
        cx = _view_x(int(card.get("pos_x", -1)), ctx.mirror_view)
        cy = _view_y(int(card.get("pos_y", -1)))
        role = _role_from_card(card)
        hp = float(card.get("hp", 0.0))
        max_hp = max(1.0, float(card.get("max_hp", 1.0)))
        effective_atk = float(card.get("effective_atk", 0.0))
        base_atk = float(card.get("atk", 0.0))
        reachable_targets = _count_ready_attack_targets_ctx(ctx, card)
        adjacent_enemies = _count_enemy_neighbors_ctx(ctx, card)
        incoming_attackers = _count_attackers_of_card_ctx(ctx, card)
        card_actions = ctx.action_map.get(str(card.get("uid", "")), [])
        has_attack_action = 1.0 if any(str(action.get("effect_id", "")) in {"DefaultAttack", "PawnGeneric"} for action in card_actions) else 0.0
        has_move_action = 1.0 if any(str(action.get("effect_id", "")) == "DefaultMove" for action in card_actions) else 0.0
        threatens_enemy_leader = 1.0 if enemy_leader is not None and _distance(cx, cy, enemy_lx, enemy_ly) >= 0 and _distance(cx, cy, enemy_lx, enemy_ly) <= (1.0 / 5.0) else 0.0
        in_center = 1.0 if 2 <= cx <= 3 and 2 <= cy <= 3 else 0.0
        row_progress = 0.0
        if card.get("is_placed"):
            row_progress = _normalize_ratio(float(cx), BOARD_SIZE - 1)
        owner_is_self = card.get("owner") == ctx.player_id
        promotion_ready = _pawn_promotion_ready(card, mirror_view=ctx.mirror_view, owner_is_self=owner_is_self)
        promotion_distance = _pawn_promotion_distance(card, mirror_view=ctx.mirror_view, owner_is_self=owner_is_self)

        vectors.extend(
            [
                1.0 if card.get("owner") == ctx.player_id else -1.0,
                1.0 if card.get("is_placed") else 0.0,
                1.0 if card.get("is_moved") else 0.0,
                1.0 if card.get("is_attacked") else 0.0,
                _normalize_pos(cx),
                _normalize_pos(cy),
                _normalize_ratio(hp, max_hp),
                _normalize_ratio(max_hp, 10.0),
                _normalize_ratio(base_atk, 10.0),
                _normalize_ratio(effective_atk, 10.0),
                _normalize_ratio(attack_mod, 5.0),
                has_move_lock,
                has_attack_lock,
                _normalize_ratio(timed_status_count, 4.0),
                _distance(cx, cy, own_lx, own_ly),
                _distance(cx, cy, enemy_lx, enemy_ly),
                _normalize_ratio(reachable_targets, 6.0),
                _normalize_ratio(adjacent_enemies, 6.0),
                _normalize_ratio(incoming_attackers, 6.0),
                has_attack_action,
                has_move_action,
                threatens_enemy_leader,
                in_center,
                row_progress,
                promotion_ready,
                promotion_distance,
                *_role_one_hot(role),
            ]
        )

    missing_slots = MAX_BOARD_CARDS - min(len(cards), MAX_BOARD_CARDS)
    if missing_slots > 0:
        vectors.extend([0.0] * missing_slots * BOARD_TOKEN_DIM)
    return vectors


def _build_hand_vector_ctx(ctx: _SnapshotContext) -> List[float]:
    vectors: List[float] = []
    for card in ctx.own_hand[:MAX_HAND_CARDS]:
        role = _role_from_card(card)
        card_id = str(card.get("card_id", ""))
        deployable = 1.0 if any(
            str(action.get("effect_id", "")) == "DeployUnit" and str(action.get("source", "")) == str(card.get("uid", ""))
            for action in ctx.actions
        ) else 0.0
        skill_usable = 1.0 if any(
            str(action.get("effect_id", "")) not in {"DeployUnit", "DefaultMove", "DefaultAttack", "TurnEnd"}
            and str(action.get("source", "")) == str(card.get("uid", ""))
            for action in ctx.actions
        ) else 0.0
        vectors.extend(
            [
                1.0,
                1.0 if card_id.startswith("Or_") else 0.0,
                1.0 if card_id.startswith("Cl_") else 0.0,
                deployable,
                skill_usable,
                *_role_one_hot(role),
            ]
        )
    missing_slots = MAX_HAND_CARDS - min(len(ctx.own_hand), MAX_HAND_CARDS)
    if missing_slots > 0:
        vectors.extend([0.0] * missing_slots * 10)
    return vectors


def _encode_action_features_ctx(ctx: _SnapshotContext, action: Dict[str, Any]) -> List[float]:
    effect_id = str(action.get("effect_id", ""))
    target = action.get("target", {})
    target_type = str(target.get("type", "None"))

    source = ctx.board_by_uid.get(str(action.get("source", "")))
    target_card = ctx.board_by_uid.get(str(target.get("guid", ""))) if target_type in {"Unit", "Card"} else None
    target_card2 = ctx.board_by_uid.get(str(target.get("guid2", ""))) if target_type == "Unit2" else None

    target_x = _view_x(int(target.get("pos_x", -1)), ctx.mirror_view)
    target_y = _view_y(int(target.get("pos_y", -1)))
    source_x = _view_x(int(source.get("pos_x", -1)), ctx.mirror_view) if source else -1
    source_y = _view_y(int(source.get("pos_y", -1))) if source else -1
    enemy_lx = _view_x(int(ctx.enemy_leader.get("pos_x", -1)), ctx.mirror_view) if ctx.enemy_leader else -1
    enemy_ly = _view_y(int(ctx.enemy_leader.get("pos_y", -1))) if ctx.enemy_leader else -1

    attack_mod, has_move_lock, has_attack_lock, timed_status_count = _status_summary_ctx(source) if source else (0.0, 0.0, 0.0, 0.0)
    source_role = _role_from_card(source or {})
    target_role = _role_from_card(target_card or {})
    source_adjacent_enemies = _count_enemy_neighbors_ctx(ctx, source) if source else 0.0
    target_incoming_attackers = _count_attackers_of_card_ctx(ctx, target_card) if target_card else 0.0

    move_distance_before = _distance(source_x, source_y, enemy_lx, enemy_ly)
    move_distance_after = _distance(target_x, target_y, enemy_lx, enemy_ly) if target_type == "Cell" else move_distance_before
    moves_closer = 1.0 if move_distance_after >= 0 and move_distance_before >= 0 and move_distance_after < move_distance_before else 0.0
    enters_leader_zone = 1.0 if target_type == "Cell" and move_distance_after >= 0 and move_distance_after <= (1.0 / 5.0) else 0.0

    target_hp = float(target_card.get("hp", 0.0)) if target_card else 0.0
    target_max_hp = max(1.0, float(target_card.get("max_hp", 1.0))) if target_card else 1.0
    source_atk = float(source.get("effective_atk", 0.0)) if source else 0.0
    can_kill_target = 1.0 if target_card and source_atk >= target_hp > 0 else 0.0
    threatens_enemy_leader = 1.0 if target_card and target_card.get("owner") != ctx.player_id and target_role == "Leader" else 0.0
    affects_two_units = 1.0 if target_card2 is not None else 0.0
    source_survives_trade = 1.0 if target_card and source is not None and float(target_card.get("effective_atk", 0.0)) < float(source.get("hp", 0.0)) else 0.0
    target_is_low_hp = 1.0 if target_card and target_hp <= 2.0 else 0.0
    source_from_hand = 1.0 if source is not None and not source.get("is_placed") else 0.0

    return [
        *_effect_one_hot(effect_id),
        *_target_one_hot(target_type),
        1.0 if effect_id == "TurnEnd" else 0.0,
        1.0 if effect_id == "DeployUnit" else 0.0,
        1.0 if effect_id == "DefaultMove" else 0.0,
        1.0 if effect_id == "DefaultAttack" else 0.0,
        0.0 if source is None else (1.0 if source.get("owner") == ctx.player_id else -1.0),
        0.0 if source is None else _normalize_ratio(float(source.get("atk", 0.0)), 10.0),
        0.0 if source is None else _normalize_ratio(source_atk, 10.0),
        0.0 if source is None else _normalize_ratio(float(source.get("hp", 0.0)), max(1.0, float(source.get("max_hp", 1.0)))),
        _normalize_ratio(attack_mod, 5.0),
        has_move_lock,
        has_attack_lock,
        _normalize_ratio(timed_status_count, 4.0),
        *_role_one_hot(source_role),
        0.0 if target_card is None else (1.0 if target_card.get("owner") != ctx.player_id else -1.0),
        0.0 if target_card is None else _normalize_ratio(float(target_card.get("effective_atk", 0.0)), 10.0),
        0.0 if target_card is None else _normalize_ratio(target_hp, target_max_hp),
        0.0 if target_card is None else (1.0 if target_role == "Leader" else 0.0),
        *_role_one_hot(target_role),
        _normalize_pos(source_x),
        _normalize_pos(source_y),
        _normalize_pos(target_x),
        _normalize_pos(target_y),
        move_distance_before if move_distance_before >= 0 else 0.0,
        move_distance_after if move_distance_after >= 0 else 0.0,
        moves_closer,
        enters_leader_zone,
        can_kill_target,
        threatens_enemy_leader,
        affects_two_units,
        source_survives_trade,
        target_is_low_hp,
        source_from_hand,
        _normalize_ratio(source_adjacent_enemies, 6.0),
        _normalize_ratio(target_incoming_attackers, 6.0),
    ]


def _build_board_vector(snapshot: Dict[str, Any], player_id: str) -> List[float]:
    _, _, enemy_id = _get_players(snapshot, player_id)
    own_leader, enemy_leader = _get_leaders(snapshot, player_id, enemy_id)
    mirror_view = _should_mirror_view(own_leader, enemy_leader)
    own_lx = _view_x(int(own_leader.get("pos_x", -1)), mirror_view) if own_leader else -1
    own_ly = _view_y(int(own_leader.get("pos_y", -1))) if own_leader else -1
    enemy_lx = _view_x(int(enemy_leader.get("pos_x", -1)), mirror_view) if enemy_leader else -1
    enemy_ly = _view_y(int(enemy_leader.get("pos_y", -1))) if enemy_leader else -1
    action_map = _actions_by_source(snapshot)

    vectors: List[float] = []
    cards = _sorted_board_cards(snapshot, player_id, mirror_view)
    for card in cards[:MAX_BOARD_CARDS]:
        attack_mod, has_move_lock, has_attack_lock, timed_status_count = _status_summary(card)
        cx = _view_x(int(card.get("pos_x", -1)), mirror_view)
        cy = _view_y(int(card.get("pos_y", -1)))
        role = _role_from_card(card)
        hp = float(card.get("hp", 0.0))
        max_hp = max(1.0, float(card.get("max_hp", 1.0)))
        effective_atk = float(card.get("effective_atk", 0.0))
        base_atk = float(card.get("atk", 0.0))
        reachable_targets = _count_ready_attack_targets(snapshot, card)
        adjacent_enemies = _count_enemy_neighbors(snapshot, card)
        incoming_attackers = _count_attackers_of_card(snapshot, card)
        card_actions = action_map.get(str(card.get("uid", "")), [])
        has_attack_action = 1.0 if any(str(action.get("effect_id", "")) in {"DefaultAttack", "PawnGeneric"} for action in card_actions) else 0.0
        has_move_action = 1.0 if any(str(action.get("effect_id", "")) == "DefaultMove" for action in card_actions) else 0.0
        threatens_enemy_leader = 1.0 if enemy_leader is not None and _distance(cx, cy, enemy_lx, enemy_ly) >= 0 and _distance(cx, cy, enemy_lx, enemy_ly) <= (1.0 / 5.0) else 0.0
        in_center = 1.0 if 2 <= cx <= 3 and 2 <= cy <= 3 else 0.0
        row_progress = 0.0
        if card.get("is_placed"):
            row_progress = _normalize_ratio(float(cx), BOARD_SIZE - 1)
        owner_is_self = card.get("owner") == player_id
        promotion_ready = _pawn_promotion_ready(card, mirror_view=mirror_view, owner_is_self=owner_is_self)
        promotion_distance = _pawn_promotion_distance(card, mirror_view=mirror_view, owner_is_self=owner_is_self)

        vectors.extend(
            [
                1.0 if card.get("owner") == player_id else -1.0,
                1.0 if card.get("is_placed") else 0.0,
                1.0 if card.get("is_moved") else 0.0,
                1.0 if card.get("is_attacked") else 0.0,
                _normalize_pos(cx),
                _normalize_pos(cy),
                _normalize_ratio(hp, max_hp),
                _normalize_ratio(max_hp, 10.0),
                _normalize_ratio(base_atk, 10.0),
                _normalize_ratio(effective_atk, 10.0),
                _normalize_ratio(attack_mod, 5.0),
                has_move_lock,
                has_attack_lock,
                _normalize_ratio(timed_status_count, 4.0),
                _distance(cx, cy, own_lx, own_ly),
                _distance(cx, cy, enemy_lx, enemy_ly),
                _normalize_ratio(reachable_targets, 6.0),
                _normalize_ratio(adjacent_enemies, 6.0),
                _normalize_ratio(incoming_attackers, 6.0),
                has_attack_action,
                has_move_action,
                threatens_enemy_leader,
                in_center,
                row_progress,
                promotion_ready,
                promotion_distance,
                *_role_one_hot(role),
            ]
        )

    missing_slots = MAX_BOARD_CARDS - min(len(cards), MAX_BOARD_CARDS)
    if missing_slots > 0:
        vectors.extend([0.0] * missing_slots * BOARD_TOKEN_DIM)
    return vectors


def _build_hand_vector(snapshot: Dict[str, Any], player_id: str) -> List[float]:
    own_player, _, _ = _get_players(snapshot, player_id)
    hand = list(own_player.get("hand", []))
    vectors: List[float] = []
    for card in hand[:MAX_HAND_CARDS]:
        role = _role_from_card(card)
        card_id = str(card.get("card_id", ""))
        deployable = 1.0 if any(
            str(action.get("effect_id", "")) == "DeployUnit" and str(action.get("source", "")) == str(card.get("uid", ""))
            for action in snapshot.get("actions", [])
        ) else 0.0
        skill_usable = 1.0 if any(
            str(action.get("effect_id", "")) not in {"DeployUnit", "DefaultMove", "DefaultAttack", "TurnEnd"}
            and str(action.get("source", "")) == str(card.get("uid", ""))
            for action in snapshot.get("actions", [])
        ) else 0.0
        vectors.extend(
            [
                1.0,
                1.0 if card_id.startswith("Or_") else 0.0,
                1.0 if card_id.startswith("Cl_") else 0.0,
                deployable,
                skill_usable,
                *_role_one_hot(role),
            ]
        )
    missing_slots = MAX_HAND_CARDS - min(len(hand), MAX_HAND_CARDS)
    if missing_slots > 0:
        vectors.extend([0.0] * missing_slots * 10)
    return vectors


def build_fixed_state_vector(snapshot: Dict[str, Any], player_id: Optional[str] = None) -> List[float]:
    player_id = player_id or snapshot.get("active_player", "P1")
    ctx = _build_context(snapshot, player_id)
    global_vector = _build_global_vector_ctx(ctx)
    board_vector = _build_board_vector_ctx(ctx)
    hand_vector = _build_hand_vector_ctx(ctx)
    return global_vector + board_vector + hand_vector


def encode_action_features(snapshot: Dict[str, Any], action: Dict[str, Any], player_id: Optional[str] = None) -> List[float]:
    player_id = player_id or snapshot.get("active_player", "P1")
    ctx = _build_context(snapshot, player_id)
    return _encode_action_features_ctx(ctx, action)


ACTION_FEATURE_DIM = len(
    encode_action_features(
        {"board": [], "actions": [], "players": [], "active_player": "P1"},
        {"effect_id": "TurnEnd", "target": {"type": "None", "pos_x": -1, "pos_y": -1}},
    )
)


def build_observation(
    snapshot: Dict[str, Any],
    player_id: Optional[str] = None,
) -> SeaEngineObservation:
    if snapshot.get("state_vector") is not None and snapshot.get("action_feature_vectors") is not None:
        state_vector = list(snapshot.get("state_vector", []))
        return SeaEngineObservation(
            unit_list=[],
            hand_list=[],
            global_vector=list(snapshot.get("global_vector", state_vector[:GLOBAL_FEATURE_DIM])),
            legal_action_mask=[1 for _ in snapshot.get("actions", [])],
            state_vector=state_vector,
            action_feature_vectors=[list(a) for a in snapshot.get("action_feature_vectors", [])],
        )

    player_id = player_id or snapshot.get("active_player", "P1")
    ctx = _build_context(snapshot, player_id)

    unit_list: List[Dict[str, Any]] = []
    hand_list: List[Dict[str, Any]] = []
    global_vector = _build_global_vector_ctx(ctx)

    board_vector = _build_board_vector_ctx(ctx)

    hand_vector = _build_hand_vector_ctx(ctx)

    state_vector = global_vector + board_vector + hand_vector
    action_feature_vectors = [_encode_action_features_ctx(ctx, action) for action in ctx.actions]

    return SeaEngineObservation(
        unit_list=unit_list,
        hand_list=hand_list,
        global_vector=global_vector,
        legal_action_mask=[1 for _ in ctx.actions],
        state_vector=state_vector,
        action_feature_vectors=action_feature_vectors,
    )


STATE_VECTOR_DIM = len(
    build_fixed_state_vector(
        {
            "players": [],
            "board": [],
            "actions": [],
            "active_player": "P1",
            "result": "Ongoing",
        }
    )
)
