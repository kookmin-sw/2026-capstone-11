from __future__ import annotations

import json
import socket
import threading

from RL_AI.server_ai_client import server_json_to_snapshot
from RL_AI.server_protocol import (
    FLAG_NONE,
    FLAG_QUERY,
    FLAG_RESPOND,
    HANDLER_GAME_MESSAGE,
    HANDLER_PEER_ENTRANCE,
    encode_packet,
    recv_packet,
    send_packet,
)


def test_packet_roundtrip_header_and_payload():
    payload = b'{"ok":true}'
    packet = encode_packet(FLAG_QUERY, HANDLER_GAME_MESSAGE, 17, payload)

    server_sock, client_sock = socket.socketpair()
    try:
        client_sock.sendall(packet)
        parsed = recv_packet(server_sock)
        assert parsed.flag == FLAG_QUERY
        assert parsed.handler_num == HANDLER_GAME_MESSAGE
        assert parsed.query_num == 17
        assert parsed.payload == payload
    finally:
        server_sock.close()
        client_sock.close()


def test_server_json_to_snapshot_normalizes_server_payload():
    packet_json = {
        "Data": {
            "Player1": {"Id": "Player1", "Hand": ["C000"], "Deck": ["C001"], "Trash": []},
            "Player2": {"Id": "Player2", "Hand": ["C002"], "Deck": ["C003"], "Trash": []},
            "Board": [
                {"Uid": "C000", "Id": "Or_L", "Owner": "Player1", "isPlaced": True, "isMoved": False, "X": 0, "Y": 2, "Atk": 3, "Hp": 9, "MaxHp": 9, "Buff": []},
                {"Uid": "C001", "Id": "Or_P", "Owner": "Player1", "isPlaced": False, "isMoved": False, "X": -1, "Y": -1, "Atk": 1, "Hp": 1, "MaxHp": 1, "Buff": []},
                {"Uid": "C002", "Id": "Cl_P", "Owner": "Player2", "isPlaced": False, "isMoved": False, "X": -1, "Y": -1, "Atk": 1, "Hp": 1, "MaxHp": 1, "Buff": []},
            ],
            "ActivePlayerId": "Player1",
        },
        "Actions": [
            {"Uid": "A000", "EffectId": "DefaultMove", "Source": "C000", "Target": {"Type": "Cell", "Value": "1/1"}},
            {"Uid": "A001", "EffectId": "Or_L", "Source": "C000", "Target": {"Type": "Unit", "Value": "C000"}},
        ],
    }

    snapshot = server_json_to_snapshot(packet_json)
    assert snapshot["active_player"] == "P1"
    assert snapshot["board"][0]["card_id"] == "Or_L"
    assert snapshot["players"][0]["hand"][0]["uid"] == "C000"
    assert snapshot["actions"][0]["target"]["type"] == "Cell"
    assert snapshot["actions"][0]["target"]["pos_x"] == 1
    assert snapshot["actions"][0]["target"]["pos_y"] == 1
    assert snapshot["actions"][1]["target"]["guid"] == "C000"
