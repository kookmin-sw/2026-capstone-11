from __future__ import annotations

# 강화학습 입력으로 쓰기 위한 관측 변환 파일
# 엔진의 전체 state를 그대로 넘기지 않고, 현재 플레이어 기준 공개 정보를
# unit / hand / global / action feature로 가공한다.

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from RL_AI.cards.card_db import CardDefinition, Role, TextCondition
from RL_AI.game_engine.state import (
    Action,
    ActionType,
    BOARD_COLS,
    BOARD_ROWS,
    GameResult,
    GameState,
    Phase,
    PlayerID,
    Position,
    get_sorted_units_for_observation,
)


ROLE_DIM = 5
TEXT_CONDITION_DIM = 5
MAX_UNITS_OBS = 14
MAX_HAND_OBS = 7
UNIT_FEATURE_DIM = 25
HAND_FEATURE_DIM = 15
ACTION_FEATURE_DIM = 43
ACTION_TYPE_ORDER = (
    ActionType.USE_CARD,
    ActionType.MOVE_UNIT,
    ActionType.UNIT_ATTACK,
    ActionType.END_TURN,
)


@dataclass(frozen=True)
class Observation:
    player_id: PlayerID
    unit_list: List[Dict[str, object]]
    hand_list: List[Dict[str, object]]
    global_vector: List[float]
    legal_action_mask: List[int]

    def to_dict(self) -> Dict[str, object]:
        return {
            "player_id": int(self.player_id),
            "unit_list": self.unit_list,
            "hand_list": self.hand_list,
            "global_vector": self.global_vector,
            "legal_action_mask": self.legal_action_mask,
        }


def _one_hot(index: int, size: int) -> List[float]:
    vec = [0.0] * size
    if 0 <= index < size:
        vec[index] = 1.0
    return vec


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _phase_to_one_hot(phase: Phase) -> List[float]:
    if phase == Phase.START:
        return [1.0, 0.0, 0.0]
    if phase == Phase.MAIN:
        return [0.0, 1.0, 0.0]
    return [0.0, 0.0, 1.0]


def _result_to_one_hot_for_player(result: GameResult, player_id: PlayerID) -> List[float]:
    if result == GameResult.ONGOING:
        return [1.0, 0.0, 0.0, 0.0]
    if (result == GameResult.P1_WIN and player_id == PlayerID.P1) or (
        result == GameResult.P2_WIN and player_id == PlayerID.P2
    ):
        return [0.0, 1.0, 0.0, 0.0]
    if (result == GameResult.P1_WIN and player_id == PlayerID.P2) or (
        result == GameResult.P2_WIN and player_id == PlayerID.P1
    ):
        return [0.0, 0.0, 1.0, 0.0]
    return [0.0, 0.0, 0.0, 1.0]


def _owner_view(player_id: PlayerID, owner: PlayerID) -> float:
    return 1.0 if player_id == owner else -1.0


def _position_norm(pos: Optional[Position]) -> List[float]:
    if pos is None:
        return [-1.0, -1.0]
    return [
        pos.row / max(1, BOARD_ROWS - 1),
        pos.col / max(1, BOARD_COLS - 1),
    ]


def _distance_norm(a: Optional[Position], b: Optional[Position]) -> float:
    if a is None or b is None:
        return -1.0
    max_dist = (BOARD_ROWS - 1) + (BOARD_COLS - 1)
    dist = abs(a.row - b.row) + abs(a.col - b.col)
    return dist / max(1, max_dist)


def _runtime_unit_for_card_instance(state: GameState, owner: PlayerID, card_instance_id: str):
    for unit in state.units.values():
        if unit.owner == owner and unit.source_card_instance_id == card_instance_id:
            return unit
    return None


