"""Evaluation loop for agents running on the C# SeaEngine backend."""

from __future__ import annotations

import json
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


def _deck_label_from_leader(card: Dict[str, Any]) -> str:
    card_id = str(card.get("card_id", card.get("id", "")))
    name = str(card.get("name", ""))
    if card_id.startswith("Or_") or "귤" in name:
        return "Orange"
    if card_id.startswith("Cl_") or "샤를로테" in name or "미스티아" in name:
        return "Charlotte"
    return "Unknown"


def _safe_hp(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _leader_hp_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, object]]:
    by_player: Dict[str, Dict[str, object]] = {}
    for card in snapshot.get("board", []):
        if str(card.get("role", "")) != "Leader":
            continue
        owner = str(card.get("owner", ""))
        if not owner:
            continue
        hp = _safe_hp(card.get("hp", 0.0))
        deck_label = _deck_label_from_leader(card)
        row = {
            "deck": deck_label,
            "hp": hp,
            "card": str(card.get("name", card.get("card_id", ""))),
        }
        by_player[owner] = row
    return by_player


def _update_min_leader_hp(
    min_by_player: Dict[str, Dict[str, object]],
    snapshot: Dict[str, Any],
) -> None:
    for player_id, row in _leader_hp_snapshot(snapshot).items():
        hp = row.get("hp")
        if hp is None:
            continue
        prev = min_by_player.get(player_id)
        if prev is None or float(hp) < float(prev.get("min_hp", hp)):
            min_by_player[player_id] = {
                "deck": row.get("deck", "Unknown"),
                "card": row.get("card", ""),
                "min_hp": float(hp),
            }


def _leader_hp_summary(
    *,
    min_by_player: Dict[str, Dict[str, object]],
    final_snapshot: Dict[str, Any],
) -> Dict[str, object]:
    final_by_player = _leader_hp_snapshot(final_snapshot)
    by_player: Dict[str, Dict[str, object]] = {}
    by_deck: Dict[str, list[Dict[str, object]]] = {}
    player_ids = set(final_by_player.keys()) | set(min_by_player.keys())
    for player_id in sorted(player_ids):
        final_row = final_by_player.get(player_id, {})
        min_row = min_by_player.get(player_id, {})
        row = {
            "deck": final_row.get("deck", min_row.get("deck", "Unknown")),
            "card": final_row.get("card", min_row.get("card", "")),
            "final_hp": final_row.get("hp"),
            "min_hp": min_row.get("min_hp", final_row.get("hp")),
        }
        by_player[player_id] = row
        deck = str(row.get("deck", "Unknown"))
        by_deck.setdefault(deck, []).append({"player": player_id, **row})
    return {
        "leader_hp_by_player": by_player,
        "leader_hp_by_deck": by_deck,
    }


def _numeric_stats(values: list[float]) -> Dict[str, float | int]:
    if not values:
        return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "avg": sum(values) / float(len(values)),
        "min": min(values),
        "max": max(values),
    }


