from __future__ import annotations

from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import random
import threading
from pathlib import Path
import time
import zipfile
from typing import Callable, Dict, Optional, Sequence

from RL_AI.SeaEngine.agents import SeaEngineAgent, SeaEngineGreedyAgent, SeaEngineRLAgent, SeaEngineRandomAgent
from RL_AI.SeaEngine.evaluator import evaluate_agents
from RL_AI.SeaEngine.trainer import SeaEnginePPOTrainer
from RL_AI.analysis.reports import build_win_rate_report, save_report


def _default_report_path(prefix: str = "se_te") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.txt"


def _default_log_zip_path(prefix: str = "log") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.zip"


def _default_model_zip_path(prefix: str = "model") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "models" / f"{prefix}_{ts}.zip"


def _scenario_report_path(*, label: str, report_path: Optional[str], prefix: str = "se_eval") -> Path:
    if report_path is None:
        return _default_report_path(f"{prefix}_{_combo_slug(*label.split('/'))}")
    base = Path(report_path)
    return base.with_name(f"{base.stem}_{_combo_slug(*label.split('/'))}.txt")


def _seed_with_offset(seed: Optional[int], offset: int) -> Optional[int]:
    return None if seed is None else seed + offset


def _training_resume_state_path() -> Path:
    return Path(__file__).resolve().parent.parent / "models" / "training_resume_state.json"