def _encode_unit_feature_vector(state: GameState, player_id: PlayerID, unit) -> List[float]:
    my_leader = state.get_leader_runtime_unit(player_id)
    enemy_leader = state.get_leader_runtime_unit(player_id.opponent())
    own_home_row = 0 if unit.owner == PlayerID.P1 else BOARD_ROWS - 1
    pos = unit.position
    row_norm, col_norm = _position_norm(pos)

    return [
        _owner_view(player_id, unit.owner),
        *[float(v) for v in _one_hot(int(unit.role), ROLE_DIM)],
        _clamp01(unit.attack / 10.0),
        _clamp01(unit.max_life / 15.0),
        0.0 if unit.max_life <= 0 else _clamp01(unit.current_life / unit.max_life),
        row_norm,
        col_norm,
        1.0 if unit.is_on_board else 0.0,
        1.0 if unit.is_alive() else 0.0,
        1.0 if unit.retired else 0.0,
        1.0 if unit.role == Role.LEADER else 0.0,
        1.0 if unit.owner == player_id else 0.0,
        1.0 if unit.can_move() else 0.0,
        1.0 if unit.can_attack() else 0.0,
        1.0 if unit.moved_this_turn else 0.0,
        1.0 if unit.attacked_this_turn else 0.0,
        1.0 if unit.promoted else 0.0,
        _clamp01(unit.shield / 3.0),
        _clamp01(unit.disabled_move_turns / 3.0),
        _clamp01(unit.disabled_attack_turns / 3.0),
        0.0 if pos is None else (1.0 if pos.row == own_home_row else 0.0),
        _distance_norm(pos, None if my_leader is None else my_leader.position),
        _distance_norm(pos, None if enemy_leader is None else enemy_leader.position),
    ]