def _resolve_history_capture_indices(num_matches: int, history_limit: Optional[int]) -> tuple[set[int], int]:
    if num_matches <= 0:
        return set(), 0
    desired_total = history_limit
    if desired_total is None:
        desired_total = max(1, round(num_matches / 5))
    desired_total = max(0, min(int(desired_total), num_matches))
    if desired_total <= 0:
        return set(), 0
    if desired_total >= num_matches:
        return set(range(num_matches)), desired_total
    if desired_total == 1:
        return {0}, desired_total
    step = (num_matches - 1) / float(desired_total - 1)
    indices = {int(round(i * step)) for i in range(desired_total)}
    while len(indices) < desired_total:
        for idx in range(num_matches):
            if idx not in indices:
                indices.add(idx)
                if len(indices) >= desired_total:
                    break
    return indices, desired_total


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
    burnin_profile: str = "fixed",
    burnin_seed: Optional[int] = None,
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
            _notify_replay_reset(
                [p1_agent, p2_agent],
                player1_deck=player1_deck,
                player2_deck=player2_deck,
                card_data_path=card_data_path,
                replay_available=True,
            )
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
                    burnin_profile=burnin_profile,
                    burnin_seed=burnin_seed,
                )
                _notify_replay_available([p1_agent, p2_agent], False)
            agents = {"P1": p1_agent, "P2": p2_agent}
            action_type_counts: Counter[str] = Counter()
            card_use_counts: Counter[str] = Counter()
            history: list[str] = []
            steps = 0
            min_leader_hp_by_player: Dict[str, Dict[str, object]] = {}
            _update_min_leader_hp(min_leader_hp_by_player, snapshot)

            while snapshot["result"] == "Ongoing" and snapshot["turn"] <= max_turns:
                _attach_engine_state_if_needed(session, snapshot, [p1_agent, p2_agent])
                actions = snapshot.get("actions", [])
                if not actions:
                    break

                active_player = snapshot["active_player"]
                acting_agent = agents[active_player]
                try:
                    _, action = choose_action_with_agent(acting_agent, snapshot)
                finally:
                    _release_engine_state_if_needed(session, snapshot)
                _notify_observed_transition([p1_agent, p2_agent], snapshot, action)

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
                _update_min_leader_hp(min_leader_hp_by_player, snapshot)
                steps += 1

            engine_log = session.consume_engine_log()
            leader_hp = _leader_hp_summary(min_by_player=min_leader_hp_by_player, final_snapshot=snapshot)
            return {
                "snapshot": snapshot,
                "steps": steps,
                "final_turn": snapshot["turn"],
                "action_type_counts": dict(sorted(action_type_counts.items())),
                "card_use_counts": dict(card_use_counts.most_common()),
                "leader_hp": leader_hp,
                "history": history if include_history else [],
                "engine_log": "",
            }
    finally:
        if owns_session:
            session.close()


def _unique_agents(agents: list[object]) -> list[object]:
    seen: set[int] = set()
    unique: list[object] = []
    for agent in agents:
        ident = id(agent)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(agent)
    return unique


def _notify_replay_reset(
    agents: list[object],
    *,
    player1_deck: str,
    player2_deck: str,
    card_data_path: Optional[str],
    replay_available: bool,
) -> None:
    for agent in _unique_agents(agents):
        reset = getattr(agent, "reset_search_history", None)
        if callable(reset):
            reset(
                player1_deck=player1_deck,
                player2_deck=player2_deck,
                card_data_path=card_data_path,
                replay_available=replay_available,
            )


def _notify_replay_available(agents: list[object], enabled: bool) -> None:
    for agent in _unique_agents(agents):
        setter = getattr(agent, "set_replay_available", None)
        if callable(setter):
            setter(enabled)


def _attach_engine_state_if_needed(session: PythonNetSession, snapshot: Dict[str, object], agents: list[object]) -> None:
    for agent in _unique_agents(agents):
        needs_state = getattr(agent, "requires_engine_state", None)
        if callable(needs_state) and bool(needs_state()):
            try:
                snapshot["_engine_game"] = session.fork_game()
            except Exception:
                snapshot.pop("_engine_game", None)
            return


def _release_engine_state_if_needed(session: PythonNetSession, snapshot: Dict[str, object]) -> None:
    snapshot.pop("_engine_game", None)


def _notify_observed_transition(agents: list[object], snapshot: Dict[str, Any], action: Dict[str, Any]) -> None:
    for agent in _unique_agents(agents):
        observer = getattr(agent, "observe_transition", None)
        if callable(observer):
            observer(snapshot, action)


