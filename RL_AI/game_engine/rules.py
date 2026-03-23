#합법성을 판정하는 파일
#룰 체크와 합법 행동 생성 프로토타입
#게임 상태로부터 소환/이동/공격/카드 사용 행동의 유효성을 검증하고, 보드 셀을 1A~6F 표기로 변환함
#상태를 변경하는 것이 아니라, 현재 상태에서의 유효한 수만 알려줌

from __future__ import annotations

from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
    TargetSelection,
    UnitState,
)

W1_KING = "0x01000000"
W1_BISHOP = "0x01000100"
W1_KNIGHT = "0x01000200"
W1_ROOK = "0x01000300"
W1_PAWN = "0x01000400"

W2_PRINCESS = "0x02000000"
W2_BISHOP = "0x02000100"
W2_KNIGHT = "0x02000200"
W2_ROOK = "0x02000300"
W2_PAWN = "0x02000400"

BOARD_FILES = "ABCDEF"


def pos_to_notation(pos: Position) -> str:
    if not pos.is_in_bounds():
        raise ValueError(f"Out-of-bounds position: {pos}")
    return f"{pos.row + 1}{BOARD_FILES[pos.col]}"


def notation_to_pos(text: str) -> Position:
    text = text.strip().upper()
    if len(text) < 2:
        raise ValueError(f"Invalid board notation: {text}")
    rank_part, file_part = text[:-1], text[-1]
    if file_part not in BOARD_FILES:
        raise ValueError(f"Invalid file in notation: {text}")
    row = int(rank_part) - 1
    col = BOARD_FILES.index(file_part)
    pos = Position(row, col)
    if not pos.is_in_bounds():
        raise ValueError(f"Out-of-bounds notation: {text}")
    return pos


def all_board_positions() -> List[Position]:
    return [Position(r, c) for r in range(BOARD_ROWS) for c in range(BOARD_COLS)]


def get_home_positions(owner: PlayerID) -> List[Position]:
    row = 0 if owner == PlayerID.P1 else BOARD_ROWS - 1
    return [Position(row, c) for c in range(BOARD_COLS)]


def _far_row_for(owner: PlayerID) -> int:
    return BOARD_ROWS - 1 if owner == PlayerID.P1 else 0


def delta(a: Position, b: Position) -> Tuple[int, int]:
    return b.row - a.row, b.col - a.col


def same_row(a: Position, b: Position) -> bool:
    return a.row == b.row


def same_col(a: Position, b: Position) -> bool:
    return a.col == b.col


def same_diag(a: Position, b: Position) -> bool:
    return abs(a.row - b.row) == abs(a.col - b.col)


def step_toward(src: Position, dst: Position) -> Tuple[int, int]:
    dr = dst.row - src.row
    dc = dst.col - src.col
    return 0 if dr == 0 else (1 if dr > 0 else -1), 0 if dc == 0 else (1 if dc > 0 else -1)


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


def _dedupe_keep_order(items: Sequence[str]) -> Tuple[str, ...]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def get_card_in_hand(state: GameState, player_id: PlayerID, card_instance_id: str):
    player = state.get_player(player_id)
    for card in player.hand:
        if card.instance_id == card_instance_id:
            return card
    return None


def get_unit_for_card_instance(state: GameState, owner: PlayerID, card_instance_id: str) -> Optional[UnitState]:
    for unit in state.units.values():
        if unit.owner == owner and unit.source_card_instance_id == card_instance_id:
            return unit
    return None


def get_ally_units_on_board(state: GameState, owner: PlayerID) -> List[UnitState]:
    return state.get_board_units_by_owner(owner)


def get_enemy_units_on_board(state: GameState, owner: PlayerID) -> List[UnitState]:
    return state.get_board_units_by_owner(owner.opponent())


def _resolve_target_units(state: GameState, player_id: PlayerID, action: Action) -> List[UnitState]:
    if action.target_selection == TargetSelection.NONE:
        ids: Tuple[str, ...] = ()
    elif action.target_selection == TargetSelection.EXPLICIT:
        ids = _dedupe_keep_order(action.target_unit_ids)
    elif action.target_selection == TargetSelection.ALL_ENEMIES:
        ids = tuple(u.unit_id for u in get_enemy_units_on_board(state, player_id))
    elif action.target_selection == TargetSelection.ALL_ALLIES:
        ids = tuple(u.unit_id for u in get_ally_units_on_board(state, player_id))
    elif action.target_selection == TargetSelection.ALL_UNITS:
        ids = tuple(u.unit_id for u in state.get_board_units())
    else:
        ids = ()
    return [state.get_unit(uid) for uid in ids]


