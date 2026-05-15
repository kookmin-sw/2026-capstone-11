"""Helpers for selecting and describing actions from SeaEngine snapshots."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def get_legal_actions(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(snapshot.get("actions", []))


def describe_action(action: Dict[str, Any]) -> str:
    return str(action.get("text", ""))


def choose_action_with_agent(agent, snapshot: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    actions = get_legal_actions(snapshot)
    return agent.select_action(snapshot, actions)
