# Human-readable debug rendering helpers for the Call of the King prototype.
# This file formats GameState, board cells, hands, units, and legal actions for CLI/manual testing.
# It does not change state; it is only for display and debugging.

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from RL_AI.cards.card_db import CardDefinition, ROLE_NAME_KO, TEXT_CONDITION_NAME_KO
from RL_AI.game_engine.state import (
    Action,
    ActionType,
    BOARD_COLS,
    BOARD_ROWS,
    GameState,
    PlayerID,
    Position,
    TargetSelection,
    UnitState,
)

try:
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
        pos_to_notation,
    )
except Exception:
    W1_BISHOP = "0x01000100"
    W1_KING = "0x01000000"
    W1_KNIGHT = "0x01000200"
    W1_PAWN = "0x01000400"
    W1_ROOK = "0x01000300"
    W2_BISHOP = "0x02000100"
    W2_KNIGHT = "0x02000200"
    W2_PAWN = "0x02000400"
    W2_PRINCESS = "0x02000000"
    W2_ROOK = "0x02000300"

    def pos_to_notation(pos: Position) -> str:
        files = "ABCDEF"
        return f"{pos.row + 1}{files[pos.col]}"


FILES = "ABCDEF"
ROLE_SHORT = {
    0: "L",
    1: "B",
    2: "N",
    3: "R",
    4: "P",
}


def player_label(player_id: PlayerID) -> str:
    return "P1" if player_id == PlayerID.P1 else "P2"


def phase_label(state: GameState) -> str:
    return str(state.phase.value if hasattr(state.phase, "value") else state.phase)


def result_label(state: GameState) -> str:
    return str(state.result.value if hasattr(state.result, "value") else state.result)


def _unit_tag(unit: UnitState) -> str:
    role_value = int(unit.role)
    role_short = ROLE_SHORT.get(role_value, "?")
    owner_short = "1" if unit.owner == PlayerID.P1 else "2"
    return f"{owner_short}{role_short}"


def _unit_summary(unit: UnitState) -> str:
    pos = "--"
    if unit.position is not None:
        pos = pos_to_notation(unit.position)

    flags: List[str] = []
    if unit.promoted:
        flags.append("promoted")
    if unit.moved_this_turn:
        flags.append("moved")
    if unit.attacked_this_turn:
        flags.append("attacked")
    if getattr(unit, "shield", 0) > 0:
        flags.append(f"shield={unit.shield}")
    if getattr(unit, "disabled_move_turns", 0) > 0:
        flags.append(f"no_move={unit.disabled_move_turns}")
    if getattr(unit, "disabled_attack_turns", 0) > 0:
        flags.append(f"no_attack={unit.disabled_attack_turns}")
    if unit.retired:
        flags.append("retired")
    if not unit.is_on_board:
        flags.append("off_board")

    flag_text = f" [{' ,'.join(flags)}]" if flags else ""
    return (
        f"{unit.unit_id} | {player_label(unit.owner)} | {unit.name} | {ROLE_NAME_KO.get(unit.role, str(unit.role))} "
        f"| ATK {unit.attack} | HP {unit.current_life}/{unit.max_life} | {pos}{flag_text}"
    )


def _sorted_units(units: Iterable[UnitState]) -> List[UnitState]:
    role_order = {0: 0, 3: 1, 2: 2, 1: 3, 4: 4}
    return sorted(
        units,
        key=lambda u: (
            int(u.owner),
            role_order.get(int(u.role), 99),
            u.name,
            u.unit_id,
        ),
    )


def _board_cell_text(state: GameState, pos: Position, width: int = 6) -> str:
    unit = state.get_unit_at(pos)
    if unit is None:
        return ".".center(width)
    return _unit_tag(unit).center(width)


def render_board(state: GameState) -> str:
    lines: List[str] = []
    header = "      " + " ".join(f"{f:^{6}}" for f in FILES[:BOARD_COLS])
    lines.append(header)

    for row in range(BOARD_ROWS):
        cells = [_board_cell_text(state, Position(row, col)) for col in range(BOARD_COLS)]
        lines.append(f"{row + 1:>2} | " + " ".join(cells))

    lines.append("")
    lines.append("Legend: 1/2 = player, L=Leader, R=Rook, N=Knight, B=Bishop, P=Pawn")
    lines.append("Top row is 1A~1F, bottom row is 6A~6F")
    return "\n".join(lines)


def _find_runtime_unit_by_card_instance(state: GameState, card_instance_id: str) -> Optional[UnitState]:
    for unit in state.all_units():
        if unit.source_card_instance_id == card_instance_id:
            return unit
    return None


