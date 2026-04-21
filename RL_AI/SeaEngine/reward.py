"""Terminal reward helpers for SeaEngine-backed training."""

from __future__ import annotations


def terminal_reward_for_player(result: str, player_id: str) -> float:
    if result in {"Draw", "Ongoing"}:
        return 0.0
    if result == "Player1Win":
        return 1.0 if player_id == "P1" else -1.0
    if result == "Player2Win":
        return 1.0 if player_id == "P2" else -1.0
    return 0.0
