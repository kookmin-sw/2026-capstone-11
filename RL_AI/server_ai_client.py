from __future__ import annotations

"""TCP AI player client for the game server JSON packet format."""

import argparse
import random
import socket
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from RL_AI.SeaEngine.action_adapter import choose_action_with_agent
from RL_AI.agents import (
    SeaEngineGreedyAgent,
    SeaEngineRandomAgent,
    SeaEngineRLAgent,
    load_state_dict_flexible,
)
from RL_AI.SeaEngine.observation import STATE_VECTOR_DIM
from RL_AI.server_protocol import (
    FLAG_NONE,
    FLAG_QUERY,
    FLAG_RESPOND,
    HANDLER_GAME_MESSAGE,
    HANDLER_PEER_ENTRANCE,
    AppPacket,
    recv_packet,
    send_packet,
)


def _player_internal_id(raw_id: Any) -> str:
    normalized = str(raw_id or "").strip()
    if normalized in {"P1", "Player1", "1"}:
        return "P1"
    if normalized in {"P2", "Player2", "2"}:
        return "P2"
    return normalized or "P1"


def _role_from_card_id(card_id: str) -> str:
    suffix = str(card_id or "").split("_")[-1].strip()[-1:]
    return {
        "L": "Leader",
        "B": "Bishop",
        "N": "Knight",
        "R": "Rook",
        "P": "Pawn",
    }.get(suffix, "")


def _parse_cell_value(value: Any) -> tuple[int, int]:
    if value is None:
        return -1, -1
    text = str(value).strip()
    if not text:
        return -1, -1
    parts = text.split("/")
    if len(parts) != 2:
        return -1, -1
    try:
        return int(parts[0]), int(parts[1])
    except Exception:
        return -1, -1


def _normalize_target(raw_target: Dict[str, Any]) -> Dict[str, Any]:
    target_type = str(raw_target.get("Type", "None"))
    value = raw_target.get("Value")
    target: Dict[str, Any] = {
        "type": target_type,
        "value": value,
    }
    if target_type == "Cell":
        pos_x, pos_y = _parse_cell_value(value)
        target["pos_x"] = pos_x
        target["pos_y"] = pos_y
    elif target_type in {"Unit", "Card", "Unit2"}:
        target["guid"] = str(value or "")
    else:
        target["guid"] = str(value or "")
    return target


def _normalize_board_card(raw_card: Dict[str, Any]) -> Dict[str, Any]:
    card_id = str(raw_card.get("Id", ""))
    owner = _player_internal_id(raw_card.get("Owner"))
    is_placed = bool(raw_card.get("isPlaced", False))
    pos_x = int(raw_card.get("X", -1))
    pos_y = int(raw_card.get("Y", -1))
    hp = float(raw_card.get("Hp", 0))
    max_hp = float(raw_card.get("MaxHp", max(hp, 1)))
    atk = float(raw_card.get("Atk", 0))
    uid = str(raw_card.get("Uid", ""))
    return {
        "uid": uid,
        "card_id": card_id,
        "name": card_id,
        "owner": owner,
        "is_placed": is_placed,
        "is_moved": bool(raw_card.get("isMoved", False)),
        "pos_x": pos_x,
        "pos_y": pos_y,
        "atk": atk,
        "effective_atk": atk,
        "hp": hp,
        "max_hp": max_hp,
        "buffs": list(raw_card.get("Buff", [])),
        "statuses": [],
        "role": _role_from_card_id(card_id),
    }


def _cards_for_uids(uids: Sequence[str], board_by_uid: Dict[str, Dict[str, Any]]) -> list[Dict[str, Any]]:
    cards = []
    for uid in uids:
        card = board_by_uid.get(str(uid))
        if card is not None:
            cards.append(dict(card))
    return cards