def _find_card_instance_in_state(state: GameState, card_instance_id: str):
    for player in state.players.values():
        for zone_name in ("hand", "deck", "trash"):
            for card in getattr(player, zone_name):
                if card.instance_id == card_instance_id:
                    return card
    return None


def _card_label(state: GameState, card_instance_id: str, card_db: Optional[Dict[str, CardDefinition]]) -> str:
    card = _find_card_instance_in_state(state, card_instance_id)
    unit = _find_runtime_unit_by_card_instance(state, card_instance_id)
    if card is not None and card_db is not None and card.card_id in card_db:
        return card_db[card.card_id].name
    if unit is not None:
        return unit.name
    return card_instance_id[:8]


def _card_detail_lines(state: GameState, card, card_db: Optional[Dict[str, CardDefinition]]) -> List[str]:
    unit = _find_runtime_unit_by_card_instance(state, card.instance_id)
    if card_db is not None and card.card_id in card_db:
        card_def = card_db[card.card_id]
        lines = [
            f"- {card_def.name} | ID {card_def.card_id} | 월드 {card_def.world} | 분류 {card_def.role_name_ko} | ATK {card_def.attack} | LIFE {card_def.life}",
            f"  텍스트 조건: {card_def.text_condition_name_ko}",
            f"  텍스트명: {card_def.text_name or '-'}",
            f"  텍스트: {card_def.text or '-'}",
            f"  효과명: {card_def.effect_name or '-'}",
            f"  효과: {card_def.effect or '-'}",
        ]
        return lines

    name = unit.name if unit is not None else card.card_id
    role_text = ROLE_NAME_KO.get(unit.role, str(unit.role)) if unit is not None else "-"
    atk = unit.attack if unit is not None else "-"
    life = unit.max_life if unit is not None else "-"
    return [f"- {name} | ID {card.card_id} | 분류 {role_text} | ATK {atk} | LIFE {life}"]


def _card_name_list(state: GameState, cards, card_db: Optional[Dict[str, CardDefinition]]) -> str:
    if not cards:
        return "-"
    names: List[str] = []
    for card in cards:
        names.append(_card_label(state, card.instance_id, card_db))
    return ", ".join(names)