def is_main_phase_for_active_player(state: GameState) -> bool:
    return state.phase == Phase.MAIN and not state.is_terminal()


def can_player_act(state: GameState, player_id: PlayerID) -> bool:
    return not state.is_terminal() and state.active_player == player_id and state.phase == Phase.MAIN


def can_summon_card_to(state: GameState, player_id: PlayerID, card_instance_id: str, target_pos: Position) -> bool:
    if not can_player_act(state, player_id):
        return False
    card = get_card_in_hand(state, player_id, card_instance_id)
    if card is None or not target_pos.is_in_bounds():
        return False
    if target_pos.row != (0 if player_id == PlayerID.P1 else BOARD_ROWS - 1):
        return False
    if not state.is_empty(target_pos):
        return False
    if state.unit_exists_for_card(player_id, card.card_id):
        return False
    unit = get_unit_for_card_instance(state, player_id, card_instance_id)
    return unit is not None and not unit.is_on_board and not unit.retired


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
    return (unit.promoted and unit.role == Role.PAWN) or unit.role in {Role.ROOK, Role.BISHOP}


def is_position_in_unit_move_range(state: GameState, unit: UnitState, target_pos: Position, require_empty: bool = True) -> bool:
    if unit.position is None or not target_pos.is_in_bounds():
        return False
    if require_empty and not state.is_empty(target_pos):
        return False
    if not is_valid_basic_move_shape(unit, unit.position, target_pos):
        return False
    if requires_clear_path_for_move(unit) and not is_path_clear(state, unit.position, target_pos):
        return False
    return True


def can_move_unit(state: GameState, player_id: PlayerID, unit_id: str, target_pos: Position) -> bool:
    if not can_player_act(state, player_id):
        return False
    unit = state.get_unit(unit_id)
    if unit.owner != player_id or not unit.can_move() or unit.position is None:
        return False
    return is_position_in_unit_move_range(state, unit, target_pos, require_empty=True)


def get_legal_move_positions(state: GameState, player_id: PlayerID, unit_id: str) -> List[Position]:
    unit = state.get_unit(unit_id)
    if unit.owner != player_id or unit.position is None:
        return []
    return [pos for pos in all_board_positions() if can_move_unit(state, player_id, unit_id, pos)]


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
    return (attacker.promoted and attacker.role == Role.PAWN) or attacker.role in {Role.ROOK, Role.BISHOP}


def can_unit_attack_target_by_effect(state: GameState, attacker: UnitState, defender: UnitState) -> bool:
    if not attacker.is_alive() or not defender.is_alive() or attacker.position is None or defender.position is None:
        return False
    if attacker.owner == defender.owner:
        return False
    if not is_valid_basic_attack_shape(attacker, attacker.position, defender.position):
        return False
    if requires_clear_path_for_attack(attacker) and not is_path_clear(state, attacker.position, defender.position):
        return False
    return True


def can_attack_unit(state: GameState, player_id: PlayerID, attacker_unit_id: str, defender_unit_id: str) -> bool:
    if not can_player_act(state, player_id):
        return False
    attacker = state.get_unit(attacker_unit_id)
    defender = state.get_unit(defender_unit_id)
    if attacker.owner != player_id or defender.owner == player_id or not attacker.can_attack():
        return False
    return can_unit_attack_target_by_effect(state, attacker, defender)


def get_legal_attack_targets(state: GameState, player_id: PlayerID, attacker_unit_id: str) -> List[str]:
    return [e.unit_id for e in get_enemy_units_on_board(state, player_id) if can_attack_unit(state, player_id, attacker_unit_id, e.unit_id)]


