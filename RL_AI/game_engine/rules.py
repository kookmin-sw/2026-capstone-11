#행동이 합법인지 확인

from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

from RL_AI.cards.card_db import CardDefinition, Role
from RL_AI.game_engine.state import (
    Action,
    ActionType,
    BOARD_COLS,
    BOARD_ROWS,
    GameState,
    Phase,
    PlayerID,
    Position,
    UnitState,
)

# ============================================================
# Board notation helpers
# ============================================================

BOARD_FILES = "ABCDEF"


def pos_to_notation(pos: Position) -> str:
    if not pos.is_in_bounds():
        raise ValueError(f"Out-of-bounds position: {pos}")
    return f"{pos.row + 1}{BOARD_FILES[pos.col]}"


def notation_to_pos(text: str) -> Position:
    text = text.strip().upper()
    if len(text) < 2:
        raise ValueError(f"Invalid board notation: {text}")

    rank_part = text[:-1]
    file_part = text[-1]
    if file_part not in BOARD_FILES:
        raise ValueError(f"Invalid board notation: {text}")

    rank = int(rank_part)
    pos = Position(rank - 1, BOARD_FILES.index(file_part))
    if not pos.is_in_bounds():
        raise ValueError(f"Out-of-bounds board notation: {text}")
    return pos


def all_board_positions() -> List[Position]:
    return [Position(r, c) for r in range(BOARD_ROWS) for c in range(BOARD_COLS)]


def is_home_row(owner: PlayerID, pos: Position) -> bool:
    return pos.row == (0 if owner == PlayerID.P1 else BOARD_ROWS - 1)


def get_home_positions(owner: PlayerID) -> List[Position]:
    row = 0 if owner == PlayerID.P1 else BOARD_ROWS - 1
    return [Position(row, c) for c in range(BOARD_COLS)]


# ============================================================
# Geometry helpers
# ============================================================

def delta(a: Position, b: Position) -> Tuple[int, int]:
    return (b.row - a.row, b.col - a.col)


def same_row(a: Position, b: Position) -> bool:
    return a.row == b.row


def same_col(a: Position, b: Position) -> bool:
    return a.col == b.col


def same_diag(a: Position, b: Position) -> bool:
    return abs(a.row - b.row) == abs(a.col - b.col)


def chebyshev_distance(a: Position, b: Position) -> int:
    return max(abs(a.row - b.row), abs(a.col - b.col))


def step_toward(src: Position, dst: Position) -> Tuple[int, int]:
    dr = dst.row - src.row
    dc = dst.col - src.col
    return (
        0 if dr == 0 else (1 if dr > 0 else -1),
        0 if dc == 0 else (1 if dc > 0 else -1),
    )


def squares_between(src: Position, dst: Position) -> List[Position]:
    if src == dst:
        return []
    if not (same_row(src, dst) or same_col(src, dst) or same_diag(src, dst)):
        return []

    dr, dc = step_toward(src, dst)
    out: List[Position] = []
    cur = Position(src.row + dr, src.col + dc)
    while cur != dst:
        out.append(cur)
        cur = Position(cur.row + dr, cur.col + dc)
    return out


def is_path_clear(state: GameState, src: Position, dst: Position) -> bool:
    return all(state.is_empty(p) for p in squares_between(src, dst))


# ============================================================
# Selection helpers
# ============================================================

def _unique_preserve_order(items: Sequence[str]) -> Tuple[str, ...]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def get_card_in_hand(state: GameState, player_id: PlayerID, card_instance_id: str):
    for card in state.get_player(player_id).hand:
        if card.instance_id == card_instance_id:
            return card
    return None


def get_unit_for_card_instance(
    state: GameState,
    owner: PlayerID,
    card_instance_id: str,
) -> Optional[UnitState]:
    for unit in state.units.values():
        if unit.owner == owner and unit.source_card_instance_id == card_instance_id:
            return unit
    return None


def get_ally_units_on_board(state: GameState, owner: PlayerID) -> List[UnitState]:
    return state.get_board_units_by_owner(owner)


def get_enemy_units_on_board(state: GameState, owner: PlayerID) -> List[UnitState]:
    return state.get_board_units_by_owner(owner.opponent())


# ============================================================
# Turn / phase checks
# ============================================================

