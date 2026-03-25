from __future__ import annotations

# Lightweight notation-oriented logging for the Call of the King prototype.
# This file records compact per-move match logs for later analysis, not full debug snapshots.
# It keeps JSONL structured data and a small TXT notation log side by side.

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from RL_AI.cards.card_db import CardDefinition, ROLE_NAME_KO
from RL_AI.game_engine.state import Action, GameState, PlayerID, Position, UnitState


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _player_label(player_id: PlayerID) -> str:
    return "P1" if player_id == PlayerID.P1 else "P2"


def _phase_label(state: GameState) -> str:
    return state.phase.value if hasattr(state.phase, "value") else str(state.phase)


def _result_label(state: GameState) -> str:
    return state.result.value if hasattr(state.result, "value") else str(state.result)


def _pos_to_notation(pos: Position) -> str:
    files = "ABCDEF"
    return f"{pos.row + 1}{files[pos.col]}"


def _card_name_from_instance(state: GameState, player_id: PlayerID, card_instance_id: Optional[str], card_db: Optional[Dict[str, CardDefinition]]) -> str:
    if card_instance_id is None:
        return "-"
    player = state.get_player(player_id)
    for zone_name in ("hand", "deck", "trash"):
        for card in getattr(player, zone_name):
            if card.instance_id == card_instance_id:
                if card_db is not None and card.card_id in card_db:
                    return card_db[card.card_id].name
                return card.card_id
    # fallback: runtime unit lookup
    for unit in state.units.values():
        if unit.owner == player_id and unit.source_card_instance_id == card_instance_id:
            return unit.name
    return card_instance_id


def _build_unit_labels(state: GameState) -> Dict[str, str]:
    """
    Display-only stable labels:
      P1 군주
      P1 폰#1
      P2 비숍
    """
    role_order = {0: 0, 3: 1, 2: 2, 1: 3, 4: 4}

    units = sorted(
        state.all_units(),
        key=lambda u: (
            int(u.owner),
            role_order.get(int(u.role), 99),
            u.name,
            u.unit_id,
        ),
    )

    grouped: Dict[tuple[int, int], List[UnitState]] = {}
    for unit in units:
        key = (int(unit.owner), int(unit.role))
        grouped.setdefault(key, []).append(unit)

    labels: Dict[str, str] = {}
    for group in grouped.values():
        multiple = len(group) > 1
        for idx, unit in enumerate(group, start=1):
            base = f"{_player_label(unit.owner)} {ROLE_NAME_KO.get(unit.role, str(unit.role))}"
            if multiple:
                base += f"#{idx}"
            labels[unit.unit_id] = base
    return labels


def _leader_hp(state: GameState, owner: PlayerID) -> Optional[int]:
    if hasattr(state, "get_leader_runtime_unit"):
        unit = state.get_leader_runtime_unit(owner)
    else:
        unit = state.get_leader_unit(owner)
    if unit is None:
        return None
    return unit.current_life


def _unit_short(unit: UnitState, unit_labels: Dict[str, str]) -> str:
    label = unit_labels.get(unit.unit_id, unit.unit_id)
    if unit.position is not None and unit.is_alive():
        return f"{label}@{_pos_to_notation(unit.position)}({unit.current_life}/{unit.max_life})"
    return f"{label}(off_board:{unit.current_life}/{unit.max_life})"


def _get_action_target_unit_ids(action: Action) -> List[str]:
    if hasattr(action, "target_unit_ids"):
        return list(getattr(action, "target_unit_ids") or ())
    target_unit_id = getattr(action, "target_unit_id", None)
    return [target_unit_id] if target_unit_id else []


def _get_action_target_positions(action: Action) -> List[Position]:
    if hasattr(action, "target_positions"):
        return list(getattr(action, "target_positions") or ())
    target_pos = getattr(action, "target_pos", None)
    return [target_pos] if target_pos else []