def _action_targets_match_card_effect(
    state: GameState,
    player_id: PlayerID,
    card_id: str,
    source_unit: UnitState,
    action: Action,
) -> bool:
    targets = _resolve_target_units(state, player_id, action)
    positions = list(action.target_positions)

    if card_id == W1_KING:
        if action.source_unit_id is not None:
            return False
        if len(targets) != 1 or len(positions) != 1:
            return False
        ally = targets[0]
        return ally.owner == player_id and ally.is_alive() and can_move_unit(state, player_id, ally.unit_id, positions[0])

    if card_id == W1_BISHOP:
        if len(positions) != 0:
            return False
        if not (1 <= len(targets) <= 2):
            return False
        return all(t.owner != player_id and t.is_alive() and can_unit_attack_target_by_effect(state, source_unit, t) for t in targets)

    if card_id == W1_KNIGHT:
        return len(targets) == 1 and len(positions) == 0 and targets[0].owner != player_id and can_unit_attack_target_by_effect(state, source_unit, targets[0])

    if card_id == W1_ROOK:
        return len(targets) == 1 and len(positions) == 0 and targets[0].owner == player_id and targets[0].is_alive()

    if card_id == W1_PAWN:
        if len(positions) != 0 or len(targets) != 2:
            return False
        allies = [u for u in targets if u.owner == player_id]
        enemies = [u for u in targets if u.owner != player_id]
        return len(allies) == 1 and len(enemies) == 1 and allies[0].is_alive() and enemies[0].is_alive() and can_unit_attack_target_by_effect(state, allies[0], enemies[0])

    if card_id == W2_PRINCESS:
        return len(targets) == 1 and len(positions) == 0 and targets[0].owner == player_id and targets[0].is_alive()

    if card_id == W2_BISHOP:
        leader = state.get_leader_unit(player_id)
        return leader is not None and len(targets) == 0 and len(positions) == 1 and is_position_in_unit_move_range(state, source_unit, positions[0], require_empty=True)

    if card_id == W2_KNIGHT:
        return len(targets) == 1 and len(positions) == 0 and targets[0].owner != player_id and can_unit_attack_target_by_effect(state, source_unit, targets[0])

    if card_id == W2_ROOK:
        return (not source_unit.moved_this_turn) and len(targets) == 1 and len(positions) == 0 and targets[0].owner != player_id and targets[0].is_alive()

    if card_id == W2_PAWN:
        if len(positions) != 0 or len(targets) != 2:
            return False
        allies = [u for u in targets if u.owner == player_id]
        enemies = [u for u in targets if u.owner != player_id]
        return len(allies) == 1 and len(enemies) == 1 and allies[0].is_alive() and enemies[0].is_alive() and can_unit_attack_target_by_effect(state, allies[0], enemies[0])

    return False


def can_use_card(
    state: GameState,
    player_id: PlayerID,
    card_instance_id: str,
    card_db: Dict[str, CardDefinition],
    *,
    action: Optional[Action] = None,
) -> bool:
    if not can_player_act(state, player_id):
        return False
    card = get_card_in_hand(state, player_id, card_instance_id)
    if card is None or card.card_id not in card_db:
        return False
    source_unit = get_unit_for_card_instance(state, player_id, card_instance_id)
    if source_unit is None:
        return False

    if not state.unit_exists_for_card(player_id, card.card_id):
        if action is None or len(action.target_positions) != 1 or action.target_selection != TargetSelection.EXPLICIT:
            return False
        return can_summon_card_to(state, player_id, card_instance_id, action.target_positions[0])

    if not source_unit.is_alive() or action is None:
        return False
    return _action_targets_match_card_effect(state, player_id, card.card_id, source_unit, action)


def can_end_turn(state: GameState, player_id: PlayerID) -> bool:
    return can_player_act(state, player_id)


