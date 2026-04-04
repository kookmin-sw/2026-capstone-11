from __future__ import annotations

# 강화학습 입력으로 쓰기 위한 관측 변환 파일
# 엔진의 전체 state를 그대로 넘기지 않고, 현재 플레이어 기준 공개 정보만 unit_list / hand_list /
# global_vector / legal_action_mask 형태로 가공한다.

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from RL_AI.cards.card_db import CardDefinition, Role
from RL_AI.game_engine.state import (
    Action,
    ActionType,
    BOARD_COLS,
    BOARD_ROWS,
    GameResult,
    GameState,
    Phase,
    PlayerID,
    get_sorted_units_for_observation,
)


ROLE_DIM = 5
MAX_UNITS_OBS = 14
MAX_HAND_OBS = 7
UNIT_FEATURE_DIM = 16
HAND_FEATURE_DIM = 5
ACTION_FEATURE_DIM = 19
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


def _phase_to_scalar(phase: Phase) -> float:
    if phase == Phase.START:
        return 0.0
    if phase == Phase.MAIN:
        return 1.0
    return 2.0


def _result_to_scalar(result: GameResult) -> float:
    if result == GameResult.ONGOING:
        return 0.0
    if result == GameResult.P1_WIN:
        return 1.0
    if result == GameResult.P2_WIN:
        return 2.0
    return 3.0


def _owner_view(player_id: PlayerID, owner: PlayerID) -> float:
    return 1.0 if player_id == owner else -1.0


def _encode_unit_for_player(state: GameState, player_id: PlayerID, unit) -> Dict[str, object]:
    position_row = -1 if unit.position is None else unit.position.row
    position_col = -1 if unit.position is None else unit.position.col

    return {
        "unit_id": unit.unit_id,
        "source_card_id": unit.source_card_id,
        "owner": int(unit.owner),
        "owner_view": _owner_view(player_id, unit.owner),
        "role": int(unit.role),
        "role_one_hot": _one_hot(int(unit.role), ROLE_DIM),
        "attack": unit.attack,
        "max_life": unit.max_life,
        "current_life": unit.current_life,
        "position_row": position_row,
        "position_col": position_col,
        "position_norm": [
            -1.0 if position_row < 0 else position_row / max(1, BOARD_ROWS - 1),
            -1.0 if position_col < 0 else position_col / max(1, BOARD_COLS - 1),
        ],
        "is_on_board": 1.0 if unit.is_on_board else 0.0,
        "is_alive": 1.0 if unit.is_alive() else 0.0,
        "retired": 1.0 if unit.retired else 0.0,
        "moved_this_turn": 1.0 if unit.moved_this_turn else 0.0,
        "attacked_this_turn": 1.0 if unit.attacked_this_turn else 0.0,
        "promoted": 1.0 if unit.promoted else 0.0,
        "shield": float(unit.shield),
        "disabled_move_turns": float(unit.disabled_move_turns),
        "disabled_attack_turns": float(unit.disabled_attack_turns),
    }


def build_unit_list_observation(state: GameState, player_id: PlayerID) -> List[Dict[str, object]]:
    units = get_sorted_units_for_observation(state)
    return [_encode_unit_for_player(state, player_id, unit) for unit in units]


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
                "world": None if card_def is None else card_def.world,
                "role": None if card_def is None else int(card_def.role),
                "attack": None if card_def is None else card_def.attack,
                "life": None if card_def is None else card_def.life,
                "text_condition": None if card_def is None else int(card_def.text_condition),
                "text_name": None if card_def is None else card_def.text_name,
                "effect_name": None if card_def is None else card_def.effect_name,
            }
        )
    return hand_obs


def build_global_vector_observation(state: GameState, player_id: PlayerID) -> List[float]:
    me = state.get_player(player_id)
    enemy = state.get_player(player_id.opponent())
    my_leader = state.get_leader_runtime_unit(player_id)
    enemy_leader = state.get_leader_runtime_unit(player_id.opponent())

    return [
        float(state.turn),
        float(int(player_id)),
        float(int(state.active_player)),
        1.0 if state.active_player == player_id else 0.0,
        _phase_to_scalar(state.phase),
        _result_to_scalar(state.result),
        float(len(me.hand)),
        float(len(me.deck)),
        float(len(me.trash)),
        float(len(enemy.hand)),  # 현재는 hand count만 공개 정보로 본다
        float(len(enemy.deck)),
        float(len(enemy.trash)),
        0.0 if my_leader is None else float(my_leader.current_life),
        0.0 if my_leader is None else float(my_leader.max_life),
        0.0 if enemy_leader is None else float(enemy_leader.current_life),
        0.0 if enemy_leader is None else float(enemy_leader.max_life),
        float(len(state.get_board_units_by_owner(player_id))),
        float(len(state.get_board_units_by_owner(player_id.opponent()))),
    ]


