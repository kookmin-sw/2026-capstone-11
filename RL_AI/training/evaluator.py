"""Evaluation loop for agents running on the C# SeaEngine backend."""

from __future__ import annotations

import os
from collections import Counter
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from RL_AI.SeaEngine.action_adapter import choose_action_with_agent
from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession
from RL_AI.analysis.reports import build_win_rate_report, save_report
from RL_AI.training.start_state import burn_in_to_deficit_mode

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


def _label_code(label: str, *, default: str = "X") -> str:
    normalized = str(label or "").strip()
    if not normalized:
        return default
    mapping = {
        "선공": "F",
        "후공": "S",
        "First": "F",
        "Second": "S",
        "귤": "O",
        "Orange": "O",
        "샤를로테": "C",
        "Charlotte": "C",
        "Teach": "T",
        "Balance": "B",
        "Self": "S",
        "Greedy": "G",
        "Random": "R",
    }
    if normalized in mapping:
        return mapping[normalized]
    for ch in normalized:
        if ch.isalnum():
            return ch.upper()
    return default


def _build_game_id(match_context: Optional[Dict[str, Any]], match_index: int) -> str:
    ctx = match_context or {}
    side_code = _label_code(str(ctx.get("side", ctx.get("side_label", ""))), default="F")
    self_code = _label_code(str(ctx.get("self_deck", ctx.get("rl_deck", ctx.get("self_deck_label", "")))), default="X")
    opp_code = _label_code(str(ctx.get("opp_deck", ctx.get("opp_deck_label", ""))), default="X")
    mode_code = _label_code(str(ctx.get("mode", ctx.get("mode_label", ""))), default="T")
    return f"{side_code}{self_code}{opp_code}{mode_code}{match_index}"


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
    logger_mode: str = "simple",
    start_mode: str = "normal",
    start_focus_player: str = "P1",
) -> Dict[str, object]:
    owns_session = session is None
    if session is None:
        session = PythonNetSession(card_data_path=card_data_path)
        session.start()
    p1_context = p1_agent.sampling_mode(False) if hasattr(p1_agent, "sampling_mode") else nullcontext()
    p2_context = p2_agent.sampling_mode(False) if hasattr(p2_agent, "sampling_mode") else nullcontext()
    try:
        with p1_context, p2_context:
            snapshot = session.init_game(player1_deck=player1_deck, player2_deck=player2_deck, logger_mode=logger_mode)
            if str(start_mode or "normal").strip().lower() != "normal":
                from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRandomAgent

                warmup_focus = SeaEngineRandomAgent(seed=0)
                warmup_enemy = SeaEngineGreedyAgent(seed=1)
                snapshot, _ = burn_in_to_deficit_mode(
                    session,
                    focus_player_id=start_focus_player,
                    target_mode=start_mode,
                    focus_agent=warmup_focus,
                    enemy_agent=warmup_enemy,
                )
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

            engine_log = session.consume_engine_log()
            return {
                "snapshot": snapshot,
                "steps": steps,
                "final_turn": snapshot["turn"],
                "action_type_counts": dict(sorted(action_type_counts.items())),
                "card_use_counts": dict(card_use_counts.most_common()),
                "history": history if include_history else [],
                "engine_log": "",
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
    history_limit: Optional[int] = None,
    match_context: Optional[Dict[str, Any]] = None,
    logger_mode: str = "simple",
    start_mode: str = "normal",
    start_focus_player: str = "P1",
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
            capture_history = include_history and (history_limit is None or match_index < history_limit)
            result = play_evaluation_match(
                p1_agent,
                p2_agent,
                session=session,
                card_data_path=card_data_path,
                player1_deck=player1_deck,
                player2_deck=player2_deck,
                max_turns=max_turns,
                include_history=capture_history,
                logger_mode=logger_mode,
                start_mode=start_mode,
                start_focus_player=start_focus_player,
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
            if capture_history:
                context_copy = dict(match_context or {})
                histories.append(
                    {
                        "match_index": match_index + 1,
                        "game_id": _build_game_id(context_copy, match_index + 1),
                        "match_context": context_copy,
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
        desired_history_total = history_limit
        if desired_history_total is None:
            desired_history_total = max(1, round(num_matches / 5))
        summary["histories"] = _select_representative_histories(histories, desired_history_total)
    report_text = build_win_rate_report(summary)
    saved_path = save_report(report_text, _default_evaluation_report_path() if report_path is None else report_path)
    summary["report_path"] = str(saved_path)
    return summary


def _select_representative_histories(
    histories: list[Dict[str, object]],
    desired_total: Optional[int],
) -> list[Dict[str, object]]:
    if not histories:
        return []
    if desired_total is None or desired_total <= 0:
        return list(histories)
    if desired_total >= len(histories):
        return list(histories)

    grouped: Dict[str, list[Dict[str, object]]] = {}
    for item in histories:
        grouped.setdefault(str(item.get("result", "")), []).append(item)

    non_empty = [key for key, items in grouped.items() if items]
    target_total = max(int(desired_total), len(non_empty))
    target_total = min(target_total, len(histories))

    raw_targets: Dict[str, float] = {}
    base_targets: Dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    for key, items in grouped.items():
        if not items:
            continue
        exact = target_total * (len(items) / len(histories))
        raw_targets[key] = exact
        base = int(exact)
        if base <= 0:
            base = 1
        base_targets[key] = min(base, len(items))
        remainders.append((exact - int(exact), key))

    allocated = sum(base_targets.values())
    if allocated < target_total:
        for _, key in sorted(remainders, key=lambda pair: (-pair[0], pair[1])):
            if allocated >= target_total:
                break
            if base_targets[key] >= len(grouped[key]):
                continue
            base_targets[key] += 1
            allocated += 1
    elif allocated > target_total:
        for _, key in sorted(remainders, key=lambda pair: (pair[0], pair[1])):
            if allocated <= target_total:
                break
            if base_targets[key] <= 1:
                continue
            base_targets[key] -= 1
            allocated -= 1

    selected: list[Dict[str, object]] = []
    for key, items in grouped.items():
        quota = min(base_targets.get(key, 0), len(items))
        if quota <= 0:
            continue
        if quota >= len(items):
            selected.extend(items)
            continue
        if quota == 1:
            indices = [0]
        else:
            step = (len(items) - 1) / float(quota - 1)
            indices = sorted({int(round(i * step)) for i in range(quota)})
            while len(indices) < quota:
                for idx in range(len(items)):
                    if idx not in indices:
                        indices.append(idx)
                        if len(indices) >= quota:
                            break
            indices = sorted(indices[:quota])
        selected.extend(items[idx] for idx in indices)

    selected.sort(key=lambda item: int(item.get("match_index", 0)))
    return selected