def can_player_act(state: GameState, player_id: PlayerID) -> bool:
    return (
        not state.is_terminal()
        and state.active_player == player_id
        and state.phase == Phase.MAIN
    )


# ============================================================
# Summon checks
# ============================================================

def can_summon_card_to(
    state: GameState,
    player_id: PlayerID,
    card_instance_id: str,
    target_pos: Position,
) -> bool:
    if not can_player_act(state, player_id):
        return False

    card = get_card_in_hand(state, player_id, card_instance_id)
    if card is None:
        return False
    if not target_pos.is_in_bounds():
        return False
    if not is_home_row(player_id, target_pos):
        return False
    if not state.is_empty(target_pos):
        return False
    if state.unit_exists_for_card(player_id, card.card_id):
        return False

    runtime_unit = get_unit_for_card_instance(state, player_id, card_instance_id)
    if runtime_unit is None:
        return False
    if runtime_unit.is_on_board and not runtime_unit.retired:
        return False
    return True


def get_legal_summon_positions(
    state: GameState,
    player_id: PlayerID,
    card_instance_id: str,
) -> List[Position]:
    return [
        pos for pos in get_home_positions(player_id)
        if can_summon_card_to(state, player_id, card_instance_id, pos)
    ]


# ============================================================
# Move checks
# ============================================================

def _pawn_forward_delta(owner: PlayerID) -> int:
    return 1 if owner == PlayerID.P1 else -1


def is_valid_basic_move_shape(unit: UnitState, src: Position, dst: Position) -> bool:
    dr, dc = delta(src, dst)
    adr, adc = abs(dr), abs(dc)

    if src == dst:
        return False

    if unit.promoted and unit.role == Role.PAWN:
        return same_row(src, dst) or same_col(src, dst) or same_diag(src, dst)

    if unit.role == Role.LEADER:
        return max(adr, adc) == 1
    if unit.role == Role.ROOK:
        return same_row(src, dst) or same_col(src, dst)
    if unit.role == Role.BISHOP:
        return same_diag(src, dst)
    if unit.role == Role.KNIGHT:
        return (adr, adc) in {(1, 2), (2, 1)}
    if unit.role == Role.PAWN:
        return dc == 0 and dr == _pawn_forward_delta(unit.owner)
    return False


def requires_clear_path_for_move(unit: UnitState) -> bool:
    return unit.promoted and unit.role == Role.PAWN or unit.role in {Role.ROOK, Role.BISHOP}


def can_move_unit(
    state: GameState,
    player_id: PlayerID,
    unit_id: str,
    target_pos: Position,
) -> bool:
    if not can_player_act(state, player_id):
        return False
    if not target_pos.is_in_bounds():
        return False

    unit = state.get_unit(unit_id)
    if unit.owner != player_id:
        return False
    if not unit.can_move():
        return False
    if unit.position is None:
        return False
    if not state.is_empty(target_pos):
        return False
    if not is_valid_basic_move_shape(unit, unit.position, target_pos):
        return False
    if requires_clear_path_for_move(unit) and not is_path_clear(state, unit.position, target_pos):
        return False
    return True


def get_legal_move_positions(state: GameState, player_id: PlayerID, unit_id: str) -> List[Position]:
    unit = state.get_unit(unit_id)
    if unit.owner != player_id or unit.position is None:
        return []
    return [pos for pos in all_board_positions() if can_move_unit(state, player_id, unit_id, pos)]


# ============================================================
# Attack checks
# ============================================================

def is_valid_basic_attack_shape(attacker: UnitState, src: Position, dst: Position) -> bool:
    dr, dc = delta(src, dst)
    adr, adc = abs(dr), abs(dc)

    if src == dst:
        return False

    if attacker.promoted and attacker.role == Role.PAWN:
        return same_row(src, dst) or same_col(src, dst) or same_diag(src, dst)

    if attacker.role == Role.LEADER:
        return max(adr, adc) == 1
    if attacker.role == Role.ROOK:
        return same_row(src, dst) or same_col(src, dst)
    if attacker.role == Role.BISHOP:
        return same_diag(src, dst)
    if attacker.role == Role.KNIGHT:
        return (adr, adc) in {(1, 2), (2, 1)}
    if attacker.role == Role.PAWN:
        return dr == _pawn_forward_delta(attacker.owner) and abs(dc) == 1
    return False


