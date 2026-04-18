#합법성을 판정하는 파일
#룰 체크와 합법 행동 생성 프로토타입
#게임 상태로부터 소환/이동/공격/카드 사용 행동의 유효성을 검증하고, 보드 셀을 1A~6F 표기로 변환함
#상태를 변경하는 것이 아니라, 현재 상태에서의 유효한 수만 알려줌
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
    TargetSelection,
    UnitState,
)

OR_LEADER = "Or_L"
OR_BISHOP = "Or_B"
OR_KNIGHT = "Or_N"
OR_ROOK = "Or_R"
OR_PAWN = "Or_P"

CL_LEADER = "Cl_L"
CL_BISHOP = "Cl_B"
CL_KNIGHT = "Cl_N"
CL_ROOK = "Cl_R"
CL_PAWN = "Cl_P"

BOARD_FILES = "ABCDEF"


def pos_to_notation(pos: Position) -> str:
    if not pos.is_in_bounds():
        raise ValueError(f"Out-of-bounds position: {pos}")
    return f"{pos.row + 1}{BOARD_FILES[pos.col]}"


def notation_to_pos(text: str) -> Position:
    text = text.strip().upper()
    if len(text) < 2:
        raise ValueError(f"Invalid notation: {text}")
    rank = int(text[:-1])
    file_char = text[-1]
    if file_char not in BOARD_FILES:
        raise ValueError(f"Invalid notation: {text}")
    pos = Position(rank - 1, BOARD_FILES.index(file_char))
    if not pos.is_in_bounds():
        raise ValueError(f"Out-of-bounds notation: {text}")
    return pos


def all_board_positions() -> List[Position]:
    return [Position(r, c) for r in range(BOARD_ROWS) for c in range(BOARD_COLS)]


def _active_main(state: GameState, player_id: PlayerID) -> bool:
    return not state.is_terminal() and state.phase == Phase.MAIN and state.active_player == player_id


def _home_row(owner: PlayerID) -> int:
    return 0 if owner == PlayerID.P1 else BOARD_ROWS - 1


def _forward(owner: PlayerID) -> int:
    return 1 if owner == PlayerID.P1 else -1


def _same_row(a: Position, b: Position) -> bool:
    return a.row == b.row


def _same_col(a: Position, b: Position) -> bool:
    return a.col == b.col


def _same_diag(a: Position, b: Position) -> bool:
    return abs(a.row - b.row) == abs(a.col - b.col)


def _step(src: Position, dst: Position) -> Tuple[int, int]:
    dr = dst.row - src.row
    dc = dst.col - src.col
    return (
        0 if dr == 0 else (1 if dr > 0 else -1),
        0 if dc == 0 else (1 if dc > 0 else -1),
    )


def _path_between(src: Position, dst: Position) -> List[Position]:
    if src == dst or not (_same_row(src, dst) or _same_col(src, dst) or _same_diag(src, dst)):
        return []
    dr, dc = _step(src, dst)
    cur = Position(src.row + dr, src.col + dc)
    out: List[Position] = []
    while cur != dst:
        out.append(cur)
        cur = Position(cur.row + dr, cur.col + dc)
    return out


def _path_clear(state: GameState, src: Position, dst: Position) -> bool:
    return all(state.is_empty(p) for p in _path_between(src, dst))


def get_ally_units_on_board(state: GameState, owner: PlayerID) -> List[UnitState]:
    return state.get_board_units_by_owner(owner)


def get_enemy_units_on_board(state: GameState, owner: PlayerID) -> List[UnitState]:
    return state.get_board_units_by_owner(owner.opponent())


def _runtime_unit_for_card_instance(state: GameState, owner: PlayerID, card_instance_id: str) -> Optional[UnitState]:
    for unit in state.units.values():
        if unit.owner == owner and unit.source_card_instance_id == card_instance_id:
            return unit
    return None


def _is_runtime_unit_on_board_for_card_instance(state: GameState, owner: PlayerID, card_instance_id: str) -> bool:
    unit = _runtime_unit_for_card_instance(state, owner, card_instance_id)
    return unit is not None and unit.is_alive()