def server_json_to_snapshot(packet_json: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(packet_json.get("Data", packet_json) or {})
    actions_raw = list(packet_json.get("Actions", []))

    board = [_normalize_board_card(card) for card in data.get("Board", [])]
    board_by_uid = {str(card["uid"]): card for card in board if card.get("uid")}

    p1_raw = dict(data.get("Player1", {}) or {})
    p2_raw = dict(data.get("Player2", {}) or {})
    p1_hand_uids = list(p1_raw.get("Hand", []))
    p1_deck_uids = list(p1_raw.get("Deck", []))
    p1_trash_uids = list(p1_raw.get("Trash", []))
    p2_hand_uids = list(p2_raw.get("Hand", []))
    p2_deck_uids = list(p2_raw.get("Deck", []))
    p2_trash_uids = list(p2_raw.get("Trash", []))

    players = [
        {
            "id": "P1",
            "server_id": str(p1_raw.get("Id", "Player1")),
            "hand": _cards_for_uids(p1_hand_uids, board_by_uid),
            "deck": _cards_for_uids(p1_deck_uids, board_by_uid),
            "trash": _cards_for_uids(p1_trash_uids, board_by_uid),
        },
        {
            "id": "P2",
            "server_id": str(p2_raw.get("Id", "Player2")),
            "hand": _cards_for_uids(p2_hand_uids, board_by_uid),
            "deck": _cards_for_uids(p2_deck_uids, board_by_uid),
            "trash": _cards_for_uids(p2_trash_uids, board_by_uid),
        },
    ]

    actions = []
    for raw_action in actions_raw:
        action = {
            "uid": str(raw_action.get("Uid", "")),
            "effect_id": str(raw_action.get("EffectId", "")),
            "source": str(raw_action.get("Source", "")),
            "target": _normalize_target(dict(raw_action.get("Target", {}) or {})),
            "text": str(raw_action.get("Text", raw_action.get("EffectId", ""))),
            "raw": raw_action,
        }
        actions.append(action)

    snapshot = {
        "players": players,
        "board": board,
        "actions": actions,
        "active_player": _player_internal_id(data.get("ActivePlayerId", packet_json.get("ActivePlayerId", "Player1"))),
        "turn": int(data.get("Turn", packet_json.get("Turn", 1)) or 1),
        "result": str(data.get("Result", packet_json.get("Result", "Ongoing"))),
        "winner_id": _player_internal_id(data.get("WinnerId", packet_json.get("WinnerId", ""))) if data.get("WinnerId") or packet_json.get("WinnerId") else "",
        "server_data": packet_json,
        "server_data_flat": data,
    }
    return snapshot


def _load_rl_agent(*, model_path: str, device: str = "auto", seed: Optional[int] = None) -> SeaEngineRLAgent:
    import torch

    def _extract_zip_model(zip_path: Path) -> Path:
        cache_root = Path.home() / ".rl_ai_model_cache"
        cache_root.mkdir(parents=True, exist_ok=True)
        signature = f"{zip_path.resolve()}|{zip_path.stat().st_size}|{zip_path.stat().st_mtime_ns}"
        extract_dir = cache_root / zip_path.stem / signature.replace(":", "_").replace("|", "_").replace("\\", "_").replace("/", "_")
        marker = extract_dir / ".extracted"
        if not marker.exists():
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)
            marker.write_text(signature, encoding="utf-8")
        pt_candidates = sorted(extract_dir.rglob("*.pt"), key=lambda p: p.stat().st_mtime)
        if not pt_candidates:
            raise FileNotFoundError(f"No .pt model found inside zip: {zip_path}")
        preferred = [p for p in pt_candidates if p.name == "model_ep_10000.pt"]
        return preferred[-1] if preferred else pt_candidates[-1]

    resolved_device = device
    if device == "auto":
        resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
    agent = SeaEngineRLAgent(seed=seed, device=resolved_device, sample_actions=False)
    agent.ensure_model(state_dim=STATE_VECTOR_DIM)
    assert agent.model is not None
    model_file = Path(model_path)
    if model_file.suffix.lower() == ".zip":
        model_file = _extract_zip_model(model_file)
    state_dict = torch.load(model_file, map_location=agent.device)
    load_state_dict_flexible(agent.model, state_dict)
    agent.model.eval()
    return agent


class ServerAiClient:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        mode: str = "rl",
        model_path: Optional[str] = None,
        player_name: str = "AI Player",
        seed: Optional[int] = None,
        device: str = "auto",
        card_data_path: Optional[str] = None,
        verbose: bool = True,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.mode = str(mode).strip().lower()
        self.model_path = model_path
        self.player_name = player_name
        self.seed = seed
        self.device = device
        self.card_data_path = card_data_path
        self.verbose = verbose
        self.rng = random.Random(seed)
        self.agent = self._build_agent()

    def _build_agent(self):
        if self.mode == "random":
            return SeaEngineRandomAgent(seed=self.seed)
        if self.mode == "greedy":
            return SeaEngineGreedyAgent(seed=self.seed)
        if self.mode == "rl":
            if not self.model_path:
                raise ValueError("mode=rl requires --model-path")
            return _load_rl_agent(model_path=self.model_path, device=self.device, seed=self.seed)
        raise ValueError(f"Unsupported mode: {self.mode}")

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    def _choose_action_uid(self, snapshot: Dict[str, Any]) -> str:
        legal_actions = list(snapshot.get("actions", []))
        if not legal_actions:
            return ""
        _, action = choose_action_with_agent(self.agent, snapshot)
        return str(action.get("uid", ""))

    def run(self) -> None:
        with socket.create_connection((self.host, self.port)) as sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            time.sleep(1.0)
            self._log(f"connected to {self.host}:{self.port} | mode={self.mode}")
            send_packet(sock, FLAG_NONE, HANDLER_PEER_ENTRANCE, 0, self.player_name)
            self._log(f"sent peer entrance: {self.player_name}")

            while True:
                try:
                    packet = recv_packet(sock)
                except ConnectionError:
                    self._log("server closed the connection")
                    break

                if packet.handler_num != HANDLER_GAME_MESSAGE:
                    self._log(f"ignore handler={packet.handler_num} flag={packet.flag} query={packet.query_num}")
                    continue

                try:
                    packet_json = packet.json_payload()
                except Exception as exc:
                    self._log(f"failed to parse JSON payload: {exc}")
                    continue

                snapshot = server_json_to_snapshot(packet_json)
                self._log(
                    f"turn={snapshot['turn']} active={snapshot['active_player']} result={snapshot['result']} "
                    f"actions={len(snapshot.get('actions', []))} flag={packet.flag} query={packet.query_num}"
                )

                if packet.is_query() or packet.flag == FLAG_NONE:
                    action_uid = self._choose_action_uid(snapshot)
                    if not action_uid:
                        self._log("no legal action uid found; sending empty response")
                    send_packet(sock, FLAG_RESPOND, HANDLER_GAME_MESSAGE, packet.query_num, action_uid)
                    self._log(f"responded with uid={action_uid}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SeaEngine server AI client")
    parser.add_argument("host", help="game server IP/hostname")
    parser.add_argument("port", type=int, help="game server port")
    parser.add_argument("--mode", choices=["rl", "greedy", "random"], default="rl")
    parser.add_argument("--model-path", help="model checkpoint path for rl mode")
    parser.add_argument("--player-name", default="AI Player")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--card-data-path", default=None)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    client = ServerAiClient(
        args.host,
        args.port,
        mode=args.mode,
        model_path=args.model_path,
        player_name=args.player_name,
        seed=args.seed,
        device=args.device,
        card_data_path=args.card_data_path,
        verbose=not args.quiet,
    )
    client.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