def requires_clear_path_for_attack(attacker: UnitState) -> bool:
    return attacker.promoted and attacker.role == Role.PAWN or attacker.role in {Role.ROOK, Role.BISHOP}


def can_attack_unit(
    state: GameState,
    player_id: PlayerID,
    attacker_unit_id: str,
    defender_unit_id: str,
) -> bool:
    if not can_player_act(state, player_id):
        return False

    attacker = state.get_unit(attacker_unit_id)
    defender = state.get_unit(defender_unit_id)

    if attacker.owner != player_id:
        return False
    if defender.owner == player_id:
        return False
    if not attacker.can_attack():
        return False
    if not defender.is_alive():
        return False
    if attacker.position is None or defender.position is None:
        return False
    if not is_valid_basic_attack_shape(attacker, attacker.position, defender.position):
        return False
    if requires_clear_path_for_attack(attacker) and not is_path_clear(state, attacker.position, defender.position):
        return False
    return True


def get_legal_attack_targets(
    state: GameState,
    player_id: PlayerID,
    attacker_unit_id: str,
) -> List[str]:
    return [
        enemy.unit_id
        for enemy in get_enemy_units_on_board(state, player_id)
        if can_attack_unit(state, player_id, attacker_unit_id, enemy.unit_id)
    ]


# ============================================================
# Card effect target validation
# ============================================================

def _validate_no_explicit_targets(target_unit_ids: Tuple[str, ...], target_positions: Tuple[Position, ...]) -> bool:
    return len(target_unit_ids) == 0 and len(target_positions) == 0


def _validate_single_board_cell(target_unit_ids: Tuple[str, ...], target_positions: Tuple[Position, ...]) -> bool:
    return len(target_unit_ids) == 0 and len(target_positions) == 1 and target_positions[0].is_in_bounds()


def _validate_exactly_one_unit(
    state: GameState,
    target_unit_ids: Tuple[str, ...],
    owner_predicate,
) -> bool:
    if len(target_unit_ids) != 1:
        return False
    unit = state.get_unit(target_unit_ids[0])
    return unit.is_alive() and owner_predicate(unit)


def _validate_up_to_two_enemy_units(
    state: GameState,
    player_id: PlayerID,
    target_unit_ids: Tuple[str, ...],
) -> bool:
    target_unit_ids = _unique_preserve_order(target_unit_ids)
    if len(target_unit_ids) not in {1, 2}:
        return False
    for unit_id in target_unit_ids:
        unit = state.get_unit(unit_id)
        if not unit.is_alive() or unit.owner == player_id:
            return False
    return True


def _validate_same_row_target(
    state: GameState,
    source_unit: UnitState,
    target_unit_ids: Tuple[str, ...],
) -> bool:
    if source_unit.position is None or len(target_unit_ids) != 1:
        return False
    target = state.get_unit(target_unit_ids[0])
    return target.is_alive() and target.position is not None and same_row(source_unit.position, target.position)


def validate_effect_target_by_schema(
    state: GameState,
    player_id: PlayerID,
    source_unit: UnitState,
    card_def: CardDefinition,
    target_unit_ids: Sequence[str] = (),
    target_positions: Sequence[Position] = (),
) -> bool:
    schema = card_def.effect_target_schema
    target_unit_ids = tuple(target_unit_ids)
    target_positions = tuple(target_positions)

    if schema == "none":
        return _validate_no_explicit_targets(target_unit_ids, target_positions)

    if schema == "board_cell":
        return _validate_single_board_cell(target_unit_ids, target_positions)

    if schema == "ally_unit":
        return _validate_exactly_one_unit(
            state,
            target_unit_ids,
            owner_predicate=lambda u: u.owner == player_id,
        ) and len(target_positions) == 0

    if schema == "ally_nonleader_unit":
        return _validate_exactly_one_unit(
            state,
            target_unit_ids,
            owner_predicate=lambda u: u.owner == player_id and u.role != Role.LEADER,
        ) and len(target_positions) == 0

    if schema == "enemy_unit":
        return _validate_exactly_one_unit(
            state,
            target_unit_ids,
            owner_predicate=lambda u: u.owner != player_id,
        ) and len(target_positions) == 0

    if schema == "same_row":
        return len(target_positions) == 0 and _validate_same_row_target(state, source_unit, target_unit_ids)

    if schema == "enemy_units_up_to_two":
        return len(target_positions) == 0 and _validate_up_to_two_enemy_units(state, player_id, target_unit_ids)

    if schema == "all_units":
        # Explicit selection is unnecessary; engine can derive targets from schema.
        return _validate_no_explicit_targets(target_unit_ids, target_positions)

    if schema == "implicit_or_custom":
        return False

    return False