def _card_in_hand(state: GameState, owner: PlayerID, card_instance_id: str):
    for card in state.get_player(owner).hand:
        if card.instance_id == card_instance_id:
            return card
    return None


def is_position_in_unit_move_range(
    state: GameState,
    unit: UnitState,
    dst: Position,
    *,
    require_empty: bool = True,
) -> bool:
    if unit.position is None or not dst.is_in_bounds() or unit.position == dst:
        return False
    if require_empty and not state.is_empty(dst):
        return False

    src = unit.position
    dr = dst.row - src.row
    dc = dst.col - src.col
    adr, adc = abs(dr), abs(dc)

    if unit.promoted and unit.role == Role.PAWN:
        ok = _same_row(src, dst) or _same_col(src, dst) or _same_diag(src, dst)
        return ok and _path_clear(state, src, dst)

    if unit.role == Role.LEADER:
        return max(adr, adc) == 1
    if unit.role == Role.ROOK:
        return (_same_row(src, dst) or _same_col(src, dst)) and _path_clear(state, src, dst)
    if unit.role == Role.BISHOP:
        return _same_diag(src, dst) and _path_clear(state, src, dst)
    if unit.role == Role.KNIGHT:
        return (adr, adc) in {(1, 2), (2, 1)}
    if unit.role == Role.PAWN:
        return dc == 0 and dr == _forward(unit.owner)
    return False


def can_move_unit(state: GameState, player_id: PlayerID, unit_id: str, target_pos: Position) -> bool:
    if not _active_main(state, player_id):
        return False
    unit = state.get_unit(unit_id)
    return (
        unit.owner == player_id
        and unit.can_move()
        and is_position_in_unit_move_range(state, unit, target_pos, require_empty=True)
    )


def get_legal_move_positions(state: GameState, player_id: PlayerID, unit_id: str) -> List[Position]:
    return [p for p in all_board_positions() if can_move_unit(state, player_id, unit_id, p)]


def _attack_shape(attacker: UnitState, dst: Position):
    assert attacker.position is not None
    src = attacker.position
    dr = dst.row - src.row
    dc = dst.col - src.col
    adr, adc = abs(dr), abs(dc)
    if src == dst:
        return False
    if attacker.promoted and attacker.role == Role.PAWN:
        return "_queen_path"
    if attacker.role == Role.LEADER:
        return max(adr, adc) == 1
    if attacker.role == Role.ROOK:
        return _same_row(src, dst) or _same_col(src, dst)
    if attacker.role == Role.BISHOP:
        return _same_diag(src, dst)
    if attacker.role == Role.KNIGHT:
        return (adr, adc) in {(1, 2), (2, 1)}
    if attacker.role == Role.PAWN:
        return dr == _forward(attacker.owner) and abs(dc) == 1
    return False


def can_unit_attack_target_by_effect(state: GameState, attacker: UnitState, defender: UnitState) -> bool:
    if not attacker.is_alive() or not defender.is_alive() or attacker.owner == defender.owner:
        return False
    if attacker.position is None or defender.position is None:
        return False
    shape = _attack_shape(attacker, defender.position)
    if shape is False:
        return False
    if shape == "_queen_path":
        return _path_clear(state, attacker.position, defender.position)
    if attacker.role in {Role.ROOK, Role.BISHOP}:
        return _path_clear(state, attacker.position, defender.position)
    return True


def can_attack_unit(state: GameState, player_id: PlayerID, attacker_unit_id: str, defender_unit_id: str) -> bool:
    if not _active_main(state, player_id):
        return False
    attacker = state.get_unit(attacker_unit_id)
    defender = state.get_unit(defender_unit_id)
    return (
        attacker.owner == player_id
        and defender.owner != player_id
        and attacker.can_attack()
        and can_unit_attack_target_by_effect(state, attacker, defender)
    )


def _legal_summon_positions(state: GameState, owner: PlayerID, card_instance_id: str) -> List[Position]:
    if _card_in_hand(state, owner, card_instance_id) is None:
        return []
    if _is_runtime_unit_on_board_for_card_instance(state, owner, card_instance_id):
        return []
    return [Position(_home_row(owner), c) for c in range(BOARD_COLS) if state.is_empty(Position(_home_row(owner), c))]


