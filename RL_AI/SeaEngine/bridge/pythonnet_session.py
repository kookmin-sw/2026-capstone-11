"""Bridge for running the SeaEngine C# project directly in-process via PythonNet."""

from __future__ import annotations

import os
import json
import uuid
import threading
from pathlib import Path
from typing import Any, Dict, Optional, List

from RL_AI.cards.card_db import Role, load_card_list

class PythonNetSession:
    _clr_initialized = False
    _assembly_loaded = False
    _init_lock = threading.Lock()
    _asm = None
    _game_type = None
    _card_loader_type = None
    _simple_logger_type = None
    _silent_logger_type = None
    _logger_interface_type = None
    _logger_requires_game_id = False
    _rl_exporter_type = None
    _rl_export_method = None

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
        self._logger = None
        self._logger_mode = "silent"
        self._turn_counter = 1
        self._uid_parse_method = None
        self._loader = None

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

    def _resolve_newtonsoft_json_path(self) -> Optional[Path]:
        direct_path = self.dll_dir / "Newtonsoft.Json.dll"
        if direct_path.exists():
            return direct_path
        nuget_root = Path.home() / ".nuget" / "packages" / "newtonsoft.json"
        if nuget_root.exists():
            candidates = sorted(nuget_root.glob("*/lib/**/Newtonsoft.Json.dll"))
            if candidates:
                return candidates[-1]
        return None

    def start(self) -> None:
        if PythonNetSession._clr_initialized:
            return

        with PythonNetSession._init_lock:
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

            # Load Newtonsoft.Json only when we can resolve a concrete file path.
            # Some environments do not have a globally resolvable assembly name,
            # so loading by path is more reliable than AddReference("name").
            json_path = self._resolve_newtonsoft_json_path()
            if json_path is not None and json_path.exists():
                try:
                    System.Reflection.Assembly.LoadFrom(str(json_path))
                except Exception:
                    try:
                        clr.AddReference(str(json_path))
                    except Exception:
                        # Newtonsoft is optional for the bridge path we use here.
                        pass

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
                PythonNetSession._simple_logger_type = PythonNetSession._asm.GetType("SeaEngine.Logger.SimpleLogger")
                PythonNetSession._logger_interface_type = PythonNetSession._asm.GetType("SeaEngine.Logger.ILogger")
                if PythonNetSession._simple_logger_type is None:
                    raise RuntimeError("SeaEngine.Logger.SimpleLogger type not found in assembly")
                if PythonNetSession._logger_interface_type is None:
                    raise RuntimeError("SeaEngine.Logger.ILogger type not found in assembly")
                PythonNetSession._logger_requires_game_id = True
                PythonNetSession._rl_exporter_type = PythonNetSession._asm.GetType("SeaEngine.RL.RlObservationExporter")
                if PythonNetSession._rl_exporter_type is not None:
                    PythonNetSession._rl_export_method = PythonNetSession._rl_exporter_type.GetMethod("Export")
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
        self._logger = None
        self._logger_mode = "silent"

    def ping(self) -> Dict[str, Any]:
        return {"message": "pong"}

    def init_game(
        self,
        *,
        player1_deck: str = "",
        player2_deck: str = "",
        player1_id: str = "P1",
        player2_id: str = "P2",
        logger_mode: str = "silent",
    ) -> Dict[str, Any]:
        import System
        if not PythonNetSession._clr_initialized:
            self.start()
        if PythonNetSession._game_type is None or PythonNetSession._card_loader_type is None:
            raise RuntimeError("SeaEngine assembly types are not initialized")
        if PythonNetSession._simple_logger_type is None or PythonNetSession._logger_interface_type is None:
            raise RuntimeError("SeaEngine logger types are not initialized")
        if PythonNetSession._rl_exporter_type is not None and PythonNetSession._rl_export_method is None:
            PythonNetSession._rl_export_method = PythonNetSession._rl_exporter_type.GetMethod("Export")

        if self._loader is None:
            self._loader = self._create_card_loader()
        mode = str(logger_mode or "silent").strip().lower()
        if mode == "simple":
            logger = System.Activator.CreateInstance(PythonNetSession._simple_logger_type, f"py_{uuid.uuid4().hex[:12]}")
        else:
            logger = self._create_silent_logger()
            mode = "silent"
        self._logger_mode = mode
        self._logger = logger

        self._game = System.Activator.CreateInstance(PythonNetSession._game_type, self._loader, logger, player1_id, player2_id)
        
        p1_deck = self._normalize_deck(player1_deck, True)
        p2_deck = self._normalize_deck(player2_deck, False)
        
        self._game.Init(p1_deck, p2_deck)
        self._turn_counter = 1
        return self.snapshot()

    def consume_engine_log(self) -> Optional[str]:
        if self._logger is None or self._logger_mode != "simple":
            return None
        try:
            end_logging = getattr(self._logger, "EndLogging", None)
            if callable(end_logging):
                return str(end_logging())
        except Exception:
            return None
        finally:
            self._logger = None
            self._logger_mode = "silent"
        return None

    def _create_silent_logger(self):
        import System
        import clr

        if PythonNetSession._silent_logger_type is None:
            logger_iface = PythonNetSession._logger_interface_type
            if logger_iface is None:
                raise RuntimeError("SeaEngine.Logger.ILogger type not found in assembly")

            assembly_name = System.Reflection.AssemblyName("RL_AI_PythonSilentLogger")
            assembly_builder = System.Reflection.Emit.AssemblyBuilder.DefineDynamicAssembly(
                assembly_name,
                System.Reflection.Emit.AssemblyBuilderAccess.Run,
            )
            module_builder = assembly_builder.DefineDynamicModule("MainModule")
            type_builder = module_builder.DefineType(
                "RL_AI.SeaEngine.PythonSilentLogger",
                System.Reflection.TypeAttributes.Public
                | System.Reflection.TypeAttributes.Sealed
                | System.Reflection.TypeAttributes.Class,
            )
            type_builder.AddInterfaceImplementation(logger_iface)

            method_specs = [
                ("LogAction", ["SeaEngine.Common.GameAction", "SeaEngine.GameDataManager.GameData"]),
                ("LogCards", ["SeaEngine.GameDataManager.GameData"]),
                ("LogEvent", ["System.String", "System.String", "SeaEngine.Common.Uid"]),
                ("Log", ["System.String", "SeaEngine.GameDataManager.GameData"]),
            ]
            for method_name, param_type_names in method_specs:
                iface_method = logger_iface.GetMethod(method_name)
                if iface_method is None:
                    raise RuntimeError(f"ILogger method not found: {method_name}")
                param_types = []
                for type_name in param_type_names:
                    if type_name == "System.String":
                        param_types.append(System.String)
                    else:
                        param_type = PythonNetSession._asm.GetType(type_name)
                        if param_type is None:
                            raise RuntimeError(f"Type not found for silent logger: {type_name}")
                        param_types.append(param_type)
                method_builder = type_builder.DefineMethod(
                    method_name,
                    System.Reflection.MethodAttributes.Public
                    | System.Reflection.MethodAttributes.Virtual
                    | System.Reflection.MethodAttributes.HideBySig
                    | System.Reflection.MethodAttributes.NewSlot
                    | System.Reflection.MethodAttributes.Final
                    | System.Reflection.MethodAttributes.SpecialName,
                    System.Void,
                    param_types,
                )
                il = method_builder.GetILGenerator()
                il.Emit(System.Reflection.Emit.OpCodes.Ret)
                type_builder.DefineMethodOverride(method_builder, iface_method)

            PythonNetSession._silent_logger_type = type_builder.CreateType()

        return System.Activator.CreateInstance(PythonNetSession._silent_logger_type)

    def _normalize_deck(self, deck_json: str, is_p1: bool) -> str:
        if deck_json and deck_json.strip():
            return deck_json
        fallback = ["Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P"] if is_p1 else ["Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P"]
        import json
        return json.dumps(fallback)

    def _build_card_loader_lines(self) -> List[str]:
        cards = load_card_list(self.card_data_path)
        leader_by_world: Dict[int, str] = {}
        for card in cards:
            if card.role == Role.LEADER and card.world not in leader_by_world:
                leader_by_world[card.world] = card.card_id

        role_to_unit_type = {
            Role.LEADER: "L",
            Role.ROOK: "R",
            Role.KNIGHT: "N",
            Role.BISHOP: "B",
            Role.PAWN: "P",
        }

        lines = ["ID,Name,LeaderID,UnitType,Atk,Hp,EffectID,EventID"]
        for card in sorted(cards, key=lambda c: (c.world, int(c.role), c.card_id)):
            unit_type = role_to_unit_type.get(card.role)
            if unit_type is None:
                raise ValueError(f"Unsupported card role: {card.role}")
            leader_id = leader_by_world.get(card.world, card.card_id)
            lines.append(
                ",".join(
                    [
                        card.card_id,
                        card.name,
                        leader_id,
                        unit_type,
                        str(card.attack),
                        str(card.life),
                        card.effect_id or card.card_id,
                        card.event_id or card.card_id,
                    ]
                )
            )
        return lines

    def _create_card_loader(self):
        import System
        from System.Runtime.Serialization import FormatterServices

        cards = load_card_list(self.card_data_path)
        loader = FormatterServices.GetUninitializedObject(PythonNetSession._card_loader_type)
        cards_field = PythonNetSession._card_loader_type.GetField(
            "_cards",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance,
        )
        if cards_field is None:
            raise RuntimeError("SeaEngine.CardManager.CardLoader._cards field not found")

        unit_type_enum = PythonNetSession._asm.GetType("SeaEngine.Common.UnitType")
        if unit_type_enum is None:
            raise RuntimeError("SeaEngine.Common.UnitType type not found in assembly")

        role_to_unit_type = {
            Role.LEADER: "Leader",
            Role.ROOK: "Rook",
            Role.KNIGHT: "Knight",
            Role.BISHOP: "Bishop",
            Role.PAWN: "Pawn",
        }
        leader_by_world: Dict[int, str] = {}
        for card in cards:
            if card.role == Role.LEADER and card.world not in leader_by_world:
                leader_by_world[card.world] = card.card_id

        carddata_type = PythonNetSession._asm.GetType("SeaEngine.CardManager.CardData")
        if carddata_type is None:
            raise RuntimeError("SeaEngine.CardManager.CardData type not found in assembly")
        dict_type = System.Collections.Generic.Dictionary[System.String, carddata_type]
        card_dict = dict_type()

        for card in cards:
            unit_type_name = role_to_unit_type.get(card.role)
            if unit_type_name is None:
                raise ValueError(f"Unsupported card role: {card.role}")
            leader_id = leader_by_world.get(card.world, card.card_id)
            unit_type = System.Enum.Parse(unit_type_enum, unit_type_name)
            effect_id = "PawnGeneric" if card.role == Role.PAWN else card.card_id
            card_data = FormatterServices.GetUninitializedObject(carddata_type)
            for field_name, value in {
                "<Id>k__BackingField": System.String(card.card_id),
                "<Name>k__BackingField": System.String(card.name),
                "<LeaderId>k__BackingField": System.String(leader_id),
                "<UnitType>k__BackingField": unit_type,
                "<Atk>k__BackingField": System.Int32(int(card.attack)),
                "<Hp>k__BackingField": System.Int32(int(card.life)),
                "EffectId": System.String(effect_id),
                "EventId": System.String(card.event_id or card.card_id),
            }.items():
                field = carddata_type.GetField(
                    field_name,
                    System.Reflection.BindingFlags.Public
                    | System.Reflection.BindingFlags.NonPublic
                    | System.Reflection.BindingFlags.Instance,
                )
                if field is None:
                    raise RuntimeError(f"SeaEngine.CardManager.CardData.{field_name} field not found")
                field.SetValue(card_data, value)
            card_dict.Add(card.card_id, card_data)

        cards_field.SetValue(loader, card_dict)
        return loader

    def _attach_python_observation(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        from RL_AI.SeaEngine import observation as obs_mod

        raw_snapshot = dict(snapshot)
        raw_snapshot["state_vector"] = None
        raw_snapshot["action_feature_vectors"] = None
        observation = obs_mod.build_observation(raw_snapshot, raw_snapshot.get("active_player"))
        snapshot["global_vector"] = list(observation.global_vector)
        snapshot["state_vector"] = list(observation.state_vector)
        snapshot["action_feature_vectors"] = [list(a) for a in observation.action_feature_vectors]
        return snapshot

    def snapshot(self) -> Dict[str, Any]:
        if self._game is None:
            raise RuntimeError("Game not initialized")
        return self._build_snapshot()

    def apply_action(self, action_uid: str) -> Dict[str, Any]:
        if self._game is None:
            raise RuntimeError("Game not initialized")
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
        return self.snapshot()

    def _build_snapshot(self) -> Dict[str, Any]:
        import System

        def _string(value: Any) -> str:
            return "" if value is None else str(value)

        def _int(value: Any, default: int = -1) -> int:
            try:
                return int(value)
            except Exception:
                return default

        def _bool(value: Any) -> bool:
            return bool(value)

        def _to_list(value: Any) -> List[Any]:
            if value is None:
                return []
            try:
                return list(value)
            except Exception:
                return []

        def _to_float_list(value: Any) -> List[float]:
            return [float(v) for v in _to_list(value)]

        def _to_float_matrix(value: Any) -> List[List[float]]:
            return [_to_float_list(row) for row in _to_list(value)]

        if PythonNetSession._rl_export_method is not None:
            frame = PythonNetSession._rl_export_method.Invoke(None, [self._game, System.Int32(self._turn_counter)])

            players = []
            for player in _to_list(getattr(frame, "Players", None)):
                hand = _to_list(getattr(player, "Hand", None))
                players.append(
                    {
                        "id": _string(getattr(player, "Id", "")),
                        "hand_count": _int(getattr(player, "HandCount", 0), 0),
                        "deck_count": _int(getattr(player, "DeckCount", 0), 0),
                        "trash_count": _int(getattr(player, "TrashCount", 0), 0),
                        "hand": [
                            {
                                "uid": _string(getattr(card, "Uid", "")),
                                "card_id": _string(getattr(card, "CardId", "")),
                                "name": _string(getattr(card, "Name", "")),
                            }
                            for card in hand
                        ],
                    }
                )

            board = []
            for card in _to_list(getattr(frame, "Board", None)):
                board.append(
                    {
                        "uid": _string(getattr(card, "Uid", "")),
                        "card_id": _string(getattr(card, "CardId", "")),
                        "name": _string(getattr(card, "Name", "")),
                        "owner": _string(getattr(card, "OwnerId", "")),
                        "role": _string(getattr(card, "Role", "")),
                        "atk": _int(getattr(card, "Atk", 0), 0),
                        "effective_atk": _int(getattr(card, "EffectiveAtk", 0), 0),
                        "hp": _int(getattr(card, "Hp", 0), 0),
                        "max_hp": _int(getattr(card, "MaxHp", 0), 0),
                        "is_placed": _bool(getattr(card, "IsPlaced", False)),
                        "is_moved": _bool(getattr(card, "IsMoved", False)),
                        "is_attacked": _bool(getattr(card, "IsAttacked", False)),
                        "pos_x": _int(getattr(card, "PosX", -1), -1),
                        "pos_y": _int(getattr(card, "PosY", -1), -1),
                        "statuses": [
                            {
                                "type": _string(getattr(status, "Type", "")),
                                "value": _int(getattr(status, "Value", 0), 0),
                                "remaining_turns": 1,
                            }
                            for status in _to_list(getattr(card, "Statuses", None))
                        ],
                    }
                )

            actions = []
            for action in _to_list(getattr(frame, "Actions", None)):
                actions.append(
                    {
                        "uid": _string(getattr(action, "Uid", "")),
                        "effect_id": _string(getattr(action, "EffectId", "")),
                        "source": _string(getattr(action, "Source", "")),
                        "target": {
                            "type": _string(getattr(action, "TargetType", "None")),
                            "guid": _string(getattr(action, "TargetGuid", "")),
                            "guid2": _string(getattr(action, "TargetGuid2", "")),
                            "pos_x": _int(getattr(action, "PosX", -1), -1),
                            "pos_y": _int(getattr(action, "PosY", -1), -1),
                        },
                    }
                )

            state_vector = _to_float_list(getattr(frame, "StateVector", None))
            action_feature_vectors = _to_float_matrix(getattr(frame, "ActionFeatureVectors", None))

            snapshot = {
                "turn": _int(getattr(frame, "Turn", self._turn_counter), self._turn_counter),
                "active_player": _string(getattr(frame, "ActivePlayerId", "")),
                "result": _string(getattr(frame, "Result", "Ongoing")),
                "winner_id": _string(getattr(frame, "WinnerId", "")),
                "players": players,
                "board": board,
                "actions": actions,
                "global_vector": state_vector[:43] if len(state_vector) >= 43 else [],
                "state_vector": state_vector,
                "action_feature_vectors": action_feature_vectors,
            }
            return self._attach_python_observation(snapshot)

        # Fallback legacy reflection path
        data = self._game.Data

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

        return self._attach_python_observation(snapshot)