# ============================================================
# USE_CARD legality
# ============================================================

def can_use_card(
    state: GameState,
    player_id: PlayerID,
    card_instance_id: str,
    card_db: Dict[str, CardDefinition],
    target_unit_ids: Sequence[str] = (),
    target_positions: Sequence[Position] = (),
) -> bool:
    if not can_player_act(state, player_id):
        return False

    card = get_card_in_hand(state, player_id, card_instance_id)
    if card is None or card.card_id not in card_db:
        return False

    card_def = card_db[card.card_id]
    source_unit = get_unit_for_card_instance(state, player_id, card_instance_id)
    if source_unit is None:
        return False

    target_unit_ids = tuple(target_unit_ids)
    target_positions = tuple(target_positions)

    # summon mode
    if not state.unit_exists_for_card(player_id, card.card_id):
        return (
            len(target_unit_ids) == 0
            and len(target_positions) == 1
            and can_summon_card_to(state, player_id, card_instance_id, target_positions[0])
        )

    # effect mode
    if not source_unit.is_alive():
        return False

    return validate_effect_target_by_schema(
        state=state,
        player_id=player_id,
        source_unit=source_unit,
        card_def=card_def,
        target_unit_ids=target_unit_ids,
        target_positions=target_positions,
    )


# ============================================================
# END_TURN legality
# ============================================================

def can_end_turn(state: GameState, player_id: PlayerID) -> bool:
    return can_player_act(state, player_id)


# ============================================================
# Generic action legality
# ============================================================