def _save_training_resume_state(
    *,
    model_path: Optional[str],
    episodes_completed: int,
    train_episodes: int,
    checkpoint_interval: int,
    save_interval: int,
    seed: Optional[int],
    device: str,
    report_path: Optional[str] = None,
) -> Path:
    payload = {
        "model_path": model_path,
        "episodes_completed": int(episodes_completed),
        "train_episodes": int(train_episodes),
        "checkpoint_interval": int(checkpoint_interval),
        "save_interval": int(save_interval),
        "seed": seed,
        "device": device,
        "report_path": report_path,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = _training_resume_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _zip_new_log_txt_files(
    *,
    since_timestamp: float,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    log_dir = Path(__file__).resolve().parent.parent / "log"
    if not log_dir.exists():
        return None
    txt_files = [
        p for p in log_dir.glob("*.txt")
        if p.is_file() and p.stat().st_mtime >= since_timestamp - 1.0
    ]
    if not txt_files:
        return None
    txt_files.sort(key=lambda p: p.name)
    zip_path = _default_log_zip_path() if output_path is None else output_path
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for txt_file in txt_files:
            zf.write(txt_file, arcname=txt_file.name)
    return zip_path


def _zip_new_model_files(
    *,
    since_timestamp: float,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    model_dir = Path(__file__).resolve().parent.parent / "models"
    if not model_dir.exists():
        return None
    model_files = [
        p for p in model_dir.glob("*.pt")
        if p.is_file() and p.stat().st_mtime >= since_timestamp - 1.0
    ]
    if not model_files:
        return None
    model_files.sort(key=lambda p: p.name)
    zip_path = _default_model_zip_path() if output_path is None else output_path
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for model_file in model_files:
            zf.write(model_file, arcname=model_file.name)
    return zip_path


def _progress_print_interval(total: int) -> int:
    if total <= 100:
        return 100
    if total <= 1000:
        return 250
    return max(500, total // 4)


def _verbose_experiment_logs() -> bool:
    return os.getenv("SEAENGINE_VERBOSE_EXPERIMENT_LOG", "0") == "1"


def _format_plan_counts(counts: Counter[str]) -> str:
    if not counts:
        return "-"
    parts = []
    for key in ("random", "greedy"):
        if key in counts:
            parts.append(f"{key}={counts[key]}")
    for key in sorted(k for k in counts.keys() if k not in {"random", "greedy"}):
        parts.append(f"{key}={counts[key]}")
    return ", ".join(parts)


def _build_training_opponent_schedule(
    *,
    opponent_pool: Sequence[SeaEngineAgent],
    train_episodes: int,
    num_envs: int,
    save_interval: int,
    seed: Optional[int] = None,
) -> tuple[list[str], Counter[str]]:
    rng = random.Random(seed)
    current_pool_names = [agent.name for agent in opponent_pool]
    schedule: list[str] = []
    total_counts: Counter[str] = Counter()

    def _weights_for_progress(progress: float, self_names: list[str]) -> Dict[str, float]:
        # The curriculum keeps greedy in the loop at every stage,
        # while gradually increasing self-play to improve robustness.
        weights: Dict[str, float]
        if progress <= 0.15:
            weights = {"random": 0.65, "greedy": 0.25}
        elif progress <= 0.35:
            weights = {"random": 0.50, "greedy": 0.30}
        elif progress <= 0.60:
            weights = {"random": 0.35, "greedy": 0.30}
        elif progress <= 0.80:
            weights = {"random": 0.25, "greedy": 0.25}
        else:
            weights = {"random": 0.20, "greedy": 0.25}

        if self_names:
            # Use a broader band of recent snapshots to avoid locking onto
            # a tiny set of rote self-play lines.
            recent_self_names = self_names[-12:]
            remaining = max(0.0, 1.0 - sum(weights.values()))
            self_weight = remaining / len(recent_self_names) if recent_self_names and remaining > 0 else 0.0
            for self_name in recent_self_names:
                weights[self_name] = self_weight

        total = sum(weights.values())
        if total <= 0:
            return {"random": 1.0}
        return {name: value / total for name, value in weights.items()}

    for episode_start in range(0, train_episodes, num_envs):
        actual_num_envs = min(num_envs, train_episodes - episode_start)
        progress = (episode_start + actual_num_envs) / max(1, train_episodes)
        self_names = [name for name in current_pool_names if name.startswith("self_ep_")]
        target_weights = _weights_for_progress(progress, self_names)

        weighted_names = []
        weighted_probs = []
        for name in current_pool_names:
            if name in target_weights:
                weighted_names.append(name)
                weighted_probs.append(target_weights[name])

        if not weighted_names:
            weighted_names = list(current_pool_names)
            weighted_probs = [1.0 for _ in weighted_names]

        weight_sum = sum(weighted_probs)
        if weight_sum <= 0:
            weighted_probs = [1.0 / max(1, len(weighted_names)) for _ in weighted_names]
        else:
            weighted_probs = [w / weight_sum for w in weighted_probs]

        batch = rng.choices(weighted_names, weights=weighted_probs, k=actual_num_envs)
        schedule.extend(batch)
        total_counts.update(batch)

        global_episodes = episode_start + actual_num_envs
        if save_interval > 0 and global_episodes % save_interval < actual_num_envs:
            current_pool_names.append(f"self_ep_{global_episodes}")

    return schedule, total_counts


def _build_recovery_schedule(
    *,
    chunk_episodes: int,
    num_envs: int,
    opponent_pool: Sequence[SeaEngineAgent],
    seed: Optional[int],
) -> list[str]:
    rng = random.Random(seed)
    pool_names = [agent.name for agent in opponent_pool]
    self_names = [name for name in pool_names if name.startswith("self_ep_")]
    recent_self = self_names[-8:]
    weights: Dict[str, float] = {"random": 0.40, "greedy": 0.25}
    if recent_self:
        # Recovery should restore stability without reverting to narrow greedy-only tuning.
        weights["random"] = 0.35
        weights["greedy"] = 0.25
        self_weight = 0.40 / len(recent_self)
        for name in recent_self:
            weights[name] = self_weight
    else:
        weights["random"] = 0.55
        weights["greedy"] = 0.45

    weighted_names = []
    weighted_probs = []
    for name in pool_names:
        if name in weights:
            weighted_names.append(name)
            weighted_probs.append(weights[name])
    if not weighted_names:
        return ["random"] * chunk_episodes

    prob_sum = sum(weighted_probs)
    weighted_probs = [w / prob_sum for w in weighted_probs] if prob_sum > 0 else [1.0 / len(weighted_names)] * len(weighted_names)
    schedule: list[str] = []
    for start in range(0, chunk_episodes, num_envs):
        k = min(num_envs, chunk_episodes - start)
        schedule.extend(rng.choices(weighted_names, weights=weighted_probs, k=k))
    return schedule


def _deck_slug(deck_name: str) -> str:
    return {
        "g": "g",
        "귤": "gul",
        "샤를로테": "char",
        "선공": "first",
        "후공": "second",
        "같은 덱": "same",
        "다른 덱": "diff",
        "greedy": "g",
    }.get(deck_name, deck_name.lower().replace(" ", "_"))


def _combo_slug(*parts: str) -> str:
    return "_".join(_deck_slug(part) for part in parts)


def _deck_label_from_json(deck_json: str, *, fallback: str) -> str:
    if not deck_json:
        return fallback
    try:
        cards = json.loads(deck_json)
    except Exception:
        return fallback
    if not isinstance(cards, list):
        return fallback
    card_ids = [str(card) for card in cards if str(card)]
    if any(card_id.startswith("Or_") for card_id in card_ids):
        return "Orange"
    if any(card_id.startswith("Cl_") for card_id in card_ids):
        return "Charlotte"
    if card_ids:
        return card_ids[0].split("_")[0] or fallback
    return fallback


def _resolve_device(device: Optional[str]) -> str:
    requested = "auto" if device is None else str(device).strip().lower()
    if requested in {"auto", ""}:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    if requested in {"cuda", "gpu"}:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    return requested


def _format_match_history(match_history: Dict[str, object]) -> str:
    context = dict(match_history.get("match_context", {}) or {})
    game_id = str(match_history.get("game_id", "")).strip()
    context_desc = []
    for key in ("side_label", "self_deck_label", "opp_deck_label", "relation_label", "mode_label"):
        value = context.get(key)
        if value:
            context_desc.append(f"{key}={value}")
    lines = [
        f"--- Match {int(match_history.get('match_index', 0))} ---",
        f"GameID={game_id}" if game_id else "GameID=",
        f"context={' | '.join(context_desc)}" if context_desc else "context=",
        f"result={match_history.get('result', '')}",
        f"steps={int(match_history.get('steps', 0))}",
        f"final_turn={int(match_history.get('final_turn', 0))}",
    ]
    history = list(match_history.get("history", []))
    if history:
        lines.append("history:")
        lines.extend(f"- {entry}" for entry in history)
    else:
        lines.append("history: []")
    return "\n".join(lines)


def _format_card_use_summary(
    card_use_counts: Dict[str, object],
    *,
    episodes: int,
    avg_steps: float,
    top_k: int = 5,
) -> str:
    counts = Counter({str(card_name): int(count) for card_name, count in card_use_counts.items()})
    if not counts:
        return "-"
    total_card_uses = sum(counts.values())
    total_steps_estimate = max(0.0, float(episodes) * float(avg_steps))
    per_match = 0.0 if episodes <= 0 else total_card_uses / episodes
    per_100_steps = 0.0 if total_steps_estimate <= 0 else (total_card_uses / total_steps_estimate) * 100.0
    parts = [
        f"total={total_card_uses}",
        f"{per_match:.2f}/match",
        f"{per_100_steps:.2f}/100steps",
    ]
    top_parts = []
    for card_name, count in counts.most_common(max(1, top_k)):
        card_per_match = 0.0 if episodes <= 0 else count / episodes
        card_per_100_steps = 0.0 if total_steps_estimate <= 0 else (count / total_steps_estimate) * 100.0
        top_parts.append(f"{card_name}={count} ({card_per_match:.2f}/match, {card_per_100_steps:.2f}/100steps)")
    parts.append("top=" + ", ".join(top_parts))
    return " | ".join(parts)


def _save_history_report(
    *,
    prefix: str,
    title: str,
    summary: Dict[str, object],
    report_path: Optional[str] = None,
) -> Optional[Path]:
    histories = list(summary.get("histories", []))
    if not histories:
        return None
    lines = [
        f"=== {title} ===",
        f"report={summary.get('report_path', '')}",
        "",
        build_win_rate_report(summary),
        "",
    ]
    for match_history in histories:
        lines.append(_format_match_history(match_history))
        lines.append("")
    output_path = _default_report_path(prefix) if report_path is None else Path(report_path)
    return save_report("\n".join(lines).rstrip() + "\n", output_path)


def _run_checkpoint_eval_suite(
    *,
    trainer: SeaEnginePPOTrainer,
    rl_agent: SeaEngineRLAgent,
    greedy_opponent: SeaEngineAgent,
    checkpoint_episodes: int,
    num_matches: int,
    card_data_path: Optional[str],
    train_player1_deck: str,
    train_player2_deck: str,
    max_turns: int,
) -> Dict[str, object]:
    deck_pairs = [
        ("귤", trainer.decks["Orange"]),
        ("샤를로테", trainer.decks["Charlotte"]),
    ]
    combo_results: list[Dict[str, object]] = []
    suite_lines = [f"=== Checkpoint Eval Suite ({num_matches} each, total {num_matches * 8}) ==="]
    history_root = Path(__file__).resolve().parent.parent / "log"

    for rl_deck_name, rl_deck in deck_pairs:
        other_deck_name, other_deck = deck_pairs[1] if rl_deck_name == deck_pairs[0][0] else deck_pairs[0]
        for side_name, rl_is_p1 in [("선공", True), ("후공", False)]:
            for relation_name, use_same_deck in [("같은 덱", True), ("다른 덱", False)]:
                opp_deck = rl_deck if use_same_deck else other_deck
                if rl_is_p1:
                    p1_agent, p2_agent = rl_agent, greedy_opponent
                    p1_deck, p2_deck = rl_deck, opp_deck
                else:
                    p1_agent, p2_agent = greedy_opponent, rl_agent
                    p1_deck, p2_deck = opp_deck, rl_deck

                summary = evaluate_agents(
                    p1_agent,
                    p2_agent,
                    num_matches=num_matches,
                    card_data_path=card_data_path,
                    player1_deck=p1_deck,
                    player2_deck=p2_deck,
                    max_turns=max_turns,
                    include_history=True,
                    match_context={
                        "mode_label": "Teach",
                        "side_label": side_name,
                        "self_deck_label": rl_deck_name,
                        "opp_deck_label": other_deck_name,
                        "relation_label": relation_name,
                    },
                )
                rl_wins = int(summary["p1_wins"] if rl_is_p1 else summary["p2_wins"])
                opp_wins = int(summary["p2_wins"] if rl_is_p1 else summary["p1_wins"])
                combo_label = f"g/{rl_deck_name}/{side_name}/{relation_name}"
                histories = list(summary.get("histories", []))
                history_slug = _combo_slug("g", rl_deck_name, side_name, relation_name)
                history_path = history_root / f"se_ckpt_{checkpoint_episodes}_{history_slug}_hist.txt"
                history_lines = [
                    f"=== Checkpoint {checkpoint_episodes} History ===",
                    f"combo={combo_label}",
                    f"episodes={num_matches}",
                    f"rl_deck={rl_deck_name}",
                    f"side={side_name}",
                    f"relation={relation_name}",
                    f"report={summary['report_path']}",
                    "",
                    build_win_rate_report(summary),
                    "",
                ]
                for match_history in histories:
                    history_lines.append(_format_match_history(match_history))
                    history_lines.append("")
                save_report("\n".join(history_lines).rstrip() + "\n", history_path)

                combo_results.append(
                    {
                        "opponent": "greedy",
                        "rl_deck": rl_deck_name,
                        "side": side_name,
                        "relation": relation_name,
                        "rl_wins": rl_wins,
                        "opp_wins": opp_wins,
                        "draws": int(summary["draws"]),
                        "episodes": int(summary["episodes"]),
                        "summary": summary,
                        "history_path": str(history_path),
                    }
                )
                suite_lines.append(
                    f"- {combo_label}: rl={rl_wins}, opp={opp_wins}, d={int(summary['draws'])}, "
                    f"avg_steps={float(summary['avg_steps']):.1f}, avg_turn={float(summary['avg_final_turn']):.1f}, "
                    f"report={summary['report_path']}, hist={history_path}"
                )

    return {
        "results": combo_results,
        "text": "\n".join(suite_lines),
    }


def _load_saved_rl_agent(
    *,
    model_path: str,
    seed: Optional[int],
    device: Optional[str],
) -> SeaEngineRLAgent:
    import torch

    resolved_device = _resolve_device(device)
    agent = SeaEngineRLAgent(seed=seed, device=resolved_device, sample_actions=False)
    # state_dim = 39 + 14*29 + 7*10 (fixed by observation layout)
    agent.ensure_model(state_dim=515)
    assert agent.model is not None
    state_dict = torch.load(model_path, map_location=agent.device)
    agent.model.load_state_dict(state_dict, strict=True)
    agent.model.eval()
    return agent


def run_saved_model_balance_experiment(
    *,
    model_path: str,
    total_matches: int = 2000,
    max_turns: int = 100,
    card_data_path: Optional[str] = None,
    seed: Optional[int] = None,
    device: Optional[str] = "auto",
    opponent_mode: str = "greedy",
    opponent_model_path: Optional[str] = None,
    include_history: bool = False,
    progress_callback: Optional[Callable[[str, int, int, str, str], None]] = None,
    report_path: Optional[str] = None,
    scenario_workers: int = 1,
) -> Dict[str, object]:
    """
    Evaluate a saved RL model on balance scenarios.
    Default: 2000 matches = 8 scenario combos x 250 matches.
    opponent_mode:
    - "greedy": RL vs Greedy
    - "self": RL vs RL (same model by default, or opponent_model_path if provided)
    """
    resolved_device = _resolve_device(device)
    scenario_worker_count = max(1, int(scenario_workers or 1))
    parallel_scenarios = scenario_worker_count > 1
    opponent_mode_normalized = str(opponent_mode or "greedy").strip().lower()

    def _build_opponent_agent() -> SeaEngineAgent:
        if opponent_mode_normalized in {"self", "rl", "self_play", "selfplay"}:
            if opponent_model_path:
                return _load_saved_rl_agent(
                    model_path=opponent_model_path,
                    seed=_seed_with_offset(seed, 2001),
                    device=resolved_device,
                )
            opponent = _load_saved_rl_agent(
                model_path=model_path,
                seed=_seed_with_offset(seed, 2001),
                device=resolved_device,
            )
            opponent.name = "rl_opp"
            return opponent
        return SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 2001))

    def _build_agents() -> tuple[SeaEngineRLAgent, SeaEngineAgent]:
        rl = _load_saved_rl_agent(model_path=model_path, seed=seed, device=resolved_device)
        opp = _build_opponent_agent()
        return rl, opp

    opponent_tag = "self" if opponent_mode_normalized in {"self", "rl", "self_play", "selfplay"} else "g"
    base_rl_agent, base_opponent_agent = _build_agents() if not parallel_scenarios else (None, None)

    deck_pairs = [
        ("귤", json.dumps(["Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P"])),
        ("샤를로테", json.dumps(["Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P"])),
    ]
    scenarios = []
    for rl_deck_name, rl_deck in deck_pairs:
        other_deck_name, other_deck = deck_pairs[1] if rl_deck_name == deck_pairs[0][0] else deck_pairs[0]
        for side_name, rl_is_p1 in [("선공", True), ("후공", False)]:
            for relation_name, use_same_deck in [("같은 덱", True), ("다른 덱", False)]:
                opp_deck = rl_deck if use_same_deck else other_deck
                if rl_is_p1:
                    p1_deck, p2_deck = rl_deck, opp_deck
                else:
                    p1_deck, p2_deck = opp_deck, rl_deck
                scenarios.append(
                    {
                        "label": f"{opponent_tag}/{rl_deck_name}/{side_name}/{relation_name}",
                        "rl_is_p1": rl_is_p1,
                        "self_deck_name": rl_deck_name,
                        "opp_deck_name": rl_deck_name if use_same_deck else other_deck_name,
                        "p1_deck": p1_deck,
                        "p2_deck": p2_deck,
                    }
                )

    scenario_count = len(scenarios)
    per = total_matches // scenario_count
    rem = total_matches % scenario_count
    aggregate = {
        "episodes": 0,
        "rl_wins": 0,
        "opp_wins": 0,
        "draws": 0,
        "avg_steps_weighted_sum": 0.0,
        "avg_final_turn_weighted_sum": 0.0,
        "action_type_counts": Counter(),
        "card_use_counts": Counter(),
    }
    scenario_results: list[Dict[str, object]] = []
    lines = [
        "=== Saved Model Balance Experiment ===",
        f"model_path={model_path}",
        f"opponent_mode={opponent_mode_normalized}",
        f"opponent_model_path={opponent_model_path or model_path if opponent_tag == 'self' else '-'}",
        f"total_matches={total_matches}",
        f"max_turns={max_turns}",
        f"device={resolved_device}",
        f"scenario_workers={scenario_worker_count}",
        "",
    ]

    def _run_single_scenario(
        idx: int,
        scenario: Dict[str, object],
        scenario_matches: int,
        *,
        rl_agent_local: Optional[SeaEngineRLAgent] = None,
        opponent_agent_local: Optional[SeaEngineAgent] = None,
    ) -> Dict[str, object]:
        if rl_agent_local is None or opponent_agent_local is None:
            rl_agent_local, opponent_agent_local = _build_agents()

        scenario_label = str(scenario["label"])
        scenario_report_path = _scenario_report_path(label=scenario_label, report_path=report_path)

        def _scenario_progress(current: int, total: int, result: str, matchup: str, *, _label: str = scenario_label) -> None:
            if progress_callback is not None:
                progress_callback(_label, current, total, result, matchup)

        summary = evaluate_agents(
            rl_agent_local if scenario["rl_is_p1"] else opponent_agent_local,
            opponent_agent_local if scenario["rl_is_p1"] else rl_agent_local,
            num_matches=scenario_matches,
            card_data_path=card_data_path,
            player1_deck=scenario["p1_deck"],
            player2_deck=scenario["p2_deck"],
            max_turns=max_turns,
            include_history=include_history,
            report_path=str(scenario_report_path),
            progress_callback=_scenario_progress if progress_callback is not None else None,
            match_context={
                "mode_label": "Balance",
                "side_label": "First" if scenario["rl_is_p1"] else "Second",
                "self_deck_label": str(scenario.get("self_deck_name", "Deck")),
                "opp_deck_label": str(scenario.get("opp_deck_name", "Deck")),
                "relation_label": str(scenario["label"]).split("/")[-1],
            },
        )

        rl_wins = int(summary["p1_wins"] if scenario["rl_is_p1"] else summary["p2_wins"])
        opp_wins = int(summary["p2_wins"] if scenario["rl_is_p1"] else summary["p1_wins"])
        draws = int(summary["draws"])
        episodes = int(summary["episodes"])
        wr = (rl_wins / episodes * 100.0) if episodes > 0 else 0.0

        scenario_history_path = None
        if include_history:
            scenario_slug = _combo_slug(*scenario_label.split("/"))
            scenario_history_lines = [
                f"=== Scenario {scenario_label} Histories ===",
                f"report={summary['report_path']}",
                "",
                build_win_rate_report(summary),
                "",
            ]
            for match_history in list(summary.get("histories", [])):
                scenario_history_lines.append(_format_match_history(match_history))
                scenario_history_lines.append("")
            if report_path is None:
                scenario_history_path = _default_report_path(f"se_bal_{scenario_slug}_hist")
            else:
                base = Path(report_path)
                scenario_history_path = base.with_name(f"{base.stem}_{scenario_slug}_hist.txt")
            save_report("\n".join(scenario_history_lines).rstrip() + "\n", scenario_history_path)

        return {
            "index": idx,
            "label": scenario_label,
            "matches": episodes,
            "rl_wins": rl_wins,
            "opp_wins": opp_wins,
            "draws": draws,
            "win_rate_percent": wr,
            "avg_steps": float(summary["avg_steps"]),
            "avg_final_turn": float(summary["avg_final_turn"]),
            "action_type_counts": dict(summary.get("action_type_counts", {})),
            "card_use_counts": dict(summary.get("card_use_counts", {})),
            "report_path": summary["report_path"],
            "history_path": None if scenario_history_path is None else str(scenario_history_path),
        }

    if parallel_scenarios:
        with ThreadPoolExecutor(max_workers=scenario_worker_count, thread_name_prefix="se-bal") as executor:
            futures = []
            for idx, scenario in enumerate(scenarios):
                scenario_matches = per + (1 if idx < rem else 0)
                if scenario_matches <= 0:
                    continue
                print(f"[*] Balance scenario {idx + 1}/{scenario_count} | {scenario['label']} | n={scenario_matches}")
                futures.append(executor.submit(_run_single_scenario, idx, scenario, scenario_matches))
            for fut in as_completed(futures):
                scenario_results.append(fut.result())
    else:
        for idx, scenario in enumerate(scenarios):
            scenario_matches = per + (1 if idx < rem else 0)
            if scenario_matches <= 0:
                continue
            print(f"[*] Balance scenario {idx + 1}/{scenario_count} | {scenario['label']} | n={scenario_matches}")
            scenario_results.append(
                _run_single_scenario(
                    idx,
                    scenario,
                    scenario_matches,
                    rl_agent_local=base_rl_agent,
                    opponent_agent_local=base_opponent_agent,
                )
            )

    scenario_results.sort(key=lambda item: int(item["index"]))
    for scenario in scenario_results:
        episodes = int(scenario["matches"])
        rl_wins = int(scenario["rl_wins"])
        opp_wins = int(scenario["opp_wins"])
        draws = int(scenario["draws"])
        wr = float(scenario["win_rate_percent"])
        aggregate["episodes"] += episodes
        aggregate["rl_wins"] += rl_wins
        aggregate["opp_wins"] += opp_wins
        aggregate["draws"] += draws
        aggregate["avg_steps_weighted_sum"] += float(scenario["avg_steps"]) * episodes
        aggregate["avg_final_turn_weighted_sum"] += float(scenario["avg_final_turn"]) * episodes
        aggregate["action_type_counts"].update(scenario.get("action_type_counts", {}))
        aggregate["card_use_counts"].update(scenario.get("card_use_counts", {}))
        lines.append(
            f"- {scenario['label']}: n={episodes}, rl={rl_wins}, opp={opp_wins}, d={draws}, "
            f"wr={wr:.1f}%, avg_steps={float(scenario['avg_steps']):.1f}, avg_turn={float(scenario['avg_final_turn']):.1f}, "
            f"card_use={_format_card_use_summary(scenario.get('card_use_counts', {}), episodes=episodes, avg_steps=float(scenario['avg_steps']))}, "
            f"eval_report={scenario['report_path']}"
        )

    total_n = max(1, int(aggregate["episodes"]))
    total_wr = (aggregate["rl_wins"] / total_n) * 100.0
    avg_steps = aggregate["avg_steps_weighted_sum"] / total_n
    avg_turn = aggregate["avg_final_turn_weighted_sum"] / total_n
    lines.extend(
        [
            "",
            "=== Aggregate ===",
            f"episodes={aggregate['episodes']}",
            f"rl_wins={aggregate['rl_wins']}",
            f"opp_wins={aggregate['opp_wins']}",
            f"draws={aggregate['draws']}",
            f"rl_win_rate_percent={total_wr:.2f}",
            f"avg_steps={avg_steps:.2f}",
            f"avg_final_turn={avg_turn:.2f}",
            f"action_type_counts={dict(sorted(aggregate['action_type_counts'].items()))}",
            f"top_card_use={dict(aggregate['card_use_counts'].most_common(20))}",
        ]
    )

    text = "\n".join(lines)
    saved = save_report(text, _default_report_path("se_bal") if report_path is None else report_path)
    history_path = None
    if include_history:
        history_lines = [
            "=== Saved Model Balance Histories ===",
            f"model_path={model_path}",
            f"opponent_mode={opponent_mode_normalized}",
            f"episodes={aggregate['episodes']}",
            "",
            text,
            "",
        ]
        for scenario in scenario_results:
            history_lines.append(f"--- Scenario {scenario['label']} ---")
            history_lines.append(f"report={scenario['report_path']}")
            history_lines.append(f"history={scenario.get('history_path')}")
            history_lines.append("")
        history_path = save_report(
            "\n".join(history_lines).rstrip() + "\n",
            _default_report_path("se_bal_hist") if report_path is None else Path(report_path).with_name(Path(report_path).stem + "_hist.txt"),
        )
    return {
        "summary_report_path": str(saved),
        "history_report_path": None if history_path is None else str(history_path),
        "scenario_results": scenario_results,
        "aggregate": {
            "episodes": int(aggregate["episodes"]),
            "rl_wins": int(aggregate["rl_wins"]),
            "opp_wins": int(aggregate["opp_wins"]),
            "draws": int(aggregate["draws"]),
            "rl_win_rate_percent": total_wr,
            "avg_steps": avg_steps,
            "avg_final_turn": avg_turn,
            "action_type_counts": dict(sorted(aggregate["action_type_counts"].items())),
            "card_use_counts": dict(aggregate["card_use_counts"].most_common()),
        },
    }


def run_train_eval_experiment(
    *,
    agent: Optional[SeaEngineRLAgent] = None,
    device: Optional[str] = "auto",
    train_opponent_pool: Optional[Sequence[SeaEngineAgent]] = None,
    eval_random_agent: Optional[SeaEngineAgent] = None,
    eval_greedy_agent: Optional[SeaEngineAgent] = None,
    eval_matches: int = 100,
    train_episodes: int = 10000,
    max_turns: int = 100,
    update_interval: int = 16,
    card_data_path: Optional[str] = None,
    player1_deck: str = "",
    player2_deck: str = "",
    seed: Optional[int] = None,
    report_path: Optional[str] = None,
    num_envs: Optional[int] = None,
    save_interval: int = 500,
    checkpoint_interval: int = 1000,
    checkpoint_eval_matches: Optional[int] = None,
    include_eval_history: bool = True,
    resume_model_path: Optional[str] = None,
    resume_episodes_completed: Optional[int] = None,
    resume_skip_pre_eval: bool = False,
) -> Dict[str, object]:
    artifact_start_wall = time.time()
    resolved_device = _resolve_device(device)
    if agent is not None:
        learning_agent = agent
    elif resume_model_path:
        learning_agent = _load_saved_rl_agent(model_path=resume_model_path, seed=seed, device=resolved_device)
    else:
        learning_agent = SeaEngineRLAgent(seed=seed, device=resolved_device)
    trainer = SeaEnginePPOTrainer(learning_agent)

    # Fast-path defaults for large-scale simulation throughput.
    train_turn_cap = int(os.getenv("SEAENGINE_TRAIN_MAX_TURNS", "100"))
    min_update_interval = int(os.getenv("SEAENGINE_MIN_UPDATE_INTERVAL", "32"))
    fast_pool_enabled = os.getenv("SEAENGINE_FAST_POOL", "0") == "1"

    random_eval_opponent = (
        SeaEngineRandomAgent(seed=_seed_with_offset(seed, 101))
        if eval_random_agent is None
        else eval_random_agent
    )
    greedy_eval_opponent = (
        SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 202))
        if eval_greedy_agent is None
        else eval_greedy_agent
    )
    if train_opponent_pool is None:
        if fast_pool_enabled:
            opponent_pool = [SeaEngineRandomAgent(seed=_seed_with_offset(seed, 303))]
        else:
            opponent_pool = trainer.build_default_opponent_pool(seed=_seed_with_offset(seed, 303))
    else:
        opponent_pool = list(train_opponent_pool)

    if num_envs is None:
        cpu = os.cpu_count() or 8
        num_envs = max(8, min(24, cpu))

    checkpoint_interval = max(1, checkpoint_interval)
    save_interval = max(1, save_interval)
    checkpoint_eval_matches = 50 if checkpoint_eval_matches is None else max(1, checkpoint_eval_matches)
    train_max_turns = min(max_turns, train_turn_cap)
    train_update_interval = max(update_interval, min_update_interval)
    resume_start_episodes = max(0, int(resume_episodes_completed or 0))
    if resume_model_path and resume_episodes_completed is None:
        resume_manifest_path = _training_resume_state_path()
        if resume_manifest_path.exists():
            try:
                manifest = json.loads(resume_manifest_path.read_text(encoding="utf-8"))
                resume_start_episodes = max(0, int(manifest.get("episodes_completed", resume_start_episodes)))
            except Exception:
                pass
    train_p1_deck_label = _deck_label_from_json(player1_deck, fallback="Orange")
    train_p2_deck_label = _deck_label_from_json(player2_deck, fallback="Charlotte")
    training_opponent_schedule, training_opponent_counts = _build_training_opponent_schedule(
        opponent_pool=opponent_pool,
        train_episodes=train_episodes,
        num_envs=num_envs,
        save_interval=save_interval,
        seed=_seed_with_offset(seed, 404),
    )

    backend = os.getenv("SEAENGINE_VECTOR_BACKEND", "local")
    local_threads = os.getenv("SEAENGINE_LOCAL_THREADS", "1")
    print(
        f"[*] Experiment start | eval_matches={eval_matches} | train_episodes={train_episodes} | "
        f"max_turns={max_turns} | update_interval={update_interval} | num_envs={num_envs} | "
        f"vector_backend={backend} | local_threads={local_threads} | "
        f"device={resolved_device} | "
        f"train_max_turns={train_max_turns} | train_update_interval={train_update_interval} | "
        f"fast_pool={fast_pool_enabled} | save_interval={save_interval} | checkpoint_interval={checkpoint_interval} | "
        f"checkpoint_eval_matches={checkpoint_eval_matches}"
    )
    print(f"[*] Opp plan total: {_format_plan_counts(training_opponent_counts)}")
    for plan_start in range(0, train_episodes, checkpoint_interval):
        plan_end = min(train_episodes, plan_start + checkpoint_interval)
        plan_counts = Counter(training_opponent_schedule[plan_start:plan_end])
        print(f"[*] Opp plan {plan_start + 1}~{plan_end}: {_format_plan_counts(plan_counts)}")

    def log_eval_progress(stage: str):
        if not _verbose_experiment_logs():
            return None
        def _callback(current: int, total: int, result: str, matchup: str) -> None:
            interval = max(1, _progress_print_interval(total))
            if current % interval != 0 and current != total:
                return
            print(f"[{stage}] {current}/{total} matches complete | matchup={matchup} | last_result={result}")

        return _callback

    def log_train_progress(current: int, total: int, opponent_name: str, stats: Dict[str, object]) -> None:
        if not _verbose_experiment_logs():
            return
        interval = max(1, _progress_print_interval(total))
        if current % interval != 0 and current != total:
            return
        message = (
            f"[train] {current}/{total} episodes complete | "
            f"opponent={opponent_name} | "
            f"last_result={stats.get('result')} | "
            f"w/l/d={stats.get('wins')}/{stats.get('losses')}/{stats.get('draws')} | "
            f"updates={stats.get('updates')}"
        )
        print(message)

    if resume_model_path and resume_skip_pre_eval:
        print("[*] Resume mode: skipping before-training evaluations.")
        before_random = {
            "episodes": 0,
            "p1_agent": learning_agent.name,
            "p2_agent": random_eval_opponent.name,
            "p1_wins": 0,
            "p2_wins": 0,
            "draws": 0,
            "avg_steps": 0.0,
            "avg_final_turn": 0.0,
            "action_type_counts": {},
            "card_use_counts": {},
            "report_path": "",
        }
        before_random_history_path = None
        before_greedy = {
            "episodes": 0,
            "p1_agent": learning_agent.name,
            "p2_agent": greedy_eval_opponent.name,
            "p1_wins": 0,
            "p2_wins": 0,
            "draws": 0,
            "avg_steps": 0.0,
            "avg_final_turn": 0.0,
            "action_type_counts": {},
            "card_use_counts": {},
            "report_path": "",
        }
        before_greedy_history_path = None
    else:
        print("[*] Evaluating before training vs random...")
        before_random = trainer.evaluate(
            opponent_agent=random_eval_opponent,
            num_matches=eval_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
            progress_callback=log_eval_progress("before-random"),
            include_history=include_eval_history,
            match_context={
                "mode_label": "Teach",
                "side_label": "First",
                "self_deck_label": train_p1_deck_label,
                "opp_deck_label": train_p2_deck_label,
                "relation_label": "fixed",
            },
        )
        before_random_history_path = None
        if include_eval_history:
            before_random_history_path = _save_history_report(
                prefix="se_evalhist_before_random",
                title="Before Training vs Random Histories",
                summary=before_random,
        )

        print("[*] Evaluating before training vs greedy...")
        before_greedy = trainer.evaluate(
            opponent_agent=greedy_eval_opponent,
            num_matches=eval_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
            progress_callback=log_eval_progress("before-greedy"),
            include_history=include_eval_history,
            match_context={
                "mode_label": "Teach",
                "side_label": "First",
                "self_deck_label": train_p1_deck_label,
                "opp_deck_label": train_p2_deck_label,
                "relation_label": "fixed",
            },
        )
        before_greedy_history_path = None
        if include_eval_history:
            before_greedy_history_path = _save_history_report(
                prefix="se_evalhist_before_greedy",
                title="Before Training vs Greedy Histories",
                summary=before_greedy,
            )

    print("[*] Training starts...")
    checkpoints: list[Dict[str, object]] = []
    episodes_completed = resume_start_episodes
    last_train_summary: Dict[str, object] = {}
    recovery_next_chunk = False
    prev_checkpoint_greedy_wr: Optional[float] = None
    after_random = None
    after_greedy = None

    while episodes_completed < train_episodes:
        chunk = min(checkpoint_interval, train_episodes - episodes_completed)
        recovery_override = False
        if recovery_next_chunk:
            recovery_override = True
            recovery_next_chunk = False
            print("[*] Recovery mode: next chunk schedule is stabilized (r/g heavy).")

        chunk_schedule = training_opponent_schedule[episodes_completed:episodes_completed + chunk]
        if recovery_override:
            chunk_schedule = _build_recovery_schedule(
                chunk_episodes=chunk,
                num_envs=num_envs,
                opponent_pool=opponent_pool,
                seed=_seed_with_offset(seed, 7000 + episodes_completed),
            )
        print(f"[*] Training chunk {episodes_completed + 1}-{episodes_completed + chunk}...")
        train_summary = trainer.train(
            num_episodes=chunk,
            opponent_pool=opponent_pool,
            opponent_schedule=chunk_schedule,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=train_max_turns,
            update_interval=train_update_interval,
            progress_callback=log_train_progress if _verbose_experiment_logs() else None,
            num_envs=num_envs,
            log_interval=200,
            save_interval=save_interval,
            episode_offset=episodes_completed,
        )
        episodes_completed += chunk
        last_train_summary = train_summary

        print(f"[*] Checkpoint {episodes_completed}/{train_episodes} -> evaluating {checkpoint_eval_matches * 8} matches...")
        suite = _run_checkpoint_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            greedy_opponent=SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 505 + episodes_completed)),
            checkpoint_episodes=episodes_completed,
            num_matches=checkpoint_eval_matches,
            card_data_path=card_data_path,
            train_player1_deck=player1_deck,
            train_player2_deck=player2_deck,
            max_turns=max_turns,
        )
        checkpoint_text = "\n".join(
            [
                f"=== Checkpoint {episodes_completed} Episodes ===",
                f"opponent_stats={train_summary.get('opponent_stats', {})}",
                suite["text"],
                "",
                f"train_summary={train_summary}",
                "",
            ]
        )
        checkpoint_path = save_report(checkpoint_text, _default_report_path(f"se_ckpt_{episodes_completed}"))
        self_stats_text = "\n".join(
            [
                f"=== Opponent Stats @ {episodes_completed} ===",
                f"episodes={episodes_completed}",
                f"stats={train_summary.get('opponent_stats', {})}",
                "",
            ]
        )
        self_stats_path = save_report(self_stats_text, _default_report_path(f"se_selfstats_{episodes_completed}"))
        checkpoints.append(
            {
                "episodes_completed": episodes_completed,
                "train_summary": train_summary,
                "suite_results": suite["results"],
                "suite_text": suite["text"],
                "report_path": str(checkpoint_path),
                "self_stats_path": str(self_stats_path),
            }
        )
        resume_state_path = _save_training_resume_state(
            model_path=str(trainer.model_dir / f"model_ep_{episodes_completed}.pt"),
            episodes_completed=episodes_completed,
            train_episodes=train_episodes,
            checkpoint_interval=checkpoint_interval,
            save_interval=save_interval,
            seed=seed,
            device=str(learning_agent.device),
            report_path=str(checkpoint_path),
        )
        print(f"[*] Resume state saved: {resume_state_path}")
        greedy_rows = [row for row in suite["results"] if row.get("opponent") == "greedy"]
        greedy_n = sum(int(row.get("episodes", 0)) for row in greedy_rows)
        greedy_w = sum(int(row.get("rl_wins", 0)) for row in greedy_rows)
        greedy_wr = 0.0 if greedy_n <= 0 else greedy_w / greedy_n
        if prev_checkpoint_greedy_wr is not None:
            delta = greedy_wr - prev_checkpoint_greedy_wr
            if delta <= -0.08:
                recovery_next_chunk = True
                print(
                    f"[!] Checkpoint drop detected: greedy winrate {prev_checkpoint_greedy_wr*100:.1f}% -> "
                    f"{greedy_wr*100:.1f}% (delta {delta*100:.1f}pp). Recovery schedule enabled for next chunk."
                )
        prev_checkpoint_greedy_wr = greedy_wr

    print("[*] Evaluating after training vs random...")
    after_random = trainer.evaluate(
        opponent_agent=SeaEngineRandomAgent(seed=_seed_with_offset(seed, 404)),
        num_matches=eval_matches,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=max_turns,
        progress_callback=log_eval_progress("after-random"),
        include_history=include_eval_history,
        match_context={
            "mode_label": "Teach",
            "side_label": "First",
            "self_deck_label": train_p1_deck_label,
            "opp_deck_label": train_p2_deck_label,
            "relation_label": "fixed",
        },
    )
    after_random_history_path = None
    if include_eval_history:
        after_random_history_path = _save_history_report(
            prefix="se_evalhist_after_random",
            title="After Training vs Random Histories",
            summary=after_random,
        )

    print("[*] Evaluating after training vs greedy...")
    after_greedy = trainer.evaluate(
        opponent_agent=SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 505)),
        num_matches=eval_matches,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=max_turns,
        progress_callback=log_eval_progress("after-greedy"),
        include_history=include_eval_history,
        match_context={
            "mode_label": "Teach",
            "side_label": "First",
            "self_deck_label": train_p1_deck_label,
            "opp_deck_label": train_p2_deck_label,
            "relation_label": "fixed",
        },
    )
    after_greedy_history_path = None
    if include_eval_history:
        after_greedy_history_path = _save_history_report(
            prefix="se_evalhist_after_greedy",
            title="After Training vs Greedy Histories",
            summary=after_greedy,
        )
    report_lines = [
        "=== SeaEngine Train/Eval Experiment ===",
        f"train_episodes={train_episodes}",
        f"eval_matches={eval_matches}",
        f"max_turns={max_turns}",
        f"update_interval={update_interval}",
        f"opponent_pool={[agent.name for agent in opponent_pool]}",
        "",
        "=== Before Training vs Random ===",
        f"report={before_random['report_path']}",
        f"history={None if before_random_history_path is None else str(before_random_history_path)}",
        build_win_rate_report(before_random),
        "",
        "=== Before Training vs Greedy ===",
        f"report={before_greedy['report_path']}",
        f"history={None if before_greedy_history_path is None else str(before_greedy_history_path)}",
        build_win_rate_report(before_greedy),
        "",
        "=== Training Summary ===",
        str(last_train_summary),
        "",
        "=== Checkpoints ===",
        "\n".join(f"- ep {ckpt['episodes_completed']}: {ckpt['report_path']}" for ckpt in checkpoints),
        "",
        "=== After Training vs Random ===",
        f"report={after_random['report_path']}",
        f"history={None if after_random_history_path is None else str(after_random_history_path)}",
        build_win_rate_report(after_random),
        "",
        "=== After Training vs Greedy ===",
        f"report={after_greedy['report_path']}",
        f"history={None if after_greedy_history_path is None else str(after_greedy_history_path)}",
        build_win_rate_report(after_greedy),
    ]

    report_text = "\n".join(report_lines)
    saved_path = save_report(report_text, _default_report_path() if report_path is None else report_path)
    zipped_logs = _zip_new_log_txt_files(since_timestamp=artifact_start_wall)
    zipped_models = _zip_new_model_files(since_timestamp=artifact_start_wall)
    final_resume_state = _save_training_resume_state(
        model_path=str(trainer.model_dir / f"model_ep_{episodes_completed}.pt") if episodes_completed > 0 else resume_model_path,
        episodes_completed=episodes_completed,
        train_episodes=train_episodes,
        checkpoint_interval=checkpoint_interval,
        save_interval=save_interval,
        seed=seed,
        device=str(learning_agent.device),
        report_path=str(saved_path),
    )
    print(f"[*] Final resume state saved: {final_resume_state}")

    return {
        "before_random": before_random,
        "before_greedy": before_greedy,
        "before_random_history_path": None if before_random_history_path is None else str(before_random_history_path),
        "before_greedy_history_path": None if before_greedy_history_path is None else str(before_greedy_history_path),
        "train": last_train_summary,
        "after_random": after_random,
        "after_greedy": after_greedy,
        "after_random_history_path": None if after_random_history_path is None else str(after_random_history_path),
        "after_greedy_history_path": None if after_greedy_history_path is None else str(after_greedy_history_path),
        "checkpoints": checkpoints,
        "report_text": report_text,
        "report_path": str(saved_path),
        "log_zip_path": None if zipped_logs is None else str(zipped_logs),
        "model_zip_path": None if zipped_models is None else str(zipped_models),
    }


