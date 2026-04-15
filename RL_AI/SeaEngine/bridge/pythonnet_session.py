"""Bridge for running the SeaEngine C# project directly in-process via PythonNet."""

from __future__ import annotations

import os
import json
import uuid
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

class PythonNetSession:
    _clr_initialized = False
    _assembly_loaded = False
    _asm = None
    _game_type = None
    _card_loader_type = None
    _silent_logger_type = None

    def __init__(
        self,
        *,
        card_data_path: Optional[str] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parent.parent)
        self.dll_dir = self.project_root / "csharp" / "SeaEngine" / "bin" / "Release" / "net10.0"
        self.card_data_path = str(
            Path(card_data_path).resolve()
            if card_data_path is not None
            else (self.project_root.parent / "cards" / "Cards.csv").resolve()
        )
        self._game = None
        self._turn_counter = 1
        self._uid_parse_method = None
        self._loader = None
        self._profile_enabled = os.getenv("SEAENGINE_PROFILE", "0") == "1"
        self._timings: Dict[str, float] = {}
        self._timing_counts: Dict[str, int] = {}

    def _candidate_dll_paths(self) -> List[Path]:
        base = self.project_root / "csharp" / "SeaEngine" / "bin"
        return [
            base / "Release" / "net10.0" / "SeaEngine.dll",
            base / "Debug" / "net10.0" / "SeaEngine.dll",
        ]

    def _resolve_dll_path(self) -> Path:
        for path in self._candidate_dll_paths():
            if path.exists():
                return path
        raise FileNotFoundError(
            "SeaEngine.dll not found. Searched: "
            + ", ".join(str(path) for path in self._candidate_dll_paths())
        )

    def start(self) -> None:
        if PythonNetSession._clr_initialized:
            return
        
        import clr_loader
        from pythonnet import set_runtime
        import sys
        
        # Ensure DLL directory is in sys.path for assembly resolution
        dll_dir_str = str(self.dll_dir.resolve())
        if dll_dir_str not in sys.path:
            sys.path.append(dll_dir_str)
            
        try:
            rt = clr_loader.get_coreclr()
            set_runtime(rt)
        except Exception:
            # Runtime might already be set
            pass
            
        import clr
        import System

        dll_path = self._resolve_dll_path()
        self.dll_dir = dll_path.parent

        # Load Newtonsoft.Json first if present alongside the engine DLL
        json_path = self.dll_dir / "Newtonsoft.Json.dll"
        if json_path.exists():
            try:
                clr.AddReference("Newtonsoft.Json")
            except Exception:
                clr.AddReference(str(json_path))

        if not PythonNetSession._assembly_loaded:
            # Load the engine assembly directly from disk so PythonNet can reflect over it.
            PythonNetSession._asm = System.Reflection.Assembly.LoadFrom(str(dll_path))
            try:
                clr.AddReference("SeaEngine")
            except Exception:
                # Assembly.LoadFrom above is enough for reflection-based usage.
                pass
            PythonNetSession._game_type = PythonNetSession._asm.GetType("SeaEngine.Game")
            PythonNetSession._card_loader_type = PythonNetSession._asm.GetType("SeaEngine.CardManager.CardLoader")
            PythonNetSession._silent_logger_type = PythonNetSession._asm.GetType("SeaEngine.Logger.SilentLogger")
            uid_type = PythonNetSession._asm.GetType("SeaEngine.Common.Uid")
            if uid_type is None:
                raise RuntimeError("SeaEngine.Common.Uid type not found in assembly")
            self._uid_parse_method = uid_type.GetMethod("Parse")
            if self._uid_parse_method is None:
                raise RuntimeError("SeaEngine.Common.Uid.Parse(string) not found")
            PythonNetSession._assembly_loaded = True
        else:
            uid_type = PythonNetSession._asm.GetType("SeaEngine.Common.Uid")
            self._uid_parse_method = uid_type.GetMethod("Parse")
            if self._uid_parse_method is None:
                raise RuntimeError("SeaEngine.Common.Uid.Parse(string) not found")

        PythonNetSession._clr_initialized = True

    def close(self) -> None:
        self._game = None

    def _record_timing(self, key: str, elapsed: float) -> None:
        if not self._profile_enabled:
            return
        self._timings[key] = self._timings.get(key, 0.0) + elapsed
        self._timing_counts[key] = self._timing_counts.get(key, 0) + 1

    def drain_profile_stats(self) -> Dict[str, Dict[str, float]]:
        if not self._profile_enabled:
            return {}
        stats = {
            key: {
                "total_sec": self._timings.get(key, 0.0),
                "count": float(self._timing_counts.get(key, 0)),
            }
            for key in sorted(self._timings.keys())
        }
        self._timings.clear()
        self._timing_counts.clear()
        return stats

    def ping(self) -> Dict[str, Any]:
        return {"message": "pong"}

    def init_game(
        self,
        *,
        player1_deck: str = "",
        player2_deck: str = "",
        player1_id: str = "P1",
        player2_id: str = "P2",
    ) -> Dict[str, Any]:
        start_t = time.perf_counter()
        import System
        if not PythonNetSession._clr_initialized:
            self.start()
        if PythonNetSession._game_type is None or PythonNetSession._card_loader_type is None or PythonNetSession._silent_logger_type is None:
            raise RuntimeError("SeaEngine assembly types are not initialized")

        if self._loader is None:
            self._loader = System.Activator.CreateInstance(PythonNetSession._card_loader_type, self.card_data_path)
        logger = System.Activator.CreateInstance(PythonNetSession._silent_logger_type)

        self._game = System.Activator.CreateInstance(PythonNetSession._game_type, self._loader, logger, player1_id, player2_id)
        
        p1_deck = self._normalize_deck(player1_deck, True)
        p2_deck = self._normalize_deck(player2_deck, False)
        
        # Use direct calling instead of Reflection Invoke for idiomatic PythonNet
        self._game.Init(p1_deck, p2_deck)
        self._turn_counter = 1
        snapshot = self.snapshot()
        self._record_timing("init_game", time.perf_counter() - start_t)
        return snapshot

    def _normalize_deck(self, deck_json: str, is_p1: bool) -> str:
        if deck_json and deck_json.strip():
            return deck_json
        fallback = ["Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P"] if is_p1 else ["Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P"]
        import json
        return json.dumps(fallback)

    def snapshot(self) -> Dict[str, Any]:
        if self._game is None:
            raise RuntimeError("Game not initialized")
        return self._build_snapshot()

    def apply_action(self, action_uid: str) -> Dict[str, Any]:
        if self._game is None:
            raise RuntimeError("Game not initialized")
        start_t = time.perf_counter()
        action_uid = str(action_uid)

        selected_action = None
        actions = self._game.Actions
        for i in range(actions.Count):
            a = actions[i]
            if str(a.Guid) == action_uid:
                selected_action = a
                if str(a.EffectId) == "TurnEnd":
                    self._turn_counter += 1
                break
        if selected_action is None:
            raise KeyError(f"Unknown action uid: {action_uid}")

        self._game.UseAction(selected_action.Guid)
        snapshot = self.snapshot()
        self._record_timing("apply_action", time.perf_counter() - start_t)
        return snapshot

    def _build_snapshot(self) -> Dict[str, Any]:
        start_t = time.perf_counter()
        data = self._game.Data

        def _string(value: Any) -> str:
            return "" if value is None else str(value)

        def _int(value: Any, default: int = -1) -> int:
            try:
                return int(value)
            except Exception:
                return default

        def _bool(value: Any) -> bool:
            return bool(value)

        def _iter_cards(zone: Any) -> List[Any]:
            cards = getattr(zone, "Cards", None)
            if cards is None:
                return []
            return list(cards)

        def _extract_hand_card(card: Any) -> Dict[str, Any]:
            return {
                "uid": _string(getattr(card, "Guid", "")),
                "card_id": _string(getattr(getattr(card, "Data", None), "Id", "")),
                "name": _string(getattr(getattr(card, "Data", None), "Name", "")),
            }

        def _extract_statuses(unit: Any) -> List[Dict[str, Any]]:
            buffs = getattr(unit, "Buffs", None)
            if buffs is None:
                return []
            statuses: List[Dict[str, Any]] = []
            for key in list(buffs.Keys):
                statuses.append(
                    {
                        "type": _string(key),
                        "value": _int(buffs[key], 0),
                        "remaining_turns": 1,
                    }
                )
            return statuses

        snapshot = {
            "turn": self._turn_counter,
            "active_player": _string(getattr(data, "ActivePlayerId", "")),
            "result": "Ongoing",
            "winner_id": _string(getattr(data, "WinnerId", "")),
            "players": [],
            "board": [],
            "actions": [],
        }

        winner_id = snapshot["winner_id"]
        p1_id = _string(getattr(getattr(data, "Player1", None), "Id", ""))
        if winner_id:
            snapshot["result"] = "Player1Win" if winner_id == p1_id else "Player2Win"

        for player in [getattr(data, "Player1", None), getattr(data, "Player2", None)]:
            if player is None:
                continue
            hand_cards = _iter_cards(getattr(player, "Hand", None))
            deck_cards = _iter_cards(getattr(player, "Deck", None))
            trash_cards = _iter_cards(getattr(player, "Trash", None))
            snapshot["players"].append(
                {
                    "id": _string(getattr(player, "Id", "")),
                    "hand_count": len(hand_cards),
                    "deck_count": len(deck_cards),
                    "trash_count": len(trash_cards),
                    "hand": [_extract_hand_card(card) for card in hand_cards],
                }
            )

        board = getattr(data, "Board", None)
        board_cards = _iter_cards(board)
        for card in board_cards:
            unit = getattr(card, "Unit", None)
            card_data = getattr(card, "Data", None)
            owner = getattr(card, "Owner", None)
            if unit is None or card_data is None or owner is None:
                continue

            atk = _int(getattr(unit, "Atk", 0), 0)
            snapshot["board"].append(
                {
                    "uid": _string(getattr(card, "Guid", "")),
                    "card_id": _string(getattr(card_data, "Id", "")),
                    "name": _string(getattr(card_data, "Name", "")),
                    "owner": _string(getattr(owner, "Id", "")),
                    "role": _string(getattr(card_data, "UnitType", "")),
                    "atk": atk,
                    "effective_atk": atk,
                    "hp": _int(getattr(unit, "Hp", 0), 0),
                    "max_hp": _int(getattr(unit, "MaxHp", 0), 0),
                    "is_placed": _bool(getattr(unit, "IsPlaced", False)),
                    "is_moved": _bool(getattr(unit, "IsMoved", False)),
                    "pos_x": _int(getattr(unit, "PosX", -1), -1),
                    "pos_y": _int(getattr(unit, "PosY", -1), -1),
                    "statuses": _extract_statuses(unit),
                }
            )

        actions = list(getattr(self._game, "Actions", []))
        for action in actions:
            target = getattr(action, "Target", None)
            target_dict = None
            if target is not None:
                target_dict = {
                    "type": _string(getattr(target, "Type", "")),
                    "guid": _string(getattr(target, "Guid", "")),
                    "guid2": _string(getattr(target, "Guid2", "")),
                    "pos_x": _int(getattr(target, "PosX", -1), -1),
                    "pos_y": _int(getattr(target, "PosY", -1), -1),
                }

            snapshot["actions"].append(
                {
                    "uid": _string(getattr(action, "Guid", "")),
                    "effect_id": _string(getattr(action, "EffectId", "")),
                    "source": _string(getattr(action, "Source", "")),
                    "target": target_dict,
                }
            )

        self._record_timing("_build_snapshot", time.perf_counter() - start_t)
        return snapshot