def is_legal_action(
    state: GameState,
    player_id: PlayerID,
    action: Action,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> bool:
    if action.action_type == ActionType.END_TURN:
        return can_end_turn(state, player_id)

    if action.action_type == ActionType.MOVE_UNIT:
        return (
            action.source_unit_id is not None
            and len(action.target_positions) == 1
            and can_move_unit(state, player_id, action.source_unit_id, action.target_positions[0])
        )

    if action.action_type == ActionType.UNIT_ATTACK:
        return (
            action.source_unit_id is not None
            and len(action.target_unit_ids) == 1
            and can_attack_unit(state, player_id, action.source_unit_id, action.target_unit_ids[0])
        )

    if action.action_type == ActionType.USE_CARD:
        return (
            card_db is not None
            and action.card_instance_id is not None
            and can_use_card(
                state=state,
                player_id=player_id,
                card_instance_id=action.card_instance_id,
                card_db=card_db,
                target_unit_ids=action.target_unit_ids,
                target_positions=action.target_positions,
            )
        )

    return False


# ============================================================
# Legal action generation
# ============================================================

def _make_use_card_action(
    card_instance_id: str,
    target_unit_ids: Sequence[str] = (),
    target_positions: Sequence[Position] = (),
) -> Action:
    return Action(
        action_type=ActionType.USE_CARD,
        card_instance_id=card_instance_id,
        target_unit_ids=tuple(target_unit_ids),
        target_positions=tuple(target_positions),
    )


def generate_use_card_actions(
    state: GameState,
    player_id: PlayerID,
    card_db: Dict[str, CardDefinition],
) -> List[Action]:
    if not can_player_act(state, player_id):
        return []

    actions: List[Action] = []
    player = state.get_player(player_id)

    for card in player.hand:
        if card.card_id not in card_db:
            continue

        card_def = card_db[card.card_id]
        runtime_unit = get_unit_for_card_instance(state, player_id, card.instance_id)
        if runtime_unit is None:
            continue

        # summon
        if not state.unit_exists_for_card(player_id, card.card_id):
            for pos in get_legal_summon_positions(state, player_id, card.instance_id):
                actions.append(_make_use_card_action(card.instance_id, target_positions=(pos,)))
            continue

        # effect
        if not runtime_unit.is_alive():
            continue

        schema = card_def.effect_target_schema

        if schema in {"none", "all_units"}:
            action = _make_use_card_action(card.instance_id)
            if is_legal_action(state, player_id, action, card_db):
                actions.append(action)

        elif schema == "board_cell":
            for pos in all_board_positions():
                action = _make_use_card_action(card.instance_id, target_positions=(pos,))
                if is_legal_action(state, player_id, action, card_db):
                    actions.append(action)

        elif schema in {"ally_unit", "ally_nonleader_unit", "enemy_unit", "same_row"}:
            for unit in state.get_board_units():
                action = _make_use_card_action(card.instance_id, target_unit_ids=(unit.unit_id,))
                if is_legal_action(state, player_id, action, card_db):
                    actions.append(action)

        elif schema == "enemy_units_up_to_two":
            enemy_ids = [u.unit_id for u in get_enemy_units_on_board(state, player_id)]
            for n in (1, 2):
                for combo in combinations(enemy_ids, n):
                    action = _make_use_card_action(card.instance_id, target_unit_ids=combo)
                    if is_legal_action(state, player_id, action, card_db):
                        actions.append(action)

        else:
            continue

    return actions


def generate_move_actions(state: GameState, player_id: PlayerID) -> List[Action]:
    if not can_player_act(state, player_id):
        return []

    actions: List[Action] = []
    for unit in get_ally_units_on_board(state, player_id):
        if not unit.can_move():
            continue
        for pos in get_legal_move_positions(state, player_id, unit.unit_id):
            actions.append(
                Action(
                    action_type=ActionType.MOVE_UNIT,
                    source_unit_id=unit.unit_id,
                    target_positions=(pos,),
                )
            )
    return actions


def generate_attack_actions(state: GameState, player_id: PlayerID) -> List[Action]:
    if not can_player_act(state, player_id):
        return []

    actions: List[Action] = []
    for unit in get_ally_units_on_board(state, player_id):
        if not unit.can_attack():
            continue
        for target_unit_id in get_legal_attack_targets(state, player_id, unit.unit_id):
            actions.append(
                Action(
                    action_type=ActionType.UNIT_ATTACK,
                    source_unit_id=unit.unit_id,
                    target_unit_ids=(target_unit_id,),
                )
            )
    return actions


def generate_end_turn_action(state: GameState, player_id: PlayerID) -> List[Action]:
    return [Action(action_type=ActionType.END_TURN)] if can_end_turn(state, player_id) else []


def get_legal_actions(
    state: GameState,
    player_id: Optional[PlayerID] = None,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> List[Action]:
    pid = state.active_player if player_id is None else player_id

    actions: List[Action] = []
    if card_db is not None:
        actions.extend(generate_use_card_actions(state, pid, card_db))
    actions.extend(generate_move_actions(state, pid))
    actions.extend(generate_attack_actions(state, pid))
    actions.extend(generate_end_turn_action(state, pid))
    return actions


# ============================================================
# Debug helpers
# ============================================================

def describe_action(state: GameState, action: Action) -> str:
    if action.action_type == ActionType.END_TURN:
        return "END_TURN"

    if action.action_type == ActionType.MOVE_UNIT:
        unit = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        dst = pos_to_notation(action.target_positions[0]) if len(action.target_positions) == 1 else "?"
        return f"MOVE_UNIT {unit.name if unit else '?'} -> {dst}"

    if action.action_type == ActionType.UNIT_ATTACK:
        src = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        dst_names = [state.get_unit(uid).name for uid in action.target_unit_ids]
        return f"UNIT_ATTACK {src.name if src else '?'} -> {', '.join(dst_names)}"

    if action.action_type == ActionType.USE_CARD:
        parts = [f"USE_CARD {action.card_instance_id}"]
        if action.target_positions:
            parts.append("@ " + ", ".join(pos_to_notation(pos) for pos in action.target_positions))
        if action.target_unit_ids:
            parts.append("-> " + ", ".join(state.get_unit(uid).name for uid in action.target_unit_ids))
        return " ".join(parts)

    return action.action_type.value