def build_legal_action_mask(legal_actions: Sequence[Action]) -> List[int]:
    return [1] * len(legal_actions)


def encode_action_type_histogram(legal_actions: Sequence[Action]) -> List[float]:
    counts = {action_type: 0.0 for action_type in ACTION_TYPE_ORDER}
    for action in legal_actions:
        counts[action.action_type] += 1.0
    return [counts[action_type] for action_type in ACTION_TYPE_ORDER]


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
    """
    Very small starter flattening helper.
    This is not the final model input format, but it is enough to prototype
    a simple tabular / MLP-based RL pipeline quickly.
    """
    flat: List[float] = list(observation.global_vector)

    for unit in observation.unit_list:
        flat.extend(
            [
                float(unit["owner_view"]),
                float(unit["role"]),
                float(unit["attack"]),
                float(unit["max_life"]),
                float(unit["current_life"]),
                float(unit["position_row"]),
                float(unit["position_col"]),
                float(unit["is_on_board"]),
                float(unit["is_alive"]),
                float(unit["retired"]),
                float(unit["moved_this_turn"]),
                float(unit["attacked_this_turn"]),
                float(unit["promoted"]),
                float(unit["shield"]),
                float(unit["disabled_move_turns"]),
                float(unit["disabled_attack_turns"]),
            ]
        )

    for card in observation.hand_list:
        flat.extend(
            [
                -1.0 if card["world"] is None else float(card["world"]),
                -1.0 if card["role"] is None else float(card["role"]),
                -1.0 if card["attack"] is None else float(card["attack"]),
                -1.0 if card["life"] is None else float(card["life"]),
                -1.0 if card["text_condition"] is None else float(card["text_condition"]),
            ]
        )

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
        flat.extend(
            [
                float(unit["owner_view"]),
                float(unit["role"]),
                float(unit["attack"]),
                float(unit["max_life"]),
                float(unit["current_life"]),
                float(unit["position_row"]),
                float(unit["position_col"]),
                float(unit["is_on_board"]),
                float(unit["is_alive"]),
                float(unit["retired"]),
                float(unit["moved_this_turn"]),
                float(unit["attacked_this_turn"]),
                float(unit["promoted"]),
                float(unit["shield"]),
                float(unit["disabled_move_turns"]),
                float(unit["disabled_attack_turns"]),
            ]
        )

    for _ in range(max(0, MAX_UNITS_OBS - len(observation.unit_list))):
        flat.extend([0.0] * UNIT_FEATURE_DIM)

    for card in observation.hand_list[:MAX_HAND_OBS]:
        flat.extend(
            [
                -1.0 if card["world"] is None else float(card["world"]),
                -1.0 if card["role"] is None else float(card["role"]),
                -1.0 if card["attack"] is None else float(card["attack"]),
                -1.0 if card["life"] is None else float(card["life"]),
                -1.0 if card["text_condition"] is None else float(card["text_condition"]),
            ]
        )

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

    source_attack = 0.0
    source_life = 0.0
    source_role = -1.0
    if action.source_unit_id is not None:
        source = state.get_unit(action.source_unit_id)
        source_attack = float(source.attack)
        source_life = float(source.current_life)
        source_role = float(int(source.role))

    target_enemy_count = 0.0
    target_ally_count = 0.0
    target_leader_count = 0.0
    target_life_sum = 0.0
    for target_unit_id in action.target_unit_ids:
        target = state.get_unit(target_unit_id)
        if target.owner == player_id:
            target_ally_count += 1.0
        else:
            target_enemy_count += 1.0
        if target.role == Role.LEADER:
            target_leader_count += 1.0
        target_life_sum += float(target.current_life)

    pos_row = -1.0
    pos_col = -1.0
    if action.target_positions:
        pos_row = float(action.target_positions[0].row)
        pos_col = float(action.target_positions[0].col)

    card_world = -1.0
    card_role = -1.0
    if action.card_instance_id is not None:
        player = state.get_player(player_id)
        card = next((c for c in player.hand if c.instance_id == action.card_instance_id), None)
        if card is not None and card_db is not None and card.card_id in card_db:
            card_def = card_db[card.card_id]
            card_world = float(card_def.world)
            card_role = float(int(card_def.role))

    return [
        *action_type_one_hot,
        0.0 if action.card_instance_id is None else 1.0,
        0.0 if action.source_unit_id is None else 1.0,
        float(len(action.target_unit_ids)),
        float(len(action.target_positions)),
        target_enemy_count,
        target_ally_count,
        target_leader_count,
        target_life_sum,
        source_attack,
        source_life,
        source_role,
        pos_row,
        pos_col,
        card_world,
        card_role,
    ]
