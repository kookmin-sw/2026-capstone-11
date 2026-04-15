"""Evaluation loop for agents running on the C# SeaEngine backend."""

from __future__ import annotations

import os
from collections import Counter
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from RL_AI.SeaEngine.action_adapter import choose_action_with_agent
from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession
from RL_AI.analysis.reports import build_win_rate_report, save_report

_VERBOSE_EVAL_MATCH_LOG = os.getenv("SEAENGINE_VERBOSE_EVAL_MATCH_LOG", "0") == "1"


def _default_evaluation_report_path(prefix: str = "se_eval") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.txt"


def _winner_to_counts(result: str) -> tuple[int, int, int]:
    if result == "Player1Win":
        return 1, 0, 0
    if result == "Player2Win":
        return 0, 1, 0
    return 0, 0, 1


def play_evaluation_match(
    p1_agent,
    p2_agent,
    *,
    session: Optional[PythonNetSession] = None,
    card_data_path: Optional[str] = None,
    player1_deck: str = "",
    player2_deck: str = "",
    max_turns: int = 100,
    include_history: bool = False,
) -> Dict[str, object]:
    owns_session = session is None
    if session is None:
        session = PythonNetSession(card_data_path=card_data_path)
        session.start()
    p1_context = p1_agent.sampling_mode(False) if hasattr(p1_agent, "sampling_mode") else nullcontext()
    p2_context = p2_agent.sampling_mode(False) if hasattr(p2_agent, "sampling_mode") else nullcontext()
    try:
        with p1_context, p2_context:
            snapshot = session.init_game(player1_deck=player1_deck, player2_deck=player2_deck)
            agents = {"P1": p1_agent, "P2": p2_agent}
            action_type_counts: Counter[str] = Counter()
            card_use_counts: Counter[str] = Counter()
            history: list[str] = []
            steps = 0

            while snapshot["result"] == "Ongoing" and snapshot["turn"] <= max_turns:
                actions = snapshot.get("actions", [])
                if not actions:
                    break

                active_player = snapshot["active_player"]
                acting_agent = agents[active_player]
                _, action = choose_action_with_agent(acting_agent, snapshot)

                effect_id = str(action.get("effect_id", ""))
                action_type_counts[effect_id] += 1

                source_uid = action.get("source", "")
                source_card = next((card for card in snapshot.get("board", []) if card.get("uid") == source_uid), None)
                if effect_id not in {"DefaultMove", "DefaultAttack", "TurnEnd"} and source_card is not None:
                    card_use_counts[str(source_card.get("name", source_card.get("card_id", source_uid)))] += 1

                if include_history:
                    target = action.get("target", {})
                    source_name = "" if source_card is None else str(source_card.get("name", source_card.get("card_id", source_uid)))
                    history.append(
                        f"T{snapshot['turn']:>3} {active_player} {effect_id} "
                        f"{source_name} -> {target.get('type', 'None')} "
                        f"({action['uid']})"
                    )

                snapshot = session.apply_action(action["uid"])
                steps += 1

            return {
                "snapshot": snapshot,
                "steps": steps,
                "final_turn": snapshot["turn"],
                "action_type_counts": dict(sorted(action_type_counts.items())),
                "card_use_counts": dict(card_use_counts.most_common()),
                "history": history if include_history else [],
            }
    finally:
        if owns_session:
            session.close()


def evaluate_agents(
    p1_agent,
    p2_agent,
    *,
    num_matches: int,
    card_data_path: Optional[str] = None,
    player1_deck: str = "",
    player2_deck: str = "",
    max_turns: int = 100,
    report_path: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    include_history: bool = False,
) -> Dict[str, object]:
    p1_wins = 0
    p2_wins = 0
    draws = 0
    total_steps = 0
    total_final_turns = 0
    action_type_counts: Counter[str] = Counter()
    card_use_counts: Counter[str] = Counter()
    histories: list[Dict[str, object]] = []

    session = PythonNetSession(card_data_path=card_data_path)
    session.start()
    try:
        for match_index in range(num_matches):
            result = play_evaluation_match(
                p1_agent,
                p2_agent,
                session=session,
                card_data_path=card_data_path,
                player1_deck=player1_deck,
                player2_deck=player2_deck,
                max_turns=max_turns,
                include_history=include_history,
            )
            snapshot = result["snapshot"]
            w1, w2, d = _winner_to_counts(str(snapshot["result"]))
            p1_wins += w1
            p2_wins += w2
            draws += d
            total_steps += int(result["steps"])
            total_final_turns += int(result["final_turn"])
            action_type_counts.update(result["action_type_counts"])
            card_use_counts.update(result["card_use_counts"])
            if include_history:
                histories.append(
                    {
                        "match_index": match_index + 1,
                        "result": str(snapshot["result"]),
                        "steps": int(result["steps"]),
                        "final_turn": int(result["final_turn"]),
                        "history": list(result["history"]),
                    }
                )
            
            if _VERBOSE_EVAL_MATCH_LOG:
                print(f"  [Match {match_index + 1}/{num_matches}] Result: {snapshot['result']} | Steps: {result['steps']}")
            
            if progress_callback is not None:
                progress_callback(
                    match_index + 1,
                    num_matches,
                    str(snapshot["result"]),
                    f"{getattr(p1_agent, 'name', 'P1')} vs {getattr(p2_agent, 'name', 'P2')}",
                )
    finally:
        session.close()

    summary = {
        "episodes": num_matches,
        "p1_agent": getattr(p1_agent, "name", "P1"),
        "p2_agent": getattr(p2_agent, "name", "P2"),
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "draws": draws,
        "avg_steps": 0.0 if num_matches == 0 else total_steps / num_matches,
        "avg_final_turn": 0.0 if num_matches == 0 else total_final_turns / num_matches,
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "card_use_counts": dict(card_use_counts.most_common()),
    }
    if include_history:
        summary["histories"] = histories
    report_text = build_win_rate_report(summary)
    saved_path = save_report(report_text, _default_evaluation_report_path() if report_path is None else report_path)
    summary["report_path"] = str(saved_path)
    return summary
