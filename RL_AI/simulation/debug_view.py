# Human-readable debug rendering helpers for the Call of the King prototype.
# This file formats GameState, board cells, hands, units, and legal actions for CLI/manual testing.
# It does not change state; it is only for display and debugging.

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

from RL_AI.cards.card_db import ROLE_NAME_KO
from RL_AI.game_engine.state import (
    Action,
    BOARD_COLS,
    BOARD_ROWS,
    GameState,
    PlayerID,
    Position,
    UnitState,
)

try:
    from RL_AI.game_engine.rules import describe_action as rules_describe_action
    from RL_AI.game_engine.rules import pos_to_notation
except Exception:
    rules_describe_action = None

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


def _role_order_value(unit: UnitState) -> int:
    role_order = {0: 0, 3: 1, 2: 2, 1: 3, 4: 4}
    return role_order.get(int(unit.role), 99)


def _sorted_units(units: Iterable[UnitState]) -> List[UnitState]:
    return sorted(
        units,
        key=lambda u: (
            int(u.owner),
            _role_order_value(u),
            u.name,
            u.unit_id,
        ),
    )


def _build_unit_display_labels(state: GameState) -> Dict[str, str]:
    """
    Build stable, human-friendly labels like:
    - P1 Leader
    - P1 Rook
    - P1 Pawn#1
    - P2 Pawn#3

    Internal unit_id remains unchanged; this is display-only.
    """
    grouped: Dict[tuple[int, int], List[UnitState]] = {}
    for unit in _sorted_units(state.all_units()):
        key = (int(unit.owner), int(unit.role))
        grouped.setdefault(key, []).append(unit)

    labels: Dict[str, str] = {}
    for units in grouped.values():
        multiple = len(units) > 1
        for idx, unit in enumerate(units, start=1):
            base = f"{player_label(unit.owner)} {ROLE_NAME_KO.get(unit.role, str(unit.role))}"
            if multiple:
                base += f"#{idx}"
            labels[unit.unit_id] = base
    return labels


def _unit_tag(unit: UnitState) -> str:
    role_value = int(unit.role)
    role_short = ROLE_SHORT.get(role_value, "?")
    owner_short = "1" if unit.owner == PlayerID.P1 else "2"
    return f"{owner_short}{role_short}"


def _unit_summary(unit: UnitState, display_labels: Dict[str, str]) -> str:
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
    label = display_labels.get(unit.unit_id, unit.unit_id)
    return (
        f"{label} | {unit.name} | {ROLE_NAME_KO.get(unit.role, str(unit.role))} "
        f"| ATK {unit.attack} | HP {unit.current_life}/{unit.max_life} | {pos}{flag_text}"
    )


def _board_cell_text(state: GameState, pos: Position, width: int = 6) -> str:
    unit = state.get_unit_at(pos)
    if unit is None:
        return ".".center(width)
    tag = _unit_tag(unit)
    return tag.center(width)


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


def _card_label(card, card_db: dict | None = None) -> str:
    if card_db is not None and card.card_id in card_db:
        card_def = card_db[card.card_id]
        return f"{card_def.name} [{card.card_id}]"
    return card.card_id


def render_player_zone_summary(state: GameState, player_id: PlayerID, card_db: dict | None = None) -> str:
    player = state.get_player(player_id)
    hand_cards = [_card_label(card, card_db) for card in player.hand]
    trash_cards = [_card_label(card, card_db) for card in player.trash]
    deck_preview = [_card_label(card, card_db) for card in player.deck[:5]]

    lines = [
        f"[{player_label(player_id)}] world={player.world} deck={len(player.deck)} hand={len(player.hand)} trash={len(player.trash)}",
        f"  hand : {', '.join(hand_cards) if hand_cards else '-'}",
        f"  trash: {', '.join(trash_cards) if trash_cards else '-'}",
        f"  deck(top5 preview): {', '.join(deck_preview) if deck_preview else '-'}",
    ]
    return "\n".join(lines)


def render_units(state: GameState, owner: PlayerID | None = None) -> str:
    units = state.all_units() if owner is None else state.get_units_by_owner(owner)
    display_labels = _build_unit_display_labels(state)
    lines = ["Units:"]
    for unit in _sorted_units(units):
        lines.append("  " + _unit_summary(unit, display_labels))
    return "\n".join(lines)


def _get_action_target_unit_ids(action: Action) -> List[str]:
    if hasattr(action, "target_unit_ids"):
        return list(getattr(action, "target_unit_ids"))
    target_unit_id = getattr(action, "target_unit_id", None)
    return [target_unit_id] if target_unit_id is not None else []


def _get_action_target_positions(action: Action) -> List[Position]:
    if hasattr(action, "target_positions"):
        return list(getattr(action, "target_positions"))
    target_pos = getattr(action, "target_pos", None)
    return [target_pos] if target_pos is not None else []


def describe_action_local(state: GameState, action: Action) -> str:
    if rules_describe_action is not None:
        try:
            return rules_describe_action(state, action)
        except Exception:
            pass

    display_labels = _build_unit_display_labels(state)
    parts = [str(action.action_type.value if hasattr(action.action_type, "value") else action.action_type)]

    source_unit_id = getattr(action, "source_unit_id", None)
    if source_unit_id:
        try:
            parts.append(f"src={display_labels.get(source_unit_id, source_unit_id)}")
        except Exception:
            parts.append(f"src={source_unit_id}")

    card_instance_id = getattr(action, "card_instance_id", None)
    if card_instance_id:
        parts.append(f"card={card_instance_id[:6]}")

    target_unit_ids = _get_action_target_unit_ids(action)
    if target_unit_ids:
        names = []
        for uid in target_unit_ids:
            names.append(display_labels.get(uid, uid))
        parts.append("targets=[" + ", ".join(names) + "]")

    target_positions = _get_action_target_positions(action)
    if target_positions:
        parts.append("pos=[" + ", ".join(pos_to_notation(p) for p in target_positions) + "]")

    return " ".join(parts)


def render_legal_actions(state: GameState, legal_actions: Sequence[Action]) -> str:
    lines = [f"Legal actions: {len(legal_actions)}"]
    for idx, action in enumerate(legal_actions):
        lines.append(f"  {idx:>3}: {describe_action_local(state, action)}")
    return "\n".join(lines)


def render_state(state: GameState, legal_actions: Sequence[Action] | None = None, card_db: dict | None = None) -> str:
    lines = [
        f"Turn {state.turn} | Active={player_label(state.active_player)} | Phase={phase_label(state)} | Result={result_label(state)}",
        render_board(state),
        render_player_zone_summary(state, PlayerID.P1, card_db),
        render_player_zone_summary(state, PlayerID.P2, card_db),
        render_units(state),
    ]
    if state.last_action is not None:
        lines.append("Last action: " + describe_action_local(state, state.last_action))
    if legal_actions is not None:
        lines.append(render_legal_actions(state, legal_actions))
    return "\n\n".join(lines)


def print_state(state: GameState, legal_actions: Sequence[Action] | None = None, card_db: dict | None = None) -> None:
    print(render_state(state, legal_actions, card_db))