def render_player_zone_summary(
    state: GameState,
    player_id: PlayerID,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> str:
    player = state.get_player(player_id)
    lines = [
        f"[{player_label(player_id)}] world={player.world} deck={len(player.deck)} hand={len(player.hand)} trash={len(player.trash)}",
        f"  trash: {_card_name_list(state, player.trash, card_db)}",
        f"  deck(top5 preview): {_card_name_list(state, player.deck[:5], card_db)}",
        "  hand detail:",
    ]
    if not player.hand:
        lines.append("    -")
    else:
        for idx, card in enumerate(player.hand, start=1):
            for line_idx, line in enumerate(_card_detail_lines(state, card, card_db)):
                prefix = f"    {idx}. " if line_idx == 0 else "       "
                lines.append(prefix + line)
    return "\n".join(lines)


def render_units(state: GameState, owner: PlayerID | None = None) -> str:
    units = state.all_units() if owner is None else state.get_units_by_owner(owner)
    lines = ["Units:"]
    for unit in _sorted_units(units):
        lines.append("  " + _unit_summary(unit))
    return "\n".join(lines)


def _resolve_action_target_units(state: GameState, action: Action) -> List[UnitState]:
    if getattr(action, "target_selection", TargetSelection.NONE) == TargetSelection.ALL_ENEMIES:
        return state.get_board_units_by_owner(state.active_player.opponent())
    if getattr(action, "target_selection", TargetSelection.NONE) == TargetSelection.ALL_ALLIES:
        return state.get_board_units_by_owner(state.active_player)
    if getattr(action, "target_selection", TargetSelection.NONE) == TargetSelection.ALL_UNITS:
        return state.get_board_units()
    return [state.get_unit(uid) for uid in getattr(action, "target_unit_ids", ())]


def describe_action_local(
    state: GameState,
    action: Action,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> str:
    if action.action_type == ActionType.END_TURN:
        return "턴 종료"

    if action.action_type == ActionType.MOVE_UNIT:
        unit = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        dst = pos_to_notation(action.target_pos) if action.target_pos else "?"
        return f"{unit.name if unit else '?'} 유닛 이동 → {dst}"

    if action.action_type == ActionType.UNIT_ATTACK:
        attacker = state.get_unit(action.source_unit_id) if action.source_unit_id else None
        target_units = _resolve_action_target_units(state, action)
        target_text = ", ".join(u.name for u in target_units) if target_units else "?"
        return f"{attacker.name if attacker else '?'} 유닛으로 {target_text} 공격"

    if action.action_type != ActionType.USE_CARD or action.card_instance_id is None:
        return str(action.action_type.value if hasattr(action.action_type, "value") else action.action_type)

    card_name = _card_label(state, action.card_instance_id, card_db)
    source_unit = _find_runtime_unit_by_card_instance(state, action.card_instance_id)
    target_units = _resolve_action_target_units(state, action)
    positions = list(getattr(action, "target_positions", ()))

    # summon
    if source_unit is not None and not source_unit.is_alive() and len(positions) == 1:
        return f"{card_name} 카드 소환 → {pos_to_notation(positions[0])}"

    # specific card-friendly wording
    source_card_id = source_unit.source_card_id if source_unit is not None else None

    if source_card_id == W1_KING and len(target_units) == 1 and len(positions) == 1:
        return f"{card_name} 카드 사용 → {target_units[0].name} 유닛을 {pos_to_notation(positions[0])}로 이동"
    if source_card_id == W1_BISHOP and target_units:
        return f"{card_name} 카드 사용 → {', '.join(u.name for u in target_units)} 공격"
    if source_card_id == W1_KNIGHT and len(target_units) == 1:
        return f"{card_name} 카드 사용 → {target_units[0].name} 공격"
    if source_card_id == W1_ROOK and len(target_units) == 1:
        return f"{card_name} 카드 사용 → {target_units[0].name} 체력 전부 회복"
    if source_card_id == W1_PAWN and len(target_units) == 2:
        ally = next((u for u in target_units if u.owner == state.active_player), None)
        enemy = next((u for u in target_units if u.owner != state.active_player), None)
        if ally is not None and enemy is not None:
            return f"{card_name} 카드 사용 → {ally.name} 유닛으로 {enemy.name}를 지정해 공격"
    if source_card_id == W2_PRINCESS and len(target_units) == 1:
        return f"{card_name} 카드 사용 → {target_units[0].name} 회복"
    if source_card_id == W2_BISHOP and len(positions) == 1:
        return f"{card_name} 카드 사용 → 군주를 {pos_to_notation(positions[0])}로 이동"
    if source_card_id == W2_KNIGHT and len(target_units) == 1:
        return f"{card_name} 카드 사용 → {target_units[0].name} 공격 후 처치 시 그 자리로 이동"
    if source_card_id == W2_ROOK and len(target_units) == 1:
        return f"{card_name} 카드 사용 → {target_units[0].name} 공격"
    if source_card_id == W2_PAWN and len(target_units) == 2:
        ally = next((u for u in target_units if u.owner == state.active_player), None)
        enemy = next((u for u in target_units if u.owner != state.active_player), None)
        if ally is not None and enemy is not None:
            return f"{card_name} 카드 사용 → {ally.name} 유닛으로 {enemy.name}를 지정해 공격"

    pieces: List[str] = [f"{card_name} 카드 사용"]
    if target_units:
        pieces.append("대상=" + ", ".join(u.name for u in target_units))
    if positions:
        pieces.append("위치=" + ", ".join(pos_to_notation(p) for p in positions))
    if getattr(action, "target_selection", TargetSelection.NONE) == TargetSelection.ALL_ENEMIES:
        pieces.append("대상=모든 적")
    elif getattr(action, "target_selection", TargetSelection.NONE) == TargetSelection.ALL_ALLIES:
        pieces.append("대상=모든 아군")
    elif getattr(action, "target_selection", TargetSelection.NONE) == TargetSelection.ALL_UNITS:
        pieces.append("대상=모든 유닛")
    return " | ".join(pieces)


def render_legal_actions(
    state: GameState,
    legal_actions: Sequence[Action],
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> str:
    lines = [f"Legal actions: {len(legal_actions)}"]
    for idx, action in enumerate(legal_actions):
        lines.append(f"  {idx:>3}: {describe_action_local(state, action, card_db)}")
    return "\n".join(lines)


def render_state(
    state: GameState,
    legal_actions: Sequence[Action] | None = None,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> str:
    lines = [
        f"Turn {state.turn} | Active={player_label(state.active_player)} | Phase={phase_label(state)} | Result={result_label(state)}",
        render_board(state),
        render_player_zone_summary(state, PlayerID.P1, card_db),
        render_player_zone_summary(state, PlayerID.P2, card_db),
        render_units(state),
    ]
    if state.last_action is not None:
        lines.append("Last action: " + describe_action_local(state, state.last_action, card_db))
    if legal_actions is not None:
        lines.append(render_legal_actions(state, legal_actions, card_db))
    return "\n\n".join(lines)


def print_state(
    state: GameState,
    legal_actions: Sequence[Action] | None = None,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> None:
    print(render_state(state, legal_actions, card_db))
