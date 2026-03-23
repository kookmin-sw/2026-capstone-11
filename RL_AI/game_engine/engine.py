#상태 변화 로직을 정의한 파일
#게임의 상태 전이 엔진
#게임 상태에 합법 행동을 적용하고 드로우, 효과 처리, 전투, 카드 버리기, 승패 판정을 처리함
#규칙/상태와 플레이/훈련 사이의 변환 계층
from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from RL_AI.cards.card_db import CardDefinition, TextCondition
from RL_AI.game_engine.rules import (
    W1_BISHOP,
    W1_KING,
    W1_KNIGHT,
    W1_PAWN,
    W1_ROOK,
    W2_BISHOP,
    W2_KNIGHT,
    W2_PAWN,
    W2_PRINCESS,
    W2_ROOK,
    can_attack_unit,
    can_move_unit,
    can_unit_attack_target_by_effect,
    can_use_card,
    get_enemy_units_on_board,
    is_legal_action,
    is_position_in_unit_move_range,
)
from RL_AI.game_engine.state import (
    Action,
    ActionType,
    BOARD_ROWS,
    GameState,
    HAND_LIMIT_AT_END,
    Phase,
    PlayerID,
    TargetSelection,
    UnitState,
)


def _rng_or_default(rng: Optional[random.Random]) -> random.Random:
    return rng if rng is not None else random.Random()


def _far_row_for(owner: PlayerID) -> int:
    return BOARD_ROWS - 1 if owner == PlayerID.P1 else 0


def _sort_units_for_determinism(units: Iterable[UnitState]) -> List[UnitState]:
    return sorted(
        units,
        key=lambda u: (
            int(u.owner),
            u.current_life,
            99 if u.position is None else u.position.row,
            99 if u.position is None else u.position.col,
            u.unit_id,
        ),
    )


def _choose_first(seq: Sequence[UnitState]) -> Optional[UnitState]:
    return seq[0] if seq else None


def _dedupe_keep_order(items: Sequence[str]) -> Tuple[str, ...]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def _find_card_zone_and_index(state: GameState, player_id: PlayerID, card_instance_id: str) -> Tuple[str, int]:
    player = state.get_player(player_id)
    for zone_name in ("deck", "hand", "trash"):
        zone = getattr(player, zone_name)
        for idx, card in enumerate(zone):
            if card.instance_id == card_instance_id:
                return zone_name, idx
    raise ValueError(f"Card instance not found in any zone: {card_instance_id}")


def _move_card_between_zones(state: GameState, player_id: PlayerID, card_instance_id: str, to_zone: str) -> None:
    player = state.get_player(player_id)
    from_zone_name, idx = _find_card_zone_and_index(state, player_id, card_instance_id)
    from_zone = getattr(player, from_zone_name)
    card = from_zone.pop(idx)
    getattr(player, to_zone).append(card)


def _get_runtime_unit_for_card_instance(state: GameState, owner: PlayerID, card_instance_id: str) -> Optional[UnitState]:
    for unit in state.units.values():
        if unit.owner == owner and unit.source_card_instance_id == card_instance_id:
            return unit
    return None


def _resolve_action_targets(state: GameState, player_id: PlayerID, action: Action) -> List[UnitState]:
    if action.target_selection == TargetSelection.EXPLICIT:
        ids = _dedupe_keep_order(action.target_unit_ids)
    elif action.target_selection == TargetSelection.ALL_ENEMIES:
        ids = tuple(u.unit_id for u in state.get_board_units_by_owner(player_id.opponent()))
    elif action.target_selection == TargetSelection.ALL_ALLIES:
        ids = tuple(u.unit_id for u in state.get_board_units_by_owner(player_id))
    elif action.target_selection == TargetSelection.ALL_UNITS:
        ids = tuple(u.unit_id for u in state.get_board_units())
    else:
        ids = ()
    return [state.get_unit(uid) for uid in ids]


def _alive_enemy_units_in_attack_range(state: GameState, source_unit: UnitState) -> List[UnitState]:
    if source_unit.position is None:
        return []
    out: List[UnitState] = []
    for enemy in state.get_board_units_by_owner(source_unit.owner.opponent()):
        if can_unit_attack_target_by_effect(state, source_unit, enemy):
            out.append(enemy)
    return _sort_units_for_determinism(out)


def _leader_of(state: GameState, owner: PlayerID) -> Optional[UnitState]:
    return state.get_leader_unit(owner)