def _resolve_selection_targets(state: GameState, owner: PlayerID, action: Action) -> List[UnitState]:
    if action.target_selection == TargetSelection.ALL_ENEMIES:
        return get_enemy_units_on_board(state, owner)
    if action.target_selection == TargetSelection.ALL_ALLIES:
        return get_ally_units_on_board(state, owner)
    if action.target_selection == TargetSelection.ALL_UNITS:
        return state.get_board_units()
    return [state.get_unit(uid) for uid in action.target_unit_ids]


def _can_use_card_effect(state: GameState, owner: PlayerID, action: Action, card_db: Dict[str, CardDefinition]) -> bool:
    assert action.card_instance_id is not None
    card = _card_in_hand(state, owner, action.card_instance_id)
    if card is None:
        return False
    unit = _runtime_unit_for_card_instance(state, owner, action.card_instance_id)
    if unit is None or not unit.is_alive():
        return False

    tu = list(action.target_unit_ids)
    tp = list(action.target_positions)

    if card.card_id == OR_LEADER:
        if len(tp) != 0 or len(tu) != 1:
            return False
        target = state.get_unit(tu[0])
        return target.owner == owner and target.is_alive()

    if card.card_id == OR_BISHOP:
        return len(tu) == 0 and len(tp) == 1 and is_position_in_unit_move_range(state, unit, tp[0], require_empty=True)

    if card.card_id == OR_KNIGHT:
        if len(tp) != 0 or len(tu) != 1:
            return False
        target = state.get_unit(tu[0])
        return target.owner != owner and target.is_alive() and can_unit_attack_target_by_effect(state, unit, target)

    if card.card_id == OR_ROOK:
        if len(tp) != 0 or len(tu) != 1 or unit.moved_this_turn:
            return False
        target = state.get_unit(tu[0])
        return target.owner != owner and target.is_alive()

    if card.card_id == OR_PAWN:
        if len(tp) != 0 or len(tu) != 2:
            return False
        units = [state.get_unit(uid) for uid in tu]
        allies = [u for u in units if u.owner == owner]
        enemies = [u for u in units if u.owner != owner]
        return len(allies) == 1 and len(enemies) == 1 and allies[0].is_alive() and enemies[0].is_alive() and can_unit_attack_target_by_effect(state, allies[0], enemies[0])

    if card.card_id == CL_LEADER:
        if len(tp) != 0 or len(tu) != 1:
            return False
        target = state.get_unit(tu[0])
        return (
            target.owner == owner
            and target.is_alive()
            and target.position is not None
            and is_position_in_unit_move_range(state, unit, target.position, require_empty=False)
        )

    if card.card_id == CL_BISHOP:
        if len(tp) != 0 or len(tu) not in {1, 2}:
            return False
        return all(
            state.get_unit(uid).owner != owner
            and state.get_unit(uid).is_alive()
            and can_unit_attack_target_by_effect(state, unit, state.get_unit(uid))
            for uid in tu
        )

    if card.card_id == CL_KNIGHT:
        if len(tp) != 0 or len(tu) != 1:
            return False
        target = state.get_unit(tu[0])
        return target.owner != owner and target.is_alive() and can_unit_attack_target_by_effect(state, unit, target)

    if card.card_id == CL_ROOK:
        if len(tp) != 0 or len(tu) != 1:
            return False
        target = state.get_unit(tu[0])
        return target.owner != owner and target.is_alive() and can_unit_attack_target_by_effect(state, unit, target)

    if card.card_id == CL_PAWN:
        if len(tp) != 0 or len(tu) != 2:
            return False
        units = [state.get_unit(uid) for uid in tu]
        allies = [u for u in units if u.owner == owner]
        enemies = [u for u in units if u.owner != owner]
        return len(allies) == 1 and len(enemies) == 1 and allies[0].is_alive() and enemies[0].is_alive() and can_unit_attack_target_by_effect(state, allies[0], enemies[0])

    return len(tu) == 0 and len(tp) == 0