def run_checkpoint_training_experiment(
    *,
    agent: Optional[SeaEngineRLAgent] = None,
    device: Optional[str] = "auto",
    train_opponent_pool: Optional[Sequence[SeaEngineAgent]] = None,
    eval_greedy_agent: Optional[SeaEngineAgent] = None,
    eval_random_agent: Optional[SeaEngineAgent] = None,
    eval_matches: int = 100,
    total_train_episodes: int = 600,
    eval_interval: int = 100,
    max_turns: int = 100,
    update_interval: int = 8,
    card_data_path: Optional[str] = None,
    player1_deck: str = "",
    player2_deck: str = "",
    seed: Optional[int] = None,
    summary_report_path: Optional[str] = None,
) -> Dict[str, object]:
    resolved_device = _resolve_device(device)
    learning_agent = SeaEngineRLAgent(seed=seed, device=resolved_device) if agent is None else agent
    trainer = SeaEnginePPOTrainer(learning_agent)
    opponent_pool = (
        trainer.build_default_opponent_pool(seed=_seed_with_offset(seed, 606))
        if train_opponent_pool is None
        else list(train_opponent_pool)
    )
    greedy_eval_opponent = (
        SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 707))
        if eval_greedy_agent is None
        else eval_greedy_agent
    )
    random_eval_opponent = (
        SeaEngineRandomAgent(seed=_seed_with_offset(seed, 808))
        if eval_random_agent is None
        else eval_random_agent
    )

    checkpoints = []
    summary_lines = [
        "=== SeaEngine Checkpoint Training Experiment ===",
        f"device={resolved_device}",
        f"total_train_episodes={total_train_episodes}",
        f"eval_interval={eval_interval}",
        f"eval_matches={eval_matches}",
        f"max_turns={max_turns}",
        f"update_interval={update_interval}",
        f"opponent_pool={[agent.name for agent in opponent_pool]}",
        "",
    ]

    before_greedy = trainer.evaluate(
        opponent_agent=greedy_eval_opponent,
        num_matches=eval_matches,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=max_turns,
        include_history=True,
        match_context={
            "mode_label": "Teach",
            "side_label": "First",
            "self_deck_label": _deck_label_from_json(player1_deck, fallback="Orange"),
            "opp_deck_label": _deck_label_from_json(player2_deck, fallback="Charlotte"),
            "relation_label": "fixed",
        },
    )
    before_greedy_history_path = _save_history_report(
        prefix="se_ckpt_before_greedy_hist",
        title="Before Training vs Greedy Histories",
        summary=before_greedy,
    )
    summary_lines.extend(
        [
            "=== Before Training vs Greedy ===",
            f"report={before_greedy['report_path']}",
            f"history={None if before_greedy_history_path is None else str(before_greedy_history_path)}",
            build_win_rate_report(before_greedy),
            "",
        ]
    )

    episodes_completed = 0
    while episodes_completed < total_train_episodes:
        chunk = min(eval_interval, total_train_episodes - episodes_completed)
        train_summary = trainer.train(
            num_episodes=chunk,
            opponent_pool=opponent_pool,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
            update_interval=update_interval,
        )
        episodes_completed += chunk

        greedy_summary = trainer.evaluate(
            opponent_agent=SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 900 + episodes_completed)),
            num_matches=eval_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
            include_history=True,
            match_context={
                "mode_label": "Teach",
                "side_label": "First",
                "self_deck_label": _deck_label_from_json(player1_deck, fallback="Orange"),
                "opp_deck_label": _deck_label_from_json(player2_deck, fallback="Charlotte"),
                "relation_label": "fixed",
            },
        )
        greedy_history_path = _save_history_report(
            prefix=f"se_ckpt_{episodes_completed}_greedy_hist",
            title=f"Checkpoint {episodes_completed} vs Greedy Histories",
            summary=greedy_summary,
        )
        random_summary = trainer.evaluate(
            opponent_agent=SeaEngineRandomAgent(seed=_seed_with_offset(seed, 1200 + episodes_completed)),
            num_matches=eval_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
            include_history=True,
            match_context={
                "mode_label": "Teach",
                "side_label": "First",
                "self_deck_label": _deck_label_from_json(player1_deck, fallback="Orange"),
                "opp_deck_label": _deck_label_from_json(player2_deck, fallback="Charlotte"),
                "relation_label": "fixed",
            },
        )
        random_history_path = _save_history_report(
            prefix=f"se_ckpt_{episodes_completed}_random_hist",
            title=f"Checkpoint {episodes_completed} vs Random Histories",
            summary=random_summary,
        )

        checkpoints.append(
            {
                "episodes_completed": episodes_completed,
                "train_summary": train_summary,
                "greedy_summary": greedy_summary,
                "random_summary": random_summary,
                "greedy_history_path": None if greedy_history_path is None else str(greedy_history_path),
                "random_history_path": None if random_history_path is None else str(random_history_path),
            }
        )
        summary_lines.extend(
            [
                f"=== Checkpoint {episodes_completed} Episodes ===",
                f"greedy_report={greedy_summary['report_path']}",
                f"greedy_history={None if greedy_history_path is None else str(greedy_history_path)}",
                build_win_rate_report(greedy_summary),
                "",
                f"random_report={random_summary['report_path']}",
                f"random_history={None if random_history_path is None else str(random_history_path)}",
                build_win_rate_report(random_summary),
                "",
                f"train_summary={train_summary}",
                "",
            ]
        )

    summary_text = "\n".join(summary_lines)
    saved_path = save_report(
        summary_text,
        _default_report_path("se_ckpt")
        if summary_report_path is None
        else summary_report_path,
    )
    artifact_start_wall = time.time()
    zipped_logs = _zip_new_log_txt_files(since_timestamp=artifact_start_wall)
    zipped_models = _zip_new_model_files(since_timestamp=artifact_start_wall)
    return {
        "before_greedy": before_greedy,
        "checkpoints": checkpoints,
        "summary_text": summary_text,
        "summary_report_path": str(saved_path),
        "log_zip_path": None if zipped_logs is None else str(zipped_logs),
        "model_zip_path": None if zipped_models is None else str(zipped_models),
    }
