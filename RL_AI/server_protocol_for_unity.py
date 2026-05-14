from __future__ import annotations

"""TCP app-level packet helpers — Unity 연동용 (standalone)."""

from dataclasses import dataclass
import json
import socket
import struct
from typing import Any, Dict

APP_HEADER_STRUCT = struct.Struct("<Iiii")
LENGTH_STRUCT = struct.Struct("<I")

FLAG_NONE    = 0x0000_0000
FLAG_CONTROL = 0x0000_0001
FLAG_RESPOND = 0x0000_0001 << 1
FLAG_QUERY   = 0x0000_0001 << 2
FLAG_CRYPTO  = 0x0000_0001 << 3

HANDLER_GAME_MESSAGE  = 6
HANDLER_PEER_ENTRANCE = 7
# ======================================================
# [추가] Unity 연결 흐름용 핸들러 ID
# ======================================================
HANDLER_GAME_READY         = 11
HANDLER_GAME_DATA_REGISTER = 12

# AI mode aliases are kept here so Unity-side clients can share the
# same strings without hardcoding them in multiple places.
AI_MODE_RANDOM = "random"
AI_MODE_GREEDY = "greedy"
AI_MODE_RULE_BASED = "rule_based"
AI_MODE_RL = "rl"
AI_MODE_BELIEF_MCTS = "belief_mcts"


@dataclass(frozen=True)
class AppPacket:
    total_size: int
    flag: int
    handler_num: int
    query_num: int
    reserved: int
    payload: bytes

    def is_query(self) -> bool:
        return bool(self.flag & FLAG_QUERY)

    def is_response(self) -> bool:
        return bool(self.flag & FLAG_RESPOND)

    def payload_text(self) -> str:
        return self.payload.decode("utf-8", errors="replace")

    def json_payload(self) -> Dict[str, Any]:
        text = self.payload_text().strip()
        if not text:
            return {}
        return json.loads(text)


def encode_packet(flag: int, handler_num: int, query_num: int, payload: bytes | str) -> bytes:
    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        payload_bytes = payload
    total_size = APP_HEADER_STRUCT.size + len(payload_bytes)
    return LENGTH_STRUCT.pack(total_size) + APP_HEADER_STRUCT.pack(int(flag), int(handler_num), int(query_num), 0) + payload_bytes


def encode_json_packet(flag: int, handler_num: int, query_num: int, payload_obj: Dict[str, Any]) -> bytes:
    payload = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return encode_packet(flag, handler_num, query_num, payload)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("socket closed while reading packet")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_packet(sock: socket.socket) -> AppPacket:
    length_bytes = recv_exact(sock, LENGTH_STRUCT.size)
    (total_size,) = LENGTH_STRUCT.unpack(length_bytes)
    if total_size < APP_HEADER_STRUCT.size:
        raise ValueError(f"invalid packet size: {total_size}")
    body = recv_exact(sock, total_size)
    flag, handler_num, query_num, reserved = APP_HEADER_STRUCT.unpack(body[:APP_HEADER_STRUCT.size])
    payload = body[APP_HEADER_STRUCT.size:]
    return AppPacket(
        total_size=int(total_size),
        flag=int(flag),
        handler_num=int(handler_num),
        query_num=int(query_num),
        reserved=int(reserved),
        payload=payload,
    )


def send_packet(sock: socket.socket, flag: int, handler_num: int, query_num: int, payload: bytes | str) -> None:
    sock.sendall(encode_packet(flag, handler_num, query_num, payload))


def send_json_packet(sock: socket.socket, flag: int, handler_num: int, query_num: int, payload_obj: Dict[str, Any]) -> None:
    sock.sendall(encode_json_packet(flag, handler_num, query_num, payload_obj))


# ======================================================
# [추가] SimpleReq / SimpleRsp 인코딩·디코딩 헬퍼
#   SimpleReq  payload : Int32(len) + UTF-8 bytes
#   SimpleRsp  payload : Int32(result) + Int32(len) + UTF-8 bytes
# ======================================================

def encode_simple_req(msg: str) -> bytes:
    """SimpleReq 포맷으로 문자열을 직렬화한다."""
    msg_bytes = msg.encode("utf-8")
    return struct.pack("<I", len(msg_bytes)) + msg_bytes


def decode_simple_rsp(payload: bytes) -> dict:
    """SimpleRsp 페이로드를 역직렬화한다.
    반환값: {"result": int, "msg": str}  (result==0 → Accepted)
    """
    result  = struct.unpack_from("<i", payload, 0)[0]
    msg_len = struct.unpack_from("<I", payload, 4)[0]
    msg     = payload[8: 8 + msg_len].decode("utf-8") if msg_len > 0 else ""
    return {"result": result, "msg": msg}