def _encode_hand_feature_vector(
    state: GameState,
    player_id: PlayerID,
    card,
    *,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> List[float]:
    card_def = None if card_db is None else card_db.get(card.card_id)
    runtime_unit = _runtime_unit_for_card_instance(state, player_id, card.instance_id)
    runtime_alive = runtime_unit is not None and runtime_unit.is_alive()
    has_summon_space = 1.0 if state.get_empty_home_cells(player_id) else 0.0
    role_one_hot = [0.0] * ROLE_DIM if card_def is None else [float(v) for v in _one_hot(int(card_def.role), ROLE_DIM)]
    text_one_hot = (
        [0.0] * TEXT_CONDITION_DIM
        if card_def is None
        else [float(v) for v in _one_hot(int(card_def.text_condition), TEXT_CONDITION_DIM)]
    )

    return [
        -1.0 if card_def is None else _clamp01(card_def.world / 10.0),
        *role_one_hot,
        -1.0 if card_def is None else _clamp01(card_def.attack / 10.0),
        -1.0 if card_def is None else _clamp01(card_def.life / 15.0),
        *text_one_hot,
        1.0 if runtime_alive else 0.0,
        0.0 if runtime_alive else has_summon_space,
    ]


def _find_card_in_hand(state: GameState, player_id: PlayerID, card_instance_id: str):
    player = state.get_player(player_id)
    return next((card for card in player.hand if card.instance_id == card_instance_id), None)


def _signed_progress_toward_enemy_leader(player_id: PlayerID, src: Optional[Position], dst: Optional[Position], enemy_leader_pos: Optional[Position]) -> float:
    if src is None or dst is None or enemy_leader_pos is None:
        return 0.0
    before = _distance_norm(src, enemy_leader_pos)
    after = _distance_norm(dst, enemy_leader_pos)
    if before < 0.0 or after < 0.0:
        return 0.0
    return before - after


def build_unit_list_observation(state: GameState, player_id: PlayerID) -> List[Dict[str, object]]:
    units = get_sorted_units_for_observation(state)
    unit_list: List[Dict[str, object]] = []
    for unit in units:
        unit_list.append(
            {
                "unit_id": unit.unit_id,
                "owner": int(unit.owner),
                "source_card_id": unit.source_card_id,
                "feature_vector": _encode_unit_feature_vector(state, player_id, unit),
            }
        )
    return unit_list


def build_hand_list_observation(
    state: GameState,
    player_id: PlayerID,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> List[Dict[str, object]]:
    player = state.get_player(player_id)
    hand_obs: List[Dict[str, object]] = []
    for card in player.hand:
        card_def = None if card_db is None else card_db.get(card.card_id)
        hand_obs.append(
            {
                "instance_id": card.instance_id,
                "card_id": card.card_id,
                "name": None if card_def is None else card_def.name,
                "feature_vector": _encode_hand_feature_vector(state, player_id, card, card_db=card_db),
            }
        )
    return hand_obs


def build_global_vector_observation(state: GameState, player_id: PlayerID) -> List[float]:
    me = state.get_player(player_id)
    enemy = state.get_player(player_id.opponent())
    my_leader = state.get_leader_runtime_unit(player_id)
    enemy_leader = state.get_leader_runtime_unit(player_id.opponent())
    my_units = state.get_board_units_by_owner(player_id)
    enemy_units = state.get_board_units_by_owner(player_id.opponent())

    my_hp_ratio = 0.0 if my_leader is None or my_leader.max_life <= 0 else _clamp01(my_leader.current_life / my_leader.max_life)
    enemy_hp_ratio = (
        0.0 if enemy_leader is None or enemy_leader.max_life <= 0 else _clamp01(enemy_leader.current_life / enemy_leader.max_life)
    )

    return [
        _clamp01(state.turn / 100.0),
        1.0 if state.active_player == player_id else 0.0,
        *[float(v) for v in _phase_to_one_hot(state.phase)],
        *[float(v) for v in _result_to_one_hot_for_player(state.result, player_id)],
        _clamp01(len(me.hand) / MAX_HAND_OBS),
        _clamp01(len(me.deck) / 20.0),
        _clamp01(len(me.trash) / 20.0),
        _clamp01(len(enemy.hand) / MAX_HAND_OBS),
        _clamp01(len(enemy.deck) / 20.0),
        _clamp01(len(enemy.trash) / 20.0),
        my_hp_ratio,
        enemy_hp_ratio,
        my_hp_ratio - enemy_hp_ratio,
        _clamp01(len(my_units) / 7.0),
        _clamp01(len(enemy_units) / 7.0),
        _clamp01(len(my_units) / 7.0) - _clamp01(len(enemy_units) / 7.0),
    ]


def build_legal_action_mask(legal_actions: Sequence[Action]) -> List[int]:
    return [1] * len(legal_actions)


def encode_action_type_histogram(legal_actions: Sequence[Action]) -> List[float]:
    counts = {action_type: 0.0 for action_type in ACTION_TYPE_ORDER}
    total = float(max(1, len(legal_actions)))
    for action in legal_actions:
        counts[action.action_type] += 1.0
    return [counts[action_type] / total for action_type in ACTION_TYPE_ORDER]


def build_observation(
    state: GameState,
    player_id: PlayerID,
    legal_actions: Sequence[Action],
    *,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> Observation:
    global_vector = build_global_vector_observation(state, player_id)
    global_vector.extend(encode_action_type_histogram(legal_actions))

    return Observation(
        player_id=player_id,
        unit_list=build_unit_list_observation(state, player_id),
        hand_list=build_hand_list_observation(state, player_id, card_db=card_db),
        global_vector=global_vector,
        legal_action_mask=build_legal_action_mask(legal_actions),
    )


def flatten_observation(observation: Observation) -> List[float]:
    flat: List[float] = list(observation.global_vector)
    for unit in observation.unit_list:
        flat.extend(float(v) for v in unit["feature_vector"])
    for card in observation.hand_list:
        flat.extend(float(v) for v in card["feature_vector"])
    flat.extend(float(value) for value in observation.legal_action_mask)
    return flat


def build_fixed_state_vector(
    state: GameState,
    player_id: PlayerID,
    legal_actions: Sequence[Action],
    *,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> List[float]:
    observation = build_observation(state, player_id, legal_actions, card_db=card_db)
    flat: List[float] = list(observation.global_vector)

    for unit in observation.unit_list[:MAX_UNITS_OBS]:
        flat.extend(float(v) for v in unit["feature_vector"])
    for _ in range(max(0, MAX_UNITS_OBS - len(observation.unit_list))):
        flat.extend([0.0] * UNIT_FEATURE_DIM)

    for card in observation.hand_list[:MAX_HAND_OBS]:
        flat.extend(float(v) for v in card["feature_vector"])
    for _ in range(max(0, MAX_HAND_OBS - len(observation.hand_list))):
        flat.extend([0.0] * HAND_FEATURE_DIM)

    return flat


def encode_action_features(
    state: GameState,
    player_id: PlayerID,
    action: Action,
    *,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> List[float]:
    action_type_one_hot = [1.0 if action.action_type == action_type else 0.0 for action_type in ACTION_TYPE_ORDER]
    enemy_leader = state.get_leader_runtime_unit(player_id.opponent())

    source_role = [0.0] * ROLE_DIM
    source_attack = 0.0
    source_life_ratio = 0.0
    source_can_attack = 0.0
    source_can_move = 0.0
    source_pos: Optional[Position] = None
    if action.source_unit_id is not None:
        source = state.get_unit(action.source_unit_id)
        source_role = [float(v) for v in _one_hot(int(source.role), ROLE_DIM)]
        source_attack = _clamp01(source.attack / 10.0)
        source_life_ratio = 0.0 if source.max_life <= 0 else _clamp01(source.current_life / source.max_life)
        source_can_attack = 1.0 if source.can_attack() else 0.0
        source_can_move = 1.0 if source.can_move() else 0.0
        source_pos = source.position

    target_enemy_count = 0.0
    target_ally_count = 0.0
    target_leader_count = 0.0
    target_total_life_ratio = 0.0
    target_low_hp_count = 0.0
    kill_potential_count = 0.0
    first_target_dist_enemy_leader = -1.0
    for index, target_unit_id in enumerate(action.target_unit_ids):
        target = state.get_unit(target_unit_id)
        if target.owner == player_id:
            target_ally_count += 1.0
        else:
            target_enemy_count += 1.0
        if target.role == Role.LEADER:
            target_leader_count += 1.0
        if target.max_life > 0:
            target_life_ratio = _clamp01(target.current_life / target.max_life)
            target_total_life_ratio += target_life_ratio
            if target_life_ratio <= 0.34:
                target_low_hp_count += 1.0
        if source_attack > 0.0 and target.current_life > 0:
            estimated_attack = source_attack * 10.0
            if estimated_attack >= target.current_life:
                kill_potential_count += 1.0
        if index == 0:
            first_target_dist_enemy_leader = _distance_norm(target.position, None if enemy_leader is None else enemy_leader.position)

    target_pos = action.target_positions[0] if action.target_positions else None
    target_row_norm, target_col_norm = _position_norm(target_pos)
    source_row_norm, source_col_norm = _position_norm(source_pos)
    move_progress = _signed_progress_toward_enemy_leader(player_id, source_pos, target_pos, None if enemy_leader is None else enemy_leader.position)

    card_role = [0.0] * ROLE_DIM
    card_attack = -1.0
    card_life = -1.0
    card_text_condition = [0.0] * TEXT_CONDITION_DIM
    card_is_effect = 0.0
    card_is_summon = 0.0
    if action.card_instance_id is not None:
        card = _find_card_in_hand(state, player_id, action.card_instance_id)
        if card is not None and card_db is not None and card.card_id in card_db:
            card_def = card_db[card.card_id]
            card_role = [float(v) for v in _one_hot(int(card_def.role), ROLE_DIM)]
            card_attack = _clamp01(card_def.attack / 10.0)
            card_life = _clamp01(card_def.life / 15.0)
            card_text_condition = [float(v) for v in _one_hot(int(card_def.text_condition), TEXT_CONDITION_DIM)]
            runtime_unit = _runtime_unit_for_card_instance(state, player_id, action.card_instance_id)
            if runtime_unit is not None and runtime_unit.is_alive():
                card_is_effect = 1.0
            else:
                card_is_summon = 1.0

    return [
        *action_type_one_hot,
        1.0 if action.card_instance_id is not None else 0.0,
        1.0 if action.source_unit_id is not None else 0.0,
        float(len(action.target_unit_ids)) / 2.0,
        float(len(action.target_positions)),
        target_enemy_count / 2.0,
        target_ally_count / 2.0,
        target_leader_count,
        target_total_life_ratio / max(1.0, float(len(action.target_unit_ids))),
        target_low_hp_count / 2.0,
        kill_potential_count / 2.0,
        *source_role,
        source_attack,
        source_life_ratio,
        source_can_attack,
        source_can_move,
        source_row_norm,
        source_col_norm,
        target_row_norm,
        target_col_norm,
        move_progress,
        first_target_dist_enemy_leader,
        *card_role,
        card_attack,
        card_life,
        *card_text_condition,
        card_is_effect,
        card_is_summon,
    ]