def _collect_belief_mcts_summary(agent: object) -> Optional[Dict[str, Any]]:
    summary_getter = getattr(agent, "get_search_summary", None)
    if callable(summary_getter):
        try:
            return dict(summary_getter())
        except Exception:
            return None
    inner = getattr(agent, "_belief_agent", None)
    if inner is not None:
        summary_getter = getattr(inner, "get_search_summary", None)
        if callable(summary_getter):
            try:
                return dict(summary_getter())
            except Exception:
                return None
    return None


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
    burnin_profile: str = "fixed",
    burnin_seed: Optional[int] = None,
    save_report_file: bool = True,
) -> Dict[str, object]:
    p1_wins = 0
    p2_wins = 0
    draws = 0
    total_steps = 0
    total_final_turns = 0
    action_type_counts: Counter[str] = Counter()
    card_use_counts: Counter[str] = Counter()
    min_hp_by_player_values: Dict[str, list[float]] = {"P1": [], "P2": []}
    final_hp_by_player_values: Dict[str, list[float]] = {"P1": [], "P2": []}
    min_hp_by_deck_values: Dict[str, list[float]] = {"Orange": [], "Charlotte": []}
    final_hp_by_deck_values: Dict[str, list[float]] = {"Orange": [], "Charlotte": []}
    histories: list[Dict[str, object]] = []
    history_capture_indices, desired_history_total = (
        _resolve_history_capture_indices(num_matches, history_limit) if include_history else (set(), 0)
    )

    session = PythonNetSession(card_data_path=card_data_path)
    session.start()
    try:
        for match_index in range(num_matches):
            capture_history = include_history and match_index in history_capture_indices
            result = play_evaluation_match(
                p1_agent,
                p2_agent,
                session=session,
                card_data_path=card_data_path,
                player1_deck=player1_deck,
                player2_deck=player2_deck,
                max_turns=max_turns,
                include_history=capture_history,
                logger_mode=logger_mode if capture_history else "silent",
                start_mode=start_mode,
                start_focus_player=start_focus_player,
                burnin_profile=burnin_profile,
                burnin_seed=burnin_seed,
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
            leader_hp = dict(result.get("leader_hp", {}) or {})
            leader_hp_by_player = dict(leader_hp.get("leader_hp_by_player", {}) or {})
            for player_id, row_obj in leader_hp_by_player.items():
                row = dict(row_obj or {})
                min_hp = row.get("min_hp")
                final_hp = row.get("final_hp")
                deck = str(row.get("deck", "Unknown"))
                if isinstance(min_hp, (int, float)):
                    min_hp_by_player_values.setdefault(str(player_id), []).append(float(min_hp))
                    if deck in min_hp_by_deck_values:
                        min_hp_by_deck_values[deck].append(float(min_hp))
                if isinstance(final_hp, (int, float)):
                    final_hp_by_player_values.setdefault(str(player_id), []).append(float(final_hp))
                    if deck in final_hp_by_deck_values:
                        final_hp_by_deck_values[deck].append(float(final_hp))
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
                        "leader_hp": leader_hp,
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
        "leader_hp_stats": {
            "min_by_player": {key: _numeric_stats(values) for key, values in sorted(min_hp_by_player_values.items())},
            "final_by_player": {key: _numeric_stats(values) for key, values in sorted(final_hp_by_player_values.items())},
            "min_by_deck": {key: _numeric_stats(values) for key, values in sorted(min_hp_by_deck_values.items())},
            "final_by_deck": {key: _numeric_stats(values) for key, values in sorted(final_hp_by_deck_values.items())},
        },
    }
    belief_mcts_summary: Dict[str, Dict[str, Any]] = {}
    for role, agent in (("p1", p1_agent), ("p2", p2_agent)):
        collected = _collect_belief_mcts_summary(agent)
        if collected:
            belief_mcts_summary[role] = collected
    if belief_mcts_summary:
        summary["belief_mcts_summary"] = belief_mcts_summary
    if include_history:
        summary["histories"] = _select_representative_histories(histories, desired_history_total)
    report_text = build_win_rate_report(summary)
    if belief_mcts_summary:
        lines = [report_text, "", "[Belief MCTS Summary]"]
        for role, stats in belief_mcts_summary.items():
            lines.append(f"- {role}: {json.dumps(stats, ensure_ascii=False, sort_keys=True)}")
        report_text = "\n".join(lines)
    if save_report_file:
        saved_path = save_report(report_text, _default_evaluation_report_path() if report_path is None else report_path)
        summary["report_path"] = str(saved_path)
    else:
        summary["report_path"] = ""
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