def can_use_card(
    state: GameState,
    player_id: PlayerID,
    card_instance_id: str,
    card_db: Dict[str, CardDefinition],
    *,
    target_unit_ids: Sequence[str] = (),
    target_positions: Sequence[Position] = (),
    target_selection: TargetSelection = TargetSelection.NONE,
) -> bool:
    if not _active_main(state, player_id):
        return False
    card = _card_in_hand(state, player_id, card_instance_id)
    if card is None or card.card_id not in card_db:
        return False

    if not _is_runtime_unit_on_board_for_card_instance(state, player_id, card_instance_id):
        return (
            target_selection in {TargetSelection.NONE, TargetSelection.EXPLICIT}
            and len(target_unit_ids) == 0
            and len(target_positions) == 1
            and target_positions[0] in _legal_summon_positions(state, player_id, card_instance_id)
        )

    action = Action(
        action_type=ActionType.USE_CARD,
        card_instance_id=card_instance_id,
        target_unit_ids=tuple(target_unit_ids),
        target_positions=tuple(target_positions),
        target_selection=target_selection,
    )
    return _can_use_card_effect(state, player_id, action, card_db)


def can_end_turn(state: GameState, player_id: PlayerID) -> bool:
    return _active_main(state, player_id)


def is_legal_action(state: GameState, player_id: PlayerID, action: Action, card_db: Optional[Dict[str, CardDefinition]] = None) -> bool:
    if action.action_type == ActionType.END_TURN:
        return can_end_turn(state, player_id)
    if action.action_type == ActionType.MOVE_UNIT:
        return action.source_unit_id is not None and len(action.target_positions) == 1 and can_move_unit(state, player_id, action.source_unit_id, action.target_positions[0])
    if action.action_type == ActionType.UNIT_ATTACK:
        return action.source_unit_id is not None and len(action.target_unit_ids) == 1 and can_attack_unit(state, player_id, action.source_unit_id, action.target_unit_ids[0])
    if action.action_type == ActionType.USE_CARD:
        return card_db is not None and action.card_instance_id is not None and can_use_card(
            state,
            player_id,
            action.card_instance_id,
            card_db,
            target_unit_ids=action.target_unit_ids,
            target_positions=action.target_positions,
            target_selection=action.target_selection,
        )
    return False


def _generate_use_card_actions(state: GameState, owner: PlayerID, card_db: Dict[str, CardDefinition]) -> List[Action]:
    if not _active_main(state, owner):
        return []
    out: List[Action] = []
    player = state.get_player(owner)

    for card in player.hand:
        runtime_unit = _runtime_unit_for_card_instance(state, owner, card.instance_id)
        if runtime_unit is None:
            continue

        if not _is_runtime_unit_on_board_for_card_instance(state, owner, card.instance_id):
            for pos in _legal_summon_positions(state, owner, card.instance_id):
                out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_positions=(pos,)))
            continue

        if card.card_id == OR_LEADER:
            for ally in get_ally_units_on_board(state, owner):
                out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(ally.unit_id,)))
        elif card.card_id == OR_BISHOP:
            for pos in all_board_positions():
                if is_position_in_unit_move_range(state, runtime_unit, pos, require_empty=True):
                    out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_positions=(pos,)))
        elif card.card_id == OR_KNIGHT:
            for enemy in get_enemy_units_on_board(state, owner):
                if can_unit_attack_target_by_effect(state, runtime_unit, enemy):
                    out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(enemy.unit_id,)))
        elif card.card_id == OR_ROOK:
            if not runtime_unit.moved_this_turn:
                for enemy in get_enemy_units_on_board(state, owner):
                    out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(enemy.unit_id,)))
        elif card.card_id == OR_PAWN:
            for ally in get_ally_units_on_board(state, owner):
                for enemy in get_enemy_units_on_board(state, owner):
                    if can_unit_attack_target_by_effect(state, ally, enemy):
                        out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(ally.unit_id, enemy.unit_id)))
        elif card.card_id == CL_LEADER:
            for ally in get_ally_units_on_board(state, owner):
                if ally.position is not None and is_position_in_unit_move_range(state, runtime_unit, ally.position, require_empty=False):
                    out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(ally.unit_id,)))
        elif card.card_id == CL_BISHOP:
            enemies = [u.unit_id for u in get_enemy_units_on_board(state, owner) if can_unit_attack_target_by_effect(state, runtime_unit, u)]
            for uid in enemies:
                out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(uid,)))
            for pair in combinations(enemies, 2):
                out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=pair))
        elif card.card_id == CL_KNIGHT:
            for enemy in get_enemy_units_on_board(state, owner):
                if can_unit_attack_target_by_effect(state, runtime_unit, enemy):
                    out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(enemy.unit_id,)))
        elif card.card_id == CL_ROOK:
            for enemy in get_enemy_units_on_board(state, owner):
                if can_unit_attack_target_by_effect(state, runtime_unit, enemy):
                    out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(enemy.unit_id,)))
        elif card.card_id == CL_PAWN:
            for ally in get_ally_units_on_board(state, owner):
                for enemy in get_enemy_units_on_board(state, owner):
                    if can_unit_attack_target_by_effect(state, ally, enemy):
                        out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id, target_unit_ids=(ally.unit_id, enemy.unit_id)))
        else:
            out.append(Action(ActionType.USE_CARD, card_instance_id=card.instance_id))
    return out


