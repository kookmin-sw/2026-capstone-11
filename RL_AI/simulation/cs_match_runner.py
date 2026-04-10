"""Run matches against the copied C# SeaEngine backend inside RL_AI."""

from __future__ import annotations

import random
from typing import Any, Dict, Optional

from RL_AI.SeaEngine.action_adapter import choose_action_with_agent
from RL_AI.SeaEngine.bridge.seaengine_session import SeaEngineSession


def _find_action_by_uid(snapshot: Dict[str, Any], action_uid: str) -> Dict[str, Any]:
    for action in snapshot.get("actions", []):
        if action["uid"] == action_uid:
            return action
    raise KeyError(f"Action uid not found: {action_uid}")


def print_cs_snapshot(snapshot: Dict[str, Any]) -> None:
    print(
        f"Turn={snapshot['turn']} Active={snapshot['active_player']} "
        f"Result={snapshot['result']} Winner={snapshot.get('winner_id') or '-'}"
    )
    print("Board:")
    for card in snapshot.get("board", []):
        if not card["is_placed"]:
            continue
        pos = f"({card['pos_x']},{card['pos_y']})"
        print(
            f"  {card['owner']} {card['name']}[{card['card_id']}] {pos} "
            f"ATK={card['effective_atk']} HP={card['hp']}/{card['max_hp']}"
        )
    print("Actions:")
    for idx, action in enumerate(snapshot.get("actions", [])):
        print(f"  [{idx}] {action['uid']} {action['effect_id']} {action['text']}")


def run_cs_random_match(
    *,
    seed: Optional[int] = None,
    max_turns: int = 100,
    card_data_path: Optional[str] = None,
    player1_deck: str = "",
    player2_deck: str = "",
    print_steps: bool = True,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    session = SeaEngineSession(card_data_path=card_data_path)
    session.start()
    try:
        snapshot = session.init_game(player1_deck=player1_deck, player2_deck=player2_deck)
        while snapshot["result"] == "Ongoing" and snapshot["turn"] <= max_turns:
            actions = snapshot.get("actions", [])
            if not actions:
                break
            chosen = rng.choice(actions)
            if print_steps:
                print(f"[turn {snapshot['turn']}] {snapshot['active_player']} -> {chosen['text']}")
            snapshot = session.apply_action(chosen["uid"])

        if print_steps:
            print_cs_snapshot(snapshot)
        return snapshot
    finally:
        session.close()


def run_cs_manual_match(
    *,
    card_data_path: Optional[str] = None,
    player1_deck: str = "",
    player2_deck: str = "",
) -> Dict[str, Any]:
    session = SeaEngineSession(card_data_path=card_data_path)
    session.start()
    try:
        snapshot = session.init_game(player1_deck=player1_deck, player2_deck=player2_deck)
        while snapshot["result"] == "Ongoing":
            print_cs_snapshot(snapshot)
            actions = snapshot.get("actions", [])
            if not actions:
                break
            raw = input("Select action index (or q): ").strip()
            if raw.lower() in {"q", "quit", "exit"}:
                break
            if not raw.isdigit():
                print("Please enter a numeric index.")
                continue
            idx = int(raw)
            if idx < 0 or idx >= len(actions):
                print("Index out of range.")
                continue
            snapshot = session.apply_action(actions[idx]["uid"])

        print_cs_snapshot(snapshot)
        return snapshot
    finally:
        session.close()


def run_cs_agent_match(
    p1_agent,
    p2_agent,
    *,
    seed: Optional[int] = None,
    max_turns: int = 100,
    card_data_path: Optional[str] = None,
    player1_deck: str = "",
    player2_deck: str = "",
    print_steps: bool = True,
) -> Dict[str, Any]:
    random.Random(seed)
    session = SeaEngineSession(card_data_path=card_data_path)
    session.start()
    try:
        snapshot = session.init_game(player1_deck=player1_deck, player2_deck=player2_deck)
        agents = {"P1": p1_agent, "P2": p2_agent}
        while snapshot["result"] == "Ongoing" and snapshot["turn"] <= max_turns:
            actions = snapshot.get("actions", [])
            if not actions:
                break
            acting_agent = agents[snapshot["active_player"]]
            _, chosen = choose_action_with_agent(acting_agent, snapshot)
            if print_steps:
                print(f"[turn {snapshot['turn']}] {snapshot['active_player']}:{acting_agent.name} -> {chosen['text']}")
            snapshot = session.apply_action(chosen["uid"])

        if print_steps:
            print_cs_snapshot(snapshot)
        return snapshot
    finally:
        session.close()


if __name__ == "__main__":
    run_cs_manual_match()