def is_legal_action(
    state: GameState,
    player_id: PlayerID,
    action: Action,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> bool:
    if action.action_type == ActionType.END_TURN:
        return can_end_turn(state, player_id)
    if action.action_type == ActionType.MOVE_UNIT:
        return action.source_unit_id is not None and action.target_pos is not None and can_move_unit(state, player_id, action.source_unit_id, action.target_pos)
    if action.action_type == ActionType.UNIT_ATTACK:
        return action.source_unit_id is not None and action.target_unit_id is not None and can_attack_unit(state, player_id, action.source_unit_id, action.target_unit_id)
    if action.action_type == ActionType.USE_CARD:
        return card_db is not None and action.card_instance_id is not None and can_use_card(state, player_id, action.card_instance_id, card_db, action=action)
    return False


def _explicit_card_action(card_instance_id: str, target_unit_ids: Sequence[str] = (), target_positions: Sequence[Position] = ()) -> Action:
    return Action(
        action_type=ActionType.USE_CARD,
        card_instance_id=card_instance_id,
        target_unit_ids=tuple(target_unit_ids),
        target_positions=tuple(target_positions),
        target_selection=TargetSelection.EXPLICIT,
    )


def generate_use_card_actions(state: GameState, player_id: PlayerID, card_db: Dict[str, CardDefinition]) -> List[Action]:
    if not can_player_act(state, player_id):
        return []
    actions: List[Action] = []
    player = state.get_player(player_id)

    for card in player.hand:
        source_unit = get_unit_for_card_instance(state, player_id, card.instance_id)
        if source_unit is None:
            continue

        if not state.unit_exists_for_card(player_id, card.card_id):
            for pos in get_home_positions(player_id):
                action = _explicit_card_action(card.instance_id, target_positions=(pos,))
                if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                    actions.append(action)
            continue

        if not source_unit.is_alive():
            continue

        if card.card_id == W1_KING:
            for ally in get_ally_units_on_board(state, player_id):
                for pos in get_legal_move_positions(state, player_id, ally.unit_id):
                    action = _explicit_card_action(card.instance_id, target_unit_ids=(ally.unit_id,), target_positions=(pos,))
                    if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                        actions.append(action)

        elif card.card_id == W1_BISHOP:
            enemies = [u for u in get_enemy_units_on_board(state, player_id) if can_unit_attack_target_by_effect(state, source_unit, u)]
            for r in (1, 2):
                for combo in combinations(enemies, r):
                    action = _explicit_card_action(card.instance_id, target_unit_ids=tuple(u.unit_id for u in combo))
                    if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                        actions.append(action)

        elif card.card_id == W1_KNIGHT:
            for enemy in get_enemy_units_on_board(state, player_id):
                action = _explicit_card_action(card.instance_id, target_unit_ids=(enemy.unit_id,))
                if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                    actions.append(action)

        elif card.card_id == W1_ROOK:
            for ally in get_ally_units_on_board(state, player_id):
                action = _explicit_card_action(card.instance_id, target_unit_ids=(ally.unit_id,))
                if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                    actions.append(action)

        elif card.card_id == W1_PAWN:
            for ally in get_ally_units_on_board(state, player_id):
                for enemy in get_enemy_units_on_board(state, player_id):
                    action = _explicit_card_action(card.instance_id, target_unit_ids=(ally.unit_id, enemy.unit_id))
                    if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                        actions.append(action)

        elif card.card_id == W2_PRINCESS:
            for ally in get_ally_units_on_board(state, player_id):
                action = _explicit_card_action(card.instance_id, target_unit_ids=(ally.unit_id,))
                if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                    actions.append(action)

        elif card.card_id == W2_BISHOP:
            for pos in all_board_positions():
                action = _explicit_card_action(card.instance_id, target_positions=(pos,))
                if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                    actions.append(action)

        elif card.card_id == W2_KNIGHT:
            for enemy in get_enemy_units_on_board(state, player_id):
                action = _explicit_card_action(card.instance_id, target_unit_ids=(enemy.unit_id,))
                if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                    actions.append(action)

        elif card.card_id == W2_ROOK:
            for enemy in get_enemy_units_on_board(state, player_id):
                action = _explicit_card_action(card.instance_id, target_unit_ids=(enemy.unit_id,))
                if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                    actions.append(action)

        elif card.card_id == W2_PAWN:
            for ally in get_ally_units_on_board(state, player_id):
                for enemy in get_enemy_units_on_board(state, player_id):
                    action = _explicit_card_action(card.instance_id, target_unit_ids=(ally.unit_id, enemy.unit_id))
                    if can_use_card(state, player_id, card.instance_id, card_db, action=action):
                        actions.append(action)

    return actions


def generate_move_actions(state: GameState, player_id: PlayerID) -> List[Action]:
    if not can_player_act(state, player_id):
        return []
    actions: List[Action] = []
    for unit in get_ally_units_on_board(state, player_id):
        for pos in get_legal_move_positions(state, player_id, unit.unit_id):
            actions.append(Action(action_type=ActionType.MOVE_UNIT, source_unit_id=unit.unit_id, target_positions=(pos,), target_selection=TargetSelection.EXPLICIT))
    return actions


def generate_attack_actions(state: GameState, player_id: PlayerID) -> List[Action]:
    if not can_player_act(state, player_id):
        return []
    actions: List[Action] = []
    for unit in get_ally_units_on_board(state, player_id):
        if not unit.can_attack():
            continue
        for target_unit_id in get_legal_attack_targets(state, player_id, unit.unit_id):
            actions.append(Action(action_type=ActionType.UNIT_ATTACK, source_unit_id=unit.unit_id, target_unit_ids=(target_unit_id,), target_selection=TargetSelection.EXPLICIT))
    return actions


def generate_end_turn_action(state: GameState, player_id: PlayerID) -> List[Action]:
    return [Action(action_type=ActionType.END_TURN)] if can_end_turn(state, player_id) else []


def get_legal_actions(state: GameState, player_id: Optional[PlayerID] = None, card_db: Optional[Dict[str, CardDefinition]] = None) -> List[Action]:
    pid = state.active_player if player_id is None else player_id
    actions: List[Action] = []
    if card_db is not None:
        actions.extend(generate_use_card_actions(state, pid, card_db))
    actions.extend(generate_move_actions(state, pid))
    actions.extend(generate_attack_actions(state, pid))
    actions.extend(generate_end_turn_action(state, pid))
    return actions


def _find_unit_for_card_instance(state: GameState, card_instance_id: str) -> Optional[UnitState]:
    for unit in state.all_units():
        if unit.source_card_instance_id == card_instance_id:
            return unit
    return None


def describe_action(state: GameState, action: Action) -> str:
    if action.action_type == ActionType.END_TURN:
        return "턴 종료"

    if action.action_type == ActionType.MOVE_UNIT:
        unit = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        dst = pos_to_notation(action.target_pos) if action.target_pos else "?"
        return f"{unit.name if unit else '?'} 유닛 이동 → {dst}"

    if action.action_type == ActionType.UNIT_ATTACK:
        src = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        targets = [state.get_unit(uid).name for uid in action.target_unit_ids]
        return f"{src.name if src else '?'} 유닛으로 {', '.join(targets)} 공격"

    if action.action_type == ActionType.USE_CARD:
        source_unit = _find_unit_for_card_instance(state, action.card_instance_id) if action.card_instance_id else None
        card_name = source_unit.name if source_unit is not None else (action.card_instance_id[:8] if action.card_instance_id else '?')
        target_units = [state.get_unit(uid) for uid in action.target_unit_ids]
        positions = [pos_to_notation(p) for p in action.target_positions]

        if source_unit is not None and not source_unit.is_alive() and len(positions) == 1:
            return f"{card_name} 카드 소환 → {positions[0]}"

        if source_unit is not None and source_unit.source_card_id == W1_KING and len(target_units) == 1 and len(positions) == 1:
            return f"{card_name} 카드 사용 → {target_units[0].name} 유닛을 {positions[0]}로 이동"

        if source_unit is not None and source_unit.source_card_id in {W1_BISHOP, W1_KNIGHT, W2_KNIGHT, W2_ROOK} and target_units:
            return f"{card_name} 카드 사용 → {', '.join(u.name for u in target_units)} 공격"

        if source_unit is not None and source_unit.source_card_id == W1_ROOK and len(target_units) == 1:
            return f"{card_name} 카드 사용 → {target_units[0].name} 체력 전부 회복"

        if source_unit is not None and source_unit.source_card_id in {W1_PAWN, W2_PAWN} and len(target_units) == 2:
            allies = [u for u in target_units if u.owner == state.active_player]
            enemies = [u for u in target_units if u.owner != state.active_player]
            if len(allies) == 1 and len(enemies) == 1:
                return f"{card_name} 카드 사용 → {allies[0].name} 유닛으로 {enemies[0].name}를 지정해 공격"

        if source_unit is not None and source_unit.source_card_id == W2_PRINCESS and len(target_units) == 1:
            return f"{card_name} 카드 사용 → {target_units[0].name} 회복"

        if source_unit is not None and source_unit.source_card_id == W2_BISHOP and len(positions) == 1:
            return f"{card_name} 카드 사용 → 군주를 {positions[0]}로 이동"

        parts = [f"{card_name} 카드 사용"]
        if target_units:
            parts.append("대상=" + ", ".join(u.name for u in target_units))
        if positions:
            parts.append("위치=" + ", ".join(positions))
        return " | ".join(parts)

    return action.action_type.value