def _generate_move_actions(state: GameState, owner: PlayerID) -> List[Action]:
    out: List[Action] = []
    for unit in get_ally_units_on_board(state, owner):
        for pos in get_legal_move_positions(state, owner, unit.unit_id):
            out.append(Action(ActionType.MOVE_UNIT, source_unit_id=unit.unit_id, target_positions=(pos,)))
    return out


def _generate_attack_actions(state: GameState, owner: PlayerID) -> List[Action]:
    out: List[Action] = []
    for unit in get_ally_units_on_board(state, owner):
        if not unit.can_attack():
            continue
        for enemy in get_enemy_units_on_board(state, owner):
            if can_attack_unit(state, owner, unit.unit_id, enemy.unit_id):
                out.append(Action(ActionType.UNIT_ATTACK, source_unit_id=unit.unit_id, target_unit_ids=(enemy.unit_id,)))
    return out


def get_legal_actions(state: GameState, player_id: Optional[PlayerID] = None, card_db: Optional[Dict[str, CardDefinition]] = None) -> List[Action]:
    owner = state.active_player if player_id is None else player_id
    out: List[Action] = []
    if card_db is not None:
        out.extend(_generate_use_card_actions(state, owner, card_db))
    out.extend(_generate_move_actions(state, owner))
    out.extend(_generate_attack_actions(state, owner))
    if can_end_turn(state, owner):
        out.append(Action(ActionType.END_TURN))
    return out


def describe_action(state: GameState, action: Action) -> str:
    if action.action_type == ActionType.END_TURN:
        return "턴 종료"
    if action.action_type == ActionType.MOVE_UNIT:
        unit = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        dst = pos_to_notation(action.target_positions[0]) if action.target_positions else "?"
        return f"{unit.name if unit else '?'} 유닛 이동 → {dst}"
    if action.action_type == ActionType.UNIT_ATTACK:
        src = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        dst = state.get_unit(action.target_unit_ids[0]) if action.target_unit_ids else None
        return f"{src.name if src else '?'} 유닛으로 {dst.name if dst else '?'} 공격"
    if action.action_type == ActionType.USE_CARD:
        card_name = "카드"
        if action.card_instance_id:
            owner = state.active_player
            card = _card_in_hand(state, owner, action.card_instance_id)
            if card is not None:
                unit = _runtime_unit_for_card_instance(state, owner, action.card_instance_id)
                card_name = unit.name if unit is not None else card.card_id
        if action.target_positions and not action.target_unit_ids:
            return f"{card_name} 카드 소환 → {pos_to_notation(action.target_positions[0])}"
        parts = [f"{card_name} 카드 사용"]
        if action.target_unit_ids:
            names = [state.get_unit(uid).name for uid in action.target_unit_ids]
            parts.append("대상=" + ", ".join(names))
        if action.target_positions:
            parts.append("위치=" + ", ".join(pos_to_notation(p) for p in action.target_positions))
        return " | ".join(parts)
    return str(action.action_type)