def _draw_cards(state: GameState, player_id: PlayerID, count: int, rng: random.Random):
    return state.get_player(player_id).draw(count, rng)


def _discard_down_to_hand_limit(state: GameState, player_id: PlayerID, hand_limit: int = HAND_LIMIT_AT_END) -> List[str]:
    player = state.get_player(player_id)
    discarded_ids: List[str] = []
    while len(player.hand) > hand_limit:
        card = player.hand.pop()
        player.trash.append(card)
        discarded_ids.append(card.instance_id)
    return discarded_ids


def _set_terminal_if_needed(state: GameState) -> None:
    state.check_leader_death()


def _handle_unit_retired(state: GameState, retired_unit: UnitState, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    card_id = retired_unit.source_card_id
    owner = retired_unit.owner
    if card_id == W2_BISHOP:
        leader = _leader_of(state, owner)
        if leader is not None:
            leader.heal(2)
    elif card_id == W2_KNIGHT:
        try:
            zone_name, _ = _find_card_zone_and_index(state, owner, retired_unit.source_card_instance_id)
        except ValueError:
            zone_name = ""
        if zone_name == "trash":
            _move_card_between_zones(state, owner, retired_unit.source_card_instance_id, "hand")
    _set_terminal_if_needed(state)


def _after_unit_moved(state: GameState, moved_unit: UnitState, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    if not moved_unit.is_alive() or moved_unit.position is None:
        return
    if moved_unit.source_card_id == W2_PAWN and moved_unit.position.row == _far_row_for(moved_unit.owner):
        moved_unit.retire()
        _handle_unit_retired(state, moved_unit, card_db, rng)
        _draw_cards(state, moved_unit.owner, 2, rng)
        _set_terminal_if_needed(state)


def _process_start_triggers(state: GameState, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    owner = state.active_player
    for unit in _sort_units_for_determinism(state.get_board_units_by_owner(owner)):
        if unit.text_condition != TextCondition.TURN_START or not unit.is_alive():
            continue
        if unit.source_card_id in {W1_KING, W1_BISHOP, W1_KNIGHT, W1_ROOK}:
            target = _choose_first(_alive_enemy_units_in_attack_range(state, unit))
            if target is not None:
                _resolve_direct_attack(state, unit, target, card_db, rng, move_after_kill=False)
        elif unit.source_card_id == W2_PRINCESS:
            unit.heal(1)
        _set_terminal_if_needed(state)
        if state.is_terminal():
            return


def _process_end_triggers(state: GameState, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    owner = state.active_player
    for unit in _sort_units_for_determinism(state.get_board_units_by_owner(owner)):
        if unit.text_condition != TextCondition.TURN_END or not unit.is_alive():
            continue
        if unit.source_card_id == W1_PAWN and unit.position is not None and unit.position.row == _far_row_for(unit.owner):
            if not unit.promoted:
                unit.promoted = True
                unit.attack += 2
                unit.max_life += 4
                unit.current_life += 4
        elif unit.source_card_id == W2_ROOK:
            target = _choose_first(_alive_enemy_units_in_attack_range(state, unit))
            if target is not None:
                _resolve_direct_attack(state, unit, target, card_db, rng, move_after_kill=False)
        _set_terminal_if_needed(state)
        if state.is_terminal():
            return


def _resolve_direct_attack(
    state: GameState,
    attacker: UnitState,
    defender: UnitState,
    card_db: Dict[str, CardDefinition],
    rng: random.Random,
    move_after_kill: bool = False,
) -> bool:
    if not attacker.is_alive() or not defender.is_alive():
        return False
    defender_pos_before = defender.position
    defender_alive_before = defender.is_alive()
    defender.take_damage(attacker.attack)
    defender_killed = defender_alive_before and not defender.is_alive()
    if defender_killed:
        _handle_unit_retired(state, defender, card_db, rng)
        if move_after_kill and attacker.is_alive() and defender_pos_before is not None and state.is_empty(defender_pos_before):
            attacker.position = defender_pos_before
            _after_unit_moved(state, attacker, card_db, rng)
    _set_terminal_if_needed(state)
    return defender_killed


def _partition_mixed_unit_targets(player_id: PlayerID, targets: Sequence[UnitState]) -> Tuple[List[UnitState], List[UnitState]]:
    allies = [u for u in targets if u.owner == player_id]
    enemies = [u for u in targets if u.owner != player_id]
    return allies, enemies


def _resolve_card_summon(state: GameState, player_id: PlayerID, action: Action, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    assert action.card_instance_id is not None and len(action.target_positions) == 1
    summon_pos = action.target_positions[0]
    player = state.get_player(player_id)
    card = player.remove_from_hand(action.card_instance_id)
    unit = _get_runtime_unit_for_card_instance(state, player_id, card.instance_id)
    if unit is None:
        raise ValueError(f"No runtime unit for card instance: {card.instance_id}")
    unit.summon_to(summon_pos)
    player.move_to_trash(card)
    _set_terminal_if_needed(state)


def _resolve_card_effect(state: GameState, player_id: PlayerID, action: Action, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    assert action.card_instance_id is not None
    player = state.get_player(player_id)
    card = next(c for c in player.hand if c.instance_id == action.card_instance_id)
    source_unit = _get_runtime_unit_for_card_instance(state, player_id, action.card_instance_id)
    if source_unit is None or not source_unit.is_alive():
        raise ValueError("Cannot activate effect: source unit is not alive on board.")

    targets = _resolve_action_targets(state, player_id, action)

    if card.card_id == W1_KING:
        _draw_cards(state, player_id, 1, rng)
        if len(targets) == 1 and len(action.target_positions) == 1:
            ally = targets[0]
            dst = action.target_positions[0]
            if ally.owner == player_id and can_move_unit(state, player_id, ally.unit_id, dst):
                state.move_unit(ally.unit_id, dst)
                ally.moved_this_turn = True
                _after_unit_moved(state, ally, card_db, rng)

    elif card.card_id == W1_BISHOP:
        for target in targets[:2]:
            if not source_unit.is_alive():
                break
            if target.owner != player_id and target.is_alive() and can_unit_attack_target_by_effect(state, source_unit, target):
                _resolve_direct_attack(state, source_unit, target, card_db, rng, move_after_kill=False)

    elif card.card_id == W1_KNIGHT:
        if len(targets) == 1:
            target = targets[0]
            if target.owner != player_id and target.is_alive() and can_unit_attack_target_by_effect(state, source_unit, target):
                _resolve_direct_attack(state, source_unit, target, card_db, rng, move_after_kill=True)

    elif card.card_id == W1_ROOK:
        source_unit.full_heal()
        if len(targets) == 1:
            ally = targets[0]
            if ally.owner == player_id and ally.is_alive():
                ally.heal(1)

    elif card.card_id == W1_PAWN:
        allies, enemies = _partition_mixed_unit_targets(player_id, targets)
        if len(allies) == 1 and len(enemies) == 1:
            attacker, defender = allies[0], enemies[0]
            if attacker.is_alive() and defender.is_alive() and can_unit_attack_target_by_effect(state, attacker, defender):
                _resolve_direct_attack(state, attacker, defender, card_db, rng, move_after_kill=False)

    elif card.card_id == W2_PRINCESS:
        _draw_cards(state, player_id, 1, rng)
        if len(targets) == 1:
            ally = targets[0]
            if ally.owner == player_id and ally.is_alive():
                ally.heal(2)

    elif card.card_id == W2_BISHOP:
        if len(action.target_positions) == 1:
            leader = _leader_of(state, player_id)
            dst = action.target_positions[0]
            if leader is not None and is_position_in_unit_move_range(state, source_unit, dst, require_empty=True):
                state.move_unit(leader.unit_id, dst)
                leader.moved_this_turn = True
                _after_unit_moved(state, leader, card_db, rng)

    elif card.card_id == W2_KNIGHT:
        if len(targets) == 1:
            target = targets[0]
            if target.owner != player_id and target.is_alive() and can_unit_attack_target_by_effect(state, source_unit, target):
                _resolve_direct_attack(state, source_unit, target, card_db, rng, move_after_kill=True)

    elif card.card_id == W2_ROOK:
        if not source_unit.moved_this_turn and len(targets) == 1:
            source_unit.disabled_move_turns = max(source_unit.disabled_move_turns, 1)
            target = targets[0]
            if target.owner != player_id and target.is_alive():
                target.disabled_move_turns = max(target.disabled_move_turns, 1)

    elif card.card_id == W2_PAWN:
        allies, enemies = _partition_mixed_unit_targets(player_id, targets)
        if len(allies) == 1 and len(enemies) == 1:
            attacker, defender = allies[0], enemies[0]
            if attacker.is_alive() and defender.is_alive() and can_unit_attack_target_by_effect(state, attacker, defender):
                _resolve_direct_attack(state, attacker, defender, card_db, rng, move_after_kill=False)

    used_card = player.remove_from_hand(action.card_instance_id)
    player.move_to_trash(used_card)
    _set_terminal_if_needed(state)


def _resolve_use_card(state: GameState, player_id: PlayerID, action: Action, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    assert action.card_instance_id is not None
    player = state.get_player(player_id)
    hand_card = next((c for c in player.hand if c.instance_id == action.card_instance_id), None)
    if hand_card is None:
        raise ValueError(f"Card not found in hand: {action.card_instance_id}")
    if not state.unit_exists_for_card(player_id, hand_card.card_id):
        _resolve_card_summon(state, player_id, action, card_db, rng)
    else:
        _resolve_card_effect(state, player_id, action, card_db, rng)


def _resolve_move_unit(state: GameState, player_id: PlayerID, action: Action, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    assert action.source_unit_id is not None and len(action.target_positions) == 1
    unit = state.get_unit(action.source_unit_id)
    dst = action.target_positions[0]
    state.move_unit(unit.unit_id, dst)
    unit.moved_this_turn = True
    _after_unit_moved(state, unit, card_db, rng)
    _set_terminal_if_needed(state)


def _resolve_unit_attack(state: GameState, player_id: PlayerID, action: Action, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    assert action.source_unit_id is not None and len(action.target_unit_ids) == 1
    attacker = state.get_unit(action.source_unit_id)
    defender = state.get_unit(action.target_unit_ids[0])
    _resolve_direct_attack(state, attacker, defender, card_db, rng, move_after_kill=False)
    if attacker.is_alive():
        attacker.attacked_this_turn = True


def run_start_phase(state: GameState, card_db: Dict[str, CardDefinition], rng: Optional[random.Random] = None) -> GameState:
    rng = _rng_or_default(rng)
    next_state = state.clone_shallow()
    if next_state.is_terminal() or next_state.phase != Phase.START:
        return next_state
    _draw_cards(next_state, next_state.active_player, 2, rng)
    _process_start_triggers(next_state, card_db, rng)
    if not next_state.is_terminal():
        next_state.phase = Phase.MAIN
    return next_state


def _resolve_end_turn(state: GameState, card_db: Dict[str, CardDefinition], rng: random.Random) -> None:
    owner = state.active_player
    state.phase = Phase.END
    _process_end_triggers(state, card_db, rng)
    if state.is_terminal():
        return
    _discard_down_to_hand_limit(state, owner, HAND_LIMIT_AT_END)
    if state.is_terminal():
        return
    state.active_player = owner.opponent()
    state.turn += 1
    for unit in state.get_board_units_by_owner(state.active_player):
        unit.begin_new_turn()
    state.phase = Phase.START


def apply_action(
    state: GameState,
    action: Action,
    card_db: Dict[str, CardDefinition],
    rng: Optional[random.Random] = None,
    *,
    auto_run_next_start_phase: bool = True,
) -> GameState:
    rng = _rng_or_default(rng)
    next_state = state.clone_shallow()
    if next_state.is_terminal():
        return next_state
    if not is_legal_action(next_state, next_state.active_player, action, card_db=card_db):
        raise ValueError(f"Illegal action for current state: {action.to_dict()}")

    player_id = next_state.active_player
    if action.action_type == ActionType.USE_CARD:
        _resolve_use_card(next_state, player_id, action, card_db, rng)
    elif action.action_type == ActionType.MOVE_UNIT:
        _resolve_move_unit(next_state, player_id, action, card_db, rng)
    elif action.action_type == ActionType.UNIT_ATTACK:
        _resolve_unit_attack(next_state, player_id, action, card_db, rng)
    elif action.action_type == ActionType.END_TURN:
        _resolve_end_turn(next_state, card_db, rng)
        if auto_run_next_start_phase and not next_state.is_terminal():
            next_state = run_start_phase(next_state, card_db, rng)
    else:
        raise ValueError(f"Unsupported action type: {action.action_type}")

    next_state.last_action = action
    _set_terminal_if_needed(next_state)
    return next_state


def initialize_main_phase(state: GameState, card_db: Dict[str, CardDefinition], rng: Optional[random.Random] = None) -> GameState:
    return run_start_phase(state, card_db, rng)