def action_to_notation(
    state: GameState,
    action: Action,
    *,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> str:
    unit_labels = _build_unit_labels(state)
    action_type = action.action_type.value if hasattr(action.action_type, "value") else str(action.action_type)
    target_unit_ids = _get_action_target_unit_ids(action)
    target_positions = _get_action_target_positions(action)

    if action_type == "END_TURN":
        return "턴 종료"

    if action_type == "MOVE_UNIT":
        src = state.get_unit(action.source_unit_id) if getattr(action, "source_unit_id", None) else None
        dst = _pos_to_notation(target_positions[0]) if target_positions else "?"
        src_name = unit_labels.get(src.unit_id, src.unit_id) if src is not None else "?"
        return f"{src_name} 이동 -> {dst}"

    if action_type == "UNIT_ATTACK":
        src = state.get_unit(action.source_unit_id) if getattr(action, "source_unit_id", None) else None
        src_name = unit_labels.get(src.unit_id, src.unit_id) if src is not None else "?"
        if len(target_unit_ids) == 1:
            dst = state.get_unit(target_unit_ids[0])
            dst_name = unit_labels.get(dst.unit_id, dst.unit_id)
            return f"{src_name} 공격 -> {dst_name}"
        return f"{src_name} 공격"

    if action_type == "USE_CARD":
        owner = state.active_player
        card_name = _card_name_from_instance(state, owner, getattr(action, "card_instance_id", None), card_db)

        # summon
        if target_positions and not target_unit_ids:
            if len(target_positions) == 1:
                return f"{card_name} 소환 -> {_pos_to_notation(target_positions[0])}"
            pos_text = ", ".join(_pos_to_notation(p) for p in target_positions)
            return f"{card_name} 사용 | 위치=[{pos_text}]"

        pieces = [f"{card_name} 사용"]
        if target_unit_ids:
            unit_names = []
            for uid in target_unit_ids:
                unit = state.get_unit(uid)
                unit_names.append(unit_labels.get(unit.unit_id, unit.unit_id))
            pieces.append("대상=" + ", ".join(unit_names))
        if target_positions:
            pieces.append("위치=" + ", ".join(_pos_to_notation(p) for p in target_positions))
        return " | ".join(pieces)

    return action_type


def action_to_dict(
    state: GameState,
    action: Action,
    *,
    card_db: Optional[Dict[str, CardDefinition]] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "action_type": action.action_type.value if hasattr(action.action_type, "value") else str(action.action_type),
        "notation": action_to_notation(state, action, card_db=card_db),
        "card_instance_id": getattr(action, "card_instance_id", None),
        "source_unit_id": getattr(action, "source_unit_id", None),
        "target_selection": (
            action.target_selection.value if hasattr(action.target_selection, "value") else str(action.target_selection)
        ) if hasattr(action, "target_selection") else None,
        "target_unit_ids": _get_action_target_unit_ids(action),
        "target_positions": [
            {"row": p.row, "col": p.col, "notation": _pos_to_notation(p)}
            for p in _get_action_target_positions(action)
        ],
    }
    return data


def compact_state_summary(state: GameState) -> Dict[str, Any]:
    unit_labels = _build_unit_labels(state)
    return {
        "turn": state.turn,
        "active_player": _player_label(state.active_player),
        "phase": _phase_label(state),
        "result": _result_label(state),
        "p1_leader_hp": _leader_hp(state, PlayerID.P1),
        "p2_leader_hp": _leader_hp(state, PlayerID.P2),
        "p1_hand_count": len(state.get_player(PlayerID.P1).hand),
        "p2_hand_count": len(state.get_player(PlayerID.P2).hand),
        "board_units": [
            _unit_short(unit, unit_labels)
            for unit in state.get_board_units()
        ],
    }


class MatchLogger:
    """
    Lightweight notation logger.

    Files created:
      - <base>.jsonl : structured compact events
      - <base>.txt   : human-readable notation log

    Recommended usage:
      logger = MatchLogger("RL_AI/log/manual_match_001", card_db=card_db)
      logger.log_match_start(state, metadata={...})
      logger.log_action_options(state, legal_actions)   # optional
      logger.log_action_chosen(state, action, action_index=0)
      ...
      logger.log_state_checkpoint(state)                # after step
      ...
      logger.log_match_end(state)
    """

    def __init__(
        self,
        base_path: str | Path,
        *,
        card_db: Optional[Dict[str, CardDefinition]] = None,
        save_text_log: bool = True,
        include_action_options: bool = False,
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.base_path.with_suffix(".jsonl")
        self.text_path = self.base_path.with_suffix(".txt")
        self.card_db = card_db
        self.save_text_log = save_text_log
        self.include_action_options = include_action_options

        self.jsonl_path.write_text("", encoding="utf-8")
        if self.save_text_log:
            self.text_path.write_text("", encoding="utf-8")

    def _write_json_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        record = {
            "timestamp_utc": _utc_now_iso(),
            "event_type": event_type,
            "payload": payload,
        }
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _append_text(self, text: str) -> None:
        if not self.save_text_log:
            return
        with self.text_path.open("a", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")

    def log_match_start(self, state: GameState, *, metadata: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "state": compact_state_summary(state),
            "metadata": metadata or {},
        }
        self._write_json_event("match_start", payload)
        self._append_text(
            f"=== MATCH START ===\n"
            f"turn={state.turn} active={_player_label(state.active_player)} phase={_phase_label(state)} "
            f"result={_result_label(state)}\n"
            f"P1 leader_hp={_leader_hp(state, PlayerID.P1)} | P2 leader_hp={_leader_hp(state, PlayerID.P2)}\n"
        )

    def log_action_options(self, state: GameState, legal_actions: Sequence[Action]) -> None:
        if not self.include_action_options:
            return
        payload = {
            "turn": state.turn,
            "active_player": _player_label(state.active_player),
            "phase": _phase_label(state),
            "legal_action_count": len(legal_actions),
            "legal_actions": [
                action_to_dict(state, action, card_db=self.card_db)
                for action in legal_actions
            ],
        }
        self._write_json_event("legal_actions", payload)

    def log_action_chosen(self, state: GameState, action: Action, *, action_index: Optional[int] = None) -> None:
        notation = action_to_notation(state, action, card_db=self.card_db)
        payload = {
            "turn": state.turn,
            "active_player": _player_label(state.active_player),
            "phase": _phase_label(state),
            "action_index": action_index,
            "action": action_to_dict(state, action, card_db=self.card_db),
        }
        self._write_json_event("action_chosen", payload)
        self._append_text(f"T{state.turn} {_player_label(state.active_player)} {_phase_label(state)} | {notation}\n")

    def log_state_checkpoint(self, state: GameState, *, note: Optional[str] = None) -> None:
        payload = {"state": compact_state_summary(state)}
        if note:
            payload["note"] = note
        self._write_json_event("state_checkpoint", payload)

        line = (
            f"    -> result={_result_label(state)} "
            f"P1_HP={_leader_hp(state, PlayerID.P1)} "
            f"P2_HP={_leader_hp(state, PlayerID.P2)} "
            f"board={'; '.join(compact_state_summary(state)['board_units'])}"
        )
        if note:
            line += f" | note={note}"
        self._append_text(line)

    def log_event(self, event_type: str, **payload: Any) -> None:
        self._write_json_event(event_type, payload)

    def log_match_end(self, state: GameState, *, metadata: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "state": compact_state_summary(state),
            "metadata": metadata or {},
        }
        self._write_json_event("match_end", payload)
        self._append_text(
            f"=== MATCH END ===\n"
            f"turn={state.turn} result={_result_label(state)} "
            f"P1_HP={_leader_hp(state, PlayerID.P1)} P2_HP={_leader_hp(state, PlayerID.P2)}\n"
        )
