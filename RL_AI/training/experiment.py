from __future__ import annotations

import copy
from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import random
import threading
import re
from pathlib import Path
import time
import zipfile
from typing import Callable, Dict, Optional, Sequence

from RL_AI.agents import (
    SeaEngineAgent,
    SeaEngineBeliefMCTSAgent,
    SeaEngineGreedyAgent,
    SeaEngineRLAgent,
    SeaEngineRandomAgent,
    SeaEngineRuleBasedAgent,
    default_model_hidden_dim,
    infer_hidden_dim_from_state_dict,
    load_state_dict_flexible,
)
from RL_AI.training.evaluator import evaluate_agents
from RL_AI.SeaEngine.observation import STATE_VECTOR_DIM
from RL_AI.training.trainer import SeaEnginePPOTrainer
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
    cleanup_after_zip: bool = False,
    keep_names: Optional[set[str]] = None,
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
    if cleanup_after_zip:
        keep = set(keep_names or set())
        for txt_file in txt_files:
            if txt_file.name in keep:
                continue
            try:
                txt_file.unlink()
            except OSError:
                pass
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
    selected_episodes = {2000, 4000, 6000, 8000, 10000}
    filtered_model_files = [p for p in model_files if _episode_from_name(p) in selected_episodes]
    if filtered_model_files:
        model_files = filtered_model_files
    model_files.sort(key=lambda p: p.name)
    zip_path = _default_model_zip_path() if output_path is None else output_path
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for model_file in model_files:
            zf.write(model_file, arcname=model_file.name)
    return zip_path


def _episode_from_name(path: Path) -> int:
    stem = path.stem
    match = re.search(r"model_ep_(\d+)$", stem)
    if match:
        return int(match.group(1))
    return -1


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
    for key in ("random", "greedy", "rule_based"):
        if key in counts:
            parts.append(f"{key}={counts[key]}")
    for key in sorted(k for k in counts.keys() if k not in {"random", "greedy", "rule_based"}):
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
            weights = {"random": 0.55, "greedy": 0.25, "rule_based": 0.10}
        elif progress <= 0.35:
            weights = {"random": 0.40, "greedy": 0.30, "rule_based": 0.15}
        elif progress <= 0.60:
            weights = {"random": 0.28, "greedy": 0.30, "rule_based": 0.17}
        elif progress <= 0.80:
            weights = {"random": 0.20, "greedy": 0.25, "rule_based": 0.20}
        else:
            weights = {"random": 0.15, "greedy": 0.25, "rule_based": 0.20}

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


def _build_deficit_start_schedule(
    *,
    train_episodes: int,
    seed: Optional[int] = None,
) -> list[str]:
    rng = random.Random(seed)
    schedule: list[str] = []
    for episode in range(1, train_episodes + 1):
        if episode <= 2000:
            weights = {"normal": 0.80, "slight": 0.15, "heavy": 0.05}
        elif episode <= 6000:
            weights = {"normal": 0.70, "slight": 0.20, "heavy": 0.10}
        else:
            weights = {"normal": 0.60, "slight": 0.25, "heavy": 0.15}
        schedule.append(rng.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0])
    return schedule


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
    weights: Dict[str, float] = {"random": 0.35, "greedy": 0.25, "rule_based": 0.15}
    if recent_self:
        # Recovery should restore stability without reverting to narrow greedy-only tuning.
        weights["random"] = 0.30
        weights["greedy"] = 0.25
        weights["rule_based"] = 0.15
        self_weight = 0.30 / len(recent_self)
        for name in recent_self:
            weights[name] = self_weight
    else:
        weights["random"] = 0.45
        weights["greedy"] = 0.35
        weights["rule_based"] = 0.20

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


def _suite_rl_win_rate(suite_pack: Optional[Dict[str, object]]) -> float:
    if not suite_pack:
        return 0.0
    rows = list(suite_pack.get("results", []))
    episodes = sum(int(row.get("episodes", 0)) for row in rows)
    wins = sum(int(row.get("rl_wins", 0)) for row in rows)
    return 0.0 if episodes <= 0 else wins / episodes


def _suite_worst_combo_rate(suite_pack: Optional[Dict[str, object]]) -> float:
    if not suite_pack:
        return 0.0
    rates = []
    for row in list(suite_pack.get("results", [])):
        episodes = int(row.get("episodes", 0))
        if episodes <= 0:
            continue
        rates.append(float(row.get("rl_wins", 0)) / float(episodes))
    return min(rates) if rates else 0.0


def _suite_side_gap_abs(suite_pack: Optional[Dict[str, object]]) -> float:
    if not suite_pack:
        return 1.0
    first_wins = first_n = second_wins = second_n = 0
    for row in list(suite_pack.get("results", [])):
        episodes = int(row.get("episodes", 0))
        wins = int(row.get("rl_wins", 0))
        if "선공" in str(row.get("label", row.get("side", ""))) or str(row.get("side", "")) == "선공":
            first_wins += wins
            first_n += episodes
        elif "후공" in str(row.get("label", row.get("side", ""))) or str(row.get("side", "")) == "후공":
            second_wins += wins
            second_n += episodes
    if first_n <= 0 or second_n <= 0:
        return 1.0
    return abs(first_wins / first_n - second_wins / second_n)


def _checkpoint_population_score(*, greedy_suite: Optional[Dict[str, object]], self_suite: Optional[Dict[str, object]]) -> Dict[str, float]:
    greedy_wr = _suite_rl_win_rate(greedy_suite)
    self_wr = _suite_rl_win_rate(self_suite)
    worst_combo = min(_suite_worst_combo_rate(greedy_suite), _suite_worst_combo_rate(self_suite))
    side_gap = max(_suite_side_gap_abs(greedy_suite), _suite_side_gap_abs(self_suite))
    score = (0.45 * greedy_wr) + (0.25 * self_wr) + (0.20 * worst_combo) - (0.10 * side_gap)
    return {
        "score": score,
        "greedy_wr": greedy_wr,
        "self_wr": self_wr,
        "worst_combo_wr": worst_combo,
        "max_side_gap": side_gap,
    }


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


def _default_scenario_workers() -> int:
    env_workers = os.getenv("SEAENGINE_SCENARIO_WORKERS", "").strip()
    if env_workers:
        try:
            return max(1, int(env_workers))
        except Exception:
            pass
    return 1


def _make_skipped_eval_summary(opponent_label: str) -> Dict[str, object]:
    return {
        "episodes": 0,
        "p1_agent": "skipped",
        "p2_agent": opponent_label,
        "p1_wins": 0,
        "p2_wins": 0,
        "draws": 0,
        "avg_steps": 0.0,
        "avg_final_turn": 0.0,
        "action_type_counts": {},
        "card_use_counts": {},
        "report_path": "skipped",
        "histories": [],
    }


def _clone_agent_for_eval(agent: SeaEngineAgent, *, use_belief_mcts: bool = True, seed: Optional[int] = None) -> SeaEngineAgent:
    clone = copy.deepcopy(agent)
    if hasattr(clone, "sample_actions"):
        try:
            setattr(clone, "sample_actions", False)
        except Exception:
            pass
    if use_belief_mcts and isinstance(clone, SeaEngineRLAgent):
        return SeaEngineBeliefMCTSAgent.from_env(clone, seed=seed)
    return clone


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
    leader_hp = dict(match_history.get("leader_hp", {}) or {})
    leader_hp_by_player = dict(leader_hp.get("leader_hp_by_player", {}) or {})
    if leader_hp_by_player:
        hp_parts = []
        for player_id in sorted(leader_hp_by_player):
            row = dict(leader_hp_by_player.get(player_id, {}) or {})
            hp_parts.append(
                f"{player_id}:{row.get('deck', 'Unknown')} "
                f"final={row.get('final_hp', '?')} min={row.get('min_hp', '?')}"
            )
        lines.append("leader_hp=" + " | ".join(hp_parts))
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


def _format_leader_hp_stats(leader_hp_stats: Dict[str, object]) -> str:
    stats = dict(leader_hp_stats or {})
    min_by_deck = dict(stats.get("min_by_deck", {}) or {})
    parts = []
    for deck_name in ("Orange", "Charlotte"):
        row = dict(min_by_deck.get(deck_name, {}) or {})
        count = int(row.get("count", 0))
        if count <= 0:
            continue
        parts.append(
            f"{deck_name}_min_hp=n{count}/avg{float(row.get('avg', 0.0)):.2f}/"
            f"min{float(row.get('min', 0.0)):.2f}/max{float(row.get('max', 0.0)):.2f}"
        )
    return " | ".join(parts) if parts else "-"


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


def _run_8combo_opponent_eval_suite(
    *,
    trainer: SeaEnginePPOTrainer,
    rl_agent: SeaEngineRLAgent,
    opponent_agent: SeaEngineAgent,
    opponent_label: str,
    suite_title: str,
    history_tag: str,
    num_matches_per_combo: int,
    card_data_path: Optional[str],
    max_turns: int,
    scenario_report_prefix: str = "se_eval",
    checkpoint_episodes: Optional[int] = None,
    start_mode: str = "normal",
    burnin_profile: str = "fixed",
    scenario_workers: int = 1,
    use_belief_mcts: bool = True,
) -> Dict[str, object]:
    deck_pairs = [
        ("귤", trainer.decks["Orange"]),
        ("샤를로테", trainer.decks["Charlotte"]),
    ]
    combo_results: list[Dict[str, object]] = []
    suite_lines = [f"=== {suite_title} ({num_matches_per_combo} each, total {num_matches_per_combo * 8}) ==="]
    history_root = Path(__file__).resolve().parent.parent / "log"
    total_episodes = 0
    total_rl_wins = 0
    total_opp_wins = 0
    total_draws = 0
    total_steps_weighted_sum = 0.0
    total_turns_weighted_sum = 0.0
    action_type_counts: Counter[str] = Counter()
    card_use_counts: Counter[str] = Counter()
    combined_histories: list[Dict[str, object]] = []
    scenario_worker_count = max(1, int(scenario_workers or 1))
    parallel_scenarios = scenario_worker_count > 1

    def _run_single_scenario(
        idx: int,
        rl_deck_name: str,
        rl_deck: str,
        side_name: str,
        rl_is_p1: bool,
        relation_name: str,
        use_same_deck: bool,
        scenario_matches: int,
    ) -> Dict[str, object]:
        other_deck_name, other_deck = deck_pairs[1] if rl_deck_name == deck_pairs[0][0] else deck_pairs[0]
        opp_deck = rl_deck if use_same_deck else other_deck
        if rl_is_p1:
            p1_agent = _clone_agent_for_eval(rl_agent, use_belief_mcts=use_belief_mcts)
            p2_agent = _clone_agent_for_eval(opponent_agent, use_belief_mcts=use_belief_mcts)
            p1_deck, p2_deck = rl_deck, opp_deck
        else:
            p1_agent = _clone_agent_for_eval(opponent_agent, use_belief_mcts=use_belief_mcts)
            p2_agent = _clone_agent_for_eval(rl_agent, use_belief_mcts=use_belief_mcts)
            p1_deck, p2_deck = opp_deck, rl_deck

        scenario_label = f"{opponent_label}/{rl_deck_name}/{side_name}/{relation_name}"
        scenario_report_path = _scenario_report_path(label=scenario_label, report_path=None, prefix=scenario_report_prefix)
        summary = evaluate_agents(
            p1_agent,
            p2_agent,
            num_matches=scenario_matches,
            report_path=str(scenario_report_path),
            card_data_path=card_data_path,
            player1_deck=p1_deck,
            player2_deck=p2_deck,
            max_turns=max_turns,
            include_history=True,
            match_context={
                "mode_label": opponent_label,
                "side_label": side_name,
                "self_deck_label": rl_deck_name,
                "opp_deck_label": other_deck_name,
                "relation_label": relation_name,
            },
            start_mode=start_mode,
            start_focus_player="P1" if rl_is_p1 else "P2",
            burnin_profile=burnin_profile,
        )
        rl_wins = int(summary["p1_wins"] if rl_is_p1 else summary["p2_wins"])
        opp_wins = int(summary["p2_wins"] if rl_is_p1 else summary["p1_wins"])
        histories = list(summary.get("histories", []))
        history_slug = _combo_slug(opponent_label, rl_deck_name, side_name, relation_name)
        if checkpoint_episodes is None:
            history_path = history_root / f"{history_tag}_{history_slug}_hist.txt"
        else:
            history_path = history_root / f"se_ckpt_{checkpoint_episodes}_{history_slug}_hist.txt"
        history_lines = [
            f"=== {suite_title} History ===",
            f"combo={scenario_label}",
            f"episodes={scenario_matches}",
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
        return {
            "index": idx,
            "label": scenario_label,
            "episodes": scenario_matches,
            "rl_wins": rl_wins,
            "opp_wins": opp_wins,
            "draws": int(summary["draws"]),
            "avg_steps": float(summary["avg_steps"]),
            "avg_final_turn": float(summary["avg_final_turn"]),
            "action_type_counts": dict(summary.get("action_type_counts", {})),
            "card_use_counts": dict(summary.get("card_use_counts", {})),
            "report_path": summary["report_path"],
            "history_path": str(history_path),
            "histories": histories,
        }

    if parallel_scenarios:
        with ThreadPoolExecutor(max_workers=scenario_worker_count, thread_name_prefix="se-eval") as executor:
            futures = []
            for idx, rl_deck_name in enumerate([deck_pairs[0][0], deck_pairs[1][0]]):
                rl_deck = deck_pairs[0][1] if rl_deck_name == deck_pairs[0][0] else deck_pairs[1][1]
                for side_name, rl_is_p1 in [("선공", True), ("후공", False)]:
                    for relation_name, use_same_deck in [("같은 덱", True), ("다른 덱", False)]:
                        scenario_matches = num_matches_per_combo
                        if scenario_matches <= 0:
                            continue
                        futures.append(
                            executor.submit(
                                _run_single_scenario,
                                len(futures),
                                rl_deck_name,
                                rl_deck,
                                side_name,
                                rl_is_p1,
                                relation_name,
                                use_same_deck,
                                scenario_matches,
                            )
                        )
            combo_results = [fut.result() for fut in as_completed(futures)]
            combo_results.sort(key=lambda item: int(item["index"]))
            for row in combo_results:
                histories = list(row.get("histories", []))
                total_episodes += int(row["episodes"])
                total_rl_wins += int(row["rl_wins"])
                total_opp_wins += int(row["opp_wins"])
                total_draws += int(row["draws"])
                total_steps_weighted_sum += float(row["avg_steps"]) * float(row["episodes"])
                total_turns_weighted_sum += float(row["avg_final_turn"]) * float(row["episodes"])
                action_type_counts.update({str(k): int(v) for k, v in dict(row.get("action_type_counts", {})).items()})
                card_use_counts.update({str(k): int(v) for k, v in dict(row.get("card_use_counts", {})).items()})
                combined_histories.extend(histories)
                suite_lines.append(
                    f"- {row['label']}: rl={row['rl_wins']}, opp={row['opp_wins']}, d={row['draws']}, "
                    f"avg_steps={float(row['avg_steps']):.1f}, avg_turn={float(row['avg_final_turn']):.1f}, "
                    f"report={row['report_path']}, hist={row['history_path']}"
                )

        history_summary = {
            "episodes": total_episodes,
            "p1_agent": rl_agent.name,
            "p2_agent": opponent_agent.name,
            "p1_wins": total_rl_wins,
            "p2_wins": total_opp_wins,
            "draws": total_draws,
            "avg_steps": 0.0 if total_episodes == 0 else total_steps_weighted_sum / total_episodes,
            "avg_final_turn": 0.0 if total_episodes == 0 else total_turns_weighted_sum / total_episodes,
            "action_type_counts": dict(sorted(action_type_counts.items())),
            "card_use_counts": dict(card_use_counts.most_common()),
            "histories": combined_histories,
            "report_path": "",
        }
        return {
            "results": combo_results,
            "text": "\n".join(suite_lines),
            "history_summary": history_summary,
        }

    for rl_deck_name, rl_deck in deck_pairs:
        other_deck_name, other_deck = deck_pairs[1] if rl_deck_name == deck_pairs[0][0] else deck_pairs[0]
        for side_name, rl_is_p1 in [("선공", True), ("후공", False)]:
            for relation_name, use_same_deck in [("같은 덱", True), ("다른 덱", False)]:
                opp_deck = rl_deck if use_same_deck else other_deck
                if rl_is_p1:
                    p1_agent = _clone_agent_for_eval(rl_agent, use_belief_mcts=use_belief_mcts)
                    p2_agent = _clone_agent_for_eval(opponent_agent, use_belief_mcts=use_belief_mcts)
                    p1_deck, p2_deck = rl_deck, opp_deck
                else:
                    p1_agent = _clone_agent_for_eval(opponent_agent, use_belief_mcts=use_belief_mcts)
                    p2_agent = _clone_agent_for_eval(rl_agent, use_belief_mcts=use_belief_mcts)
                    p1_deck, p2_deck = opp_deck, rl_deck

                scenario_label = f"{opponent_label}/{rl_deck_name}/{side_name}/{relation_name}"
                scenario_report_path = _scenario_report_path(label=scenario_label, report_path=None, prefix=scenario_report_prefix)
                summary = evaluate_agents(
                    p1_agent,
                    p2_agent,
                    num_matches=num_matches_per_combo,
                    report_path=str(scenario_report_path),
                    card_data_path=card_data_path,
                    player1_deck=p1_deck,
                    player2_deck=p2_deck,
                    max_turns=max_turns,
                    include_history=True,
                    match_context={
                        "mode_label": opponent_label,
                        "side_label": side_name,
                        "self_deck_label": rl_deck_name,
                        "opp_deck_label": other_deck_name,
                        "relation_label": relation_name,
                    },
                    start_mode=start_mode,
                    start_focus_player="P1" if rl_is_p1 else "P2",
                    burnin_profile=burnin_profile,
                )
                rl_wins = int(summary["p1_wins"] if rl_is_p1 else summary["p2_wins"])
                opp_wins = int(summary["p2_wins"] if rl_is_p1 else summary["p1_wins"])
                combo_label = scenario_label
                histories = list(summary.get("histories", []))
                history_slug = _combo_slug(opponent_label, rl_deck_name, side_name, relation_name)
                if checkpoint_episodes is None:
                    history_path = history_root / f"{history_tag}_{history_slug}_hist.txt"
                else:
                    history_path = history_root / f"se_ckpt_{checkpoint_episodes}_{history_slug}_hist.txt"
                history_lines = [
                    f"=== {suite_title} History ===",
                    f"combo={combo_label}",
                    f"episodes={num_matches_per_combo}",
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

                total_episodes += int(summary["episodes"])
                total_rl_wins += rl_wins
                total_opp_wins += opp_wins
                total_draws += int(summary["draws"])
                total_steps_weighted_sum += float(summary["avg_steps"]) * float(summary["episodes"])
                total_turns_weighted_sum += float(summary["avg_final_turn"]) * float(summary["episodes"])
                action_type_counts.update({str(k): int(v) for k, v in dict(summary.get("action_type_counts", {})).items()})
                card_use_counts.update({str(k): int(v) for k, v in dict(summary.get("card_use_counts", {})).items()})
                combined_histories.extend(histories)

                combo_results.append(
                    {
                        "opponent": opponent_label,
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

    history_summary = {
        "episodes": total_episodes,
        "p1_agent": rl_agent.name,
        "p2_agent": opponent_agent.name,
        "p1_wins": total_rl_wins,
        "p2_wins": total_opp_wins,
        "draws": total_draws,
        "avg_steps": 0.0 if total_episodes == 0 else total_steps_weighted_sum / total_episodes,
        "avg_final_turn": 0.0 if total_episodes == 0 else total_turns_weighted_sum / total_episodes,
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "card_use_counts": dict(card_use_counts.most_common()),
        "histories": combined_histories,
        "report_path": "",
    }
    return {
        "results": combo_results,
        "text": "\n".join(suite_lines),
        "history_summary": history_summary,
    }


def _load_saved_rl_agent(
    *,
    model_path: str,
    seed: Optional[int],
    device: Optional[str],
) -> SeaEngineRLAgent:
    import torch

    resolved_device = _resolve_device(device)
    state_dict = torch.load(model_path, map_location=resolved_device)
    agent = SeaEngineRLAgent(
        seed=seed,
        device=resolved_device,
        sample_actions=False,
        hidden_dim=infer_hidden_dim_from_state_dict(state_dict),
    )
    agent.ensure_model(state_dim=STATE_VECTOR_DIM)
    assert agent.model is not None
    load_state_dict_flexible(agent.model, state_dict)
    agent.model.eval()
    return agent


def _maybe_wrap_belief_mcts(agent: SeaEngineAgent, *, enabled: bool, seed: Optional[int]) -> SeaEngineAgent:
    if enabled and isinstance(agent, SeaEngineRLAgent):
        return SeaEngineBeliefMCTSAgent.from_env(agent, seed=seed)
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
    history_limit: Optional[int] = None,
    progress_callback: Optional[Callable[[str, int, int, str, str], None]] = None,
    report_path: Optional[str] = None,
    scenario_workers: int = 1,
    scenario_shards: int = 1,
    use_belief_mcts: bool = True,
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
    scenario_shard_count = max(1, int(scenario_shards or 1))
    parallel_scenarios = scenario_worker_count > 1 or scenario_shard_count > 1
    opponent_mode_normalized = str(opponent_mode or "greedy").strip().lower()

    def _build_opponent_agent() -> SeaEngineAgent:
        if opponent_mode_normalized in {"self", "rl", "self_play", "selfplay"}:
            if opponent_model_path:
                return _maybe_wrap_belief_mcts(
                    _load_saved_rl_agent(
                        model_path=opponent_model_path,
                        seed=_seed_with_offset(seed, 2001),
                        device=resolved_device,
                    ),
                    enabled=use_belief_mcts,
                    seed=_seed_with_offset(seed, 2001),
                )
            opponent = _maybe_wrap_belief_mcts(
                _load_saved_rl_agent(
                    model_path=opponent_model_path,
                    seed=_seed_with_offset(seed, 2001),
                    device=resolved_device,
                )
                if opponent_model_path
                else _load_saved_rl_agent(
                    model_path=model_path,
                    seed=_seed_with_offset(seed, 2001),
                    device=resolved_device,
                ),
                enabled=use_belief_mcts,
                seed=_seed_with_offset(seed, 2001),
            )
            opponent.name = "rl_opp"
            return opponent
        if opponent_mode_normalized in {"rule", "rule_based", "rule-based"}:
            return SeaEngineRuleBasedAgent(seed=_seed_with_offset(seed, 2001))
        return SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 2001))

    def _build_agents() -> tuple[SeaEngineRLAgent, SeaEngineAgent]:
        rl = _maybe_wrap_belief_mcts(
            _load_saved_rl_agent(model_path=model_path, seed=seed, device=resolved_device),
            enabled=use_belief_mcts,
            seed=seed,
        )
        opp = _build_opponent_agent()
        return rl, opp

    opponent_tag = (
        "self"
        if opponent_mode_normalized in {"self", "rl", "self_play", "selfplay"}
        else ("rule" if opponent_mode_normalized in {"rule", "rule_based", "rule-based"} else "g")
    )
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
        f"scenario_shards={scenario_shard_count}",
        f"use_belief_mcts={use_belief_mcts}",
        f"history_limit={history_limit if history_limit is not None else 'auto'}",
        "",
    ]

    def _run_single_scenario(
        idx: int,
        scenario: Dict[str, object],
        scenario_matches: int,
        *,
        rl_agent_local: Optional[SeaEngineRLAgent] = None,
        opponent_agent_local: Optional[SeaEngineAgent] = None,
        local_history_limit: Optional[int] = history_limit,
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
            history_limit=local_history_limit,
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
            "leader_hp_stats": dict(summary.get("leader_hp_stats", {})),
            "report_path": summary["report_path"],
            "history_path": None if scenario_history_path is None else str(scenario_history_path),
        }

    def _run_scenario_shard(
        idx: int,
        scenario: Dict[str, object],
        shard_idx: int,
        shard_matches: int,
    ) -> Dict[str, object]:
        shard_label = f"{scenario['label']}/shard{shard_idx + 1}"
        shard_scenario = dict(scenario)
        shard_scenario["label"] = shard_label
        shard_history_limit = history_limit
        if history_limit is not None:
            shard_history_limit = max(1, (int(history_limit) + scenario_shard_count - 1) // scenario_shard_count)
        return _run_single_scenario(idx, shard_scenario, shard_matches, local_history_limit=shard_history_limit)

    def _merge_scenario_shards(idx: int, scenario: Dict[str, object], shard_rows: list[Dict[str, object]]) -> Dict[str, object]:
        scenario_label = str(scenario["label"])
        episodes = sum(int(row["matches"]) for row in shard_rows)
        rl_wins = sum(int(row["rl_wins"]) for row in shard_rows)
        opp_wins = sum(int(row["opp_wins"]) for row in shard_rows)
        draws = sum(int(row["draws"]) for row in shard_rows)
        avg_steps = 0.0 if episodes <= 0 else sum(float(row["avg_steps"]) * int(row["matches"]) for row in shard_rows) / episodes
        avg_turn = 0.0 if episodes <= 0 else sum(float(row["avg_final_turn"]) * int(row["matches"]) for row in shard_rows) / episodes
        action_counts: Counter[str] = Counter()
        card_counts: Counter[str] = Counter()
        for row in shard_rows:
            action_counts.update(row.get("action_type_counts", {}))
            card_counts.update(row.get("card_use_counts", {}))

        wr = (rl_wins / episodes * 100.0) if episodes > 0 else 0.0
        p1_wins = rl_wins if bool(scenario["rl_is_p1"]) else opp_wins
        p2_wins = opp_wins if bool(scenario["rl_is_p1"]) else rl_wins
        merged_summary = {
            "episodes": episodes,
            "p1_agent": "rl" if bool(scenario["rl_is_p1"]) else "opponent",
            "p2_agent": "opponent" if bool(scenario["rl_is_p1"]) else "rl",
            "p1_wins": p1_wins,
            "p2_wins": p2_wins,
            "draws": draws,
            "avg_steps": avg_steps,
            "avg_final_turn": avg_turn,
            "action_type_counts": dict(sorted(action_counts.items())),
            "card_use_counts": dict(card_counts.most_common()),
        }
        scenario_report_path = _scenario_report_path(label=scenario_label, report_path=report_path)
        shard_report_lines = [f"- {row['label']}: report={row['report_path']}" for row in shard_rows]
        scenario_report_text = "\n".join(
            [
                f"=== Scenario {scenario_label} Sharded Aggregate ===",
                f"scenario_shards={len(shard_rows)}",
                "",
                build_win_rate_report(merged_summary),
                "",
                "=== Shard Reports ===",
                *shard_report_lines,
            ]
        )
        saved_scenario_report = save_report(scenario_report_text.rstrip() + "\n", scenario_report_path)

        scenario_history_path = None
        if include_history:
            scenario_slug = _combo_slug(*scenario_label.split("/"))
            history_lines = [
                f"=== Scenario {scenario_label} Sharded Histories ===",
                f"report={saved_scenario_report}",
                "",
                "=== Shard Histories ===",
            ]
            for row in shard_rows:
                history_lines.append(f"- {row['label']}: history={row.get('history_path')}")
            if report_path is None:
                scenario_history_path = _default_report_path(f"se_bal_{scenario_slug}_hist")
            else:
                base = Path(report_path)
                scenario_history_path = base.with_name(f"{base.stem}_{scenario_slug}_hist.txt")
            save_report("\n".join(history_lines).rstrip() + "\n", scenario_history_path)

        return {
            "index": idx,
            "label": scenario_label,
            "matches": episodes,
            "rl_wins": rl_wins,
            "opp_wins": opp_wins,
            "draws": draws,
            "win_rate_percent": wr,
            "avg_steps": avg_steps,
            "avg_final_turn": avg_turn,
            "action_type_counts": dict(sorted(action_counts.items())),
            "card_use_counts": dict(card_counts.most_common()),
            "leader_hp_stats": {},
            "report_path": str(saved_scenario_report),
            "history_path": None if scenario_history_path is None else str(scenario_history_path),
            "shard_report_paths": [str(row.get("report_path", "")) for row in shard_rows if row.get("report_path")],
            "shard_history_paths": [str(row.get("history_path", "")) for row in shard_rows if row.get("history_path")],
        }

    if parallel_scenarios:
        with ThreadPoolExecutor(max_workers=scenario_worker_count, thread_name_prefix="se-bal") as executor:
            futures = []
            future_meta: Dict[object, tuple[int, Dict[str, object]]] = {}
            for idx, scenario in enumerate(scenarios):
                scenario_matches = per + (1 if idx < rem else 0)
                if scenario_matches <= 0:
                    continue
                if scenario_shard_count <= 1:
                    print(f"[*] Balance scenario {idx + 1}/{scenario_count} | {scenario['label']} | n={scenario_matches}")
                    futures.append(executor.submit(_run_single_scenario, idx, scenario, scenario_matches))
                    future_meta[futures[-1]] = (idx, scenario)
                    continue
                shard_per = scenario_matches // scenario_shard_count
                shard_rem = scenario_matches % scenario_shard_count
                print(
                    f"[*] Balance scenario {idx + 1}/{scenario_count} | {scenario['label']} | "
                    f"n={scenario_matches} | shards={scenario_shard_count}"
                )
                for shard_idx in range(scenario_shard_count):
                    shard_matches = shard_per + (1 if shard_idx < shard_rem else 0)
                    if shard_matches <= 0:
                        continue
                    fut = executor.submit(_run_scenario_shard, idx, scenario, shard_idx, shard_matches)
                    futures.append(fut)
                    future_meta[fut] = (idx, scenario)
            shard_groups: Dict[int, list[Dict[str, object]]] = {}
            scenario_by_index: Dict[int, Dict[str, object]] = {}
            for fut in as_completed(futures):
                idx, scenario = future_meta[fut]
                row = fut.result()
                if scenario_shard_count <= 1:
                    scenario_results.append(row)
                else:
                    shard_groups.setdefault(idx, []).append(row)
                    scenario_by_index[idx] = scenario
            if scenario_shard_count > 1:
                for idx, rows in shard_groups.items():
                    rows.sort(key=lambda row: str(row["label"]))
                    scenario_results.append(_merge_scenario_shards(idx, scenario_by_index[idx], rows))
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
            f"leader_hp={_format_leader_hp_stats(dict(scenario.get('leader_hp_stats', {}) or {}))}, "
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
    eval_rule_agent: Optional[SeaEngineAgent] = None,
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
    save_interval: int = 1000,
    checkpoint_interval: int = 1000,
    checkpoint_eval_matches: Optional[int] = None,
    include_eval_history: bool = True,
    resume_model_path: Optional[str] = None,
    resume_episodes_completed: Optional[int] = None,
    resume_skip_pre_eval: bool = False,
    summary_report_path: Optional[str] = None,
    eval_belief_mcts: bool = True,
    skip_prepost_eval: bool = True,
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
    rule_eval_opponent = (
        SeaEngineRuleBasedAgent(seed=_seed_with_offset(seed, 252))
        if eval_rule_agent is None
        else eval_rule_agent
    )
    if train_opponent_pool is None:
        if fast_pool_enabled:
            opponent_pool = [SeaEngineRandomAgent(seed=_seed_with_offset(seed, 303))]
        else:
            opponent_pool = trainer.build_default_opponent_pool(seed=_seed_with_offset(seed, 303))
    else:
        opponent_pool = list(train_opponent_pool)

    if num_envs is None:
        env_num_envs_raw = os.getenv("SEAENGINE_NUM_ENVS", "").strip()
        if env_num_envs_raw:
            try:
                num_envs = max(1, int(env_num_envs_raw))
            except ValueError:
                num_envs = None
    if num_envs is None:
        num_envs = 1
    scenario_workers = _default_scenario_workers()

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
    deficit_start_schedule = _build_deficit_start_schedule(
        train_episodes=train_episodes,
        seed=_seed_with_offset(seed, 505),
    )

    backend = os.getenv("SEAENGINE_VECTOR_BACKEND", "local")
    local_threads = os.getenv("SEAENGINE_LOCAL_THREADS", "1")
    print(
        f"[*] Experiment start | eval_matches_per_combo={eval_matches} (per suite total {eval_matches * 8}, all pre/post suites total {0 if skip_prepost_eval else eval_matches * 32}) | train_episodes={train_episodes} | "
        f"max_turns={max_turns} | update_interval={update_interval} | num_envs={num_envs} | "
        f"vector_backend={backend} | local_threads={local_threads} | "
        f"device={resolved_device} | model_hidden_dim={getattr(learning_agent, 'hidden_dim', default_model_hidden_dim())} | "
        f"train_max_turns={train_max_turns} | train_update_interval={train_update_interval} | "
        f"fast_pool={fast_pool_enabled} | save_interval={save_interval} | checkpoint_interval={checkpoint_interval} | "
        f"ppo_lr={trainer.config.learning_rate} | ppo_entropy={trainer.config.entropy_coef} | "
        f"ppo_clip={trainer.config.clip_epsilon} | ppo_epochs={trainer.config.update_epochs} | "
        f"layout_mode={getattr(trainer, '_layout_mode', 'balanced')} | layout_seed={getattr(trainer, '_layout_seed', '17011')} | "
        f"scenario_workers={scenario_workers} | "
        f"prepost_eval={not skip_prepost_eval} | "
        f"eval_belief_mcts={eval_belief_mcts} | "
        f"checkpoint_eval_per_combo={checkpoint_eval_matches} (per suite total {checkpoint_eval_matches * 8}, all checkpoint suites total {checkpoint_eval_matches * 24})"
    )
    print(f"[*] Opp plan total: {_format_plan_counts(training_opponent_counts)}")
    for plan_start in range(0, train_episodes, checkpoint_interval):
        plan_end = min(train_episodes, plan_start + checkpoint_interval)
        plan_counts = Counter(training_opponent_schedule[plan_start:plan_end])
        print(f"[*] Opp plan {plan_start + 1}~{plan_end}: {_format_plan_counts(plan_counts)}")

    summary_snapshot_path = Path(summary_report_path) if summary_report_path else None

    def _write_summary_snapshot(stage: str, extra_lines: Optional[list[str]] = None) -> None:
        if summary_snapshot_path is None:
            return
        lines = [
            "=== SeaEngine Train/Eval Experiment (Running) ===",
            f"stage={stage}",
            f"device={resolved_device}",
            f"train_episodes={train_episodes}",
            f"eval_matches={eval_matches}",
            f"max_turns={max_turns}",
            f"update_interval={update_interval}",
            f"opponent_pool={[agent.name for agent in opponent_pool]}",
            f"resume_model_path={resume_model_path or ''}",
            "",
        ]
        if extra_lines:
            lines.extend(extra_lines)
        try:
            save_report("\n".join(lines).rstrip() + "\n", summary_snapshot_path)
        except Exception as exc:
            print(f"[!] failed to update start summary snapshot: {exc}")

    def _compact_eval_line(name: str, summary: Dict[str, object]) -> str:
        episodes = int(summary.get("episodes", 0))
        p1_wins = int(summary.get("p1_wins", 0))
        p2_wins = int(summary.get("p2_wins", 0))
        draws = int(summary.get("draws", 0))
        avg_steps = float(summary.get("avg_steps", 0.0))
        avg_final_turn = float(summary.get("avg_final_turn", 0.0))
        p1_rate = 0.0 if episodes == 0 else 100.0 * p1_wins / episodes
        p2_rate = 0.0 if episodes == 0 else 100.0 * p2_wins / episodes
        draw_rate = 0.0 if episodes == 0 else 100.0 * draws / episodes
        return (
            f"{name}=episodes={episodes}, p1_wins={p1_wins} ({p1_rate:.1f}%), "
            f"p2_wins={p2_wins} ({p2_rate:.1f}%), draws={draws} ({draw_rate:.1f}%), "
            f"avg_steps={avg_steps:.2f}, avg_final_turn={avg_final_turn:.2f}, "
            f"report={summary.get('report_path', '')}"
        )

    def _compact_train_line(train_summary: Dict[str, object]) -> str:
        episodes = int(train_summary.get("episodes", 0))
        wins = int(train_summary.get("wins", 0))
        losses = int(train_summary.get("losses", 0))
        draws = int(train_summary.get("draws", 0))
        updates = int(train_summary.get("updates", 0))
        win_rate = 0.0 if episodes == 0 else 100.0 * wins / episodes
        avg_speed = 0.0
        last_update = dict(train_summary.get("last_update", {}) or {})
        parts = [
            f"episodes={episodes}",
            f"wins={wins} ({win_rate:.1f}%)",
            f"losses={losses}",
            f"draws={draws}",
            f"updates={updates}",
        ]
        if last_update:
            parts.append(
                "last_update="
                + ",".join(
                    f"{key}={float(last_update.get(key, 0.0)):.4f}"
                    for key in ("policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction", "grad_norm")
                )
            )
        if episodes > 0:
            start_time = float(train_summary.get("train_elapsed_sec", 0.0) or 0.0)
            if start_time > 0.0:
                avg_speed = episodes / start_time
        if avg_speed > 0.0:
            parts.append(f"avg_speed={avg_speed:.2f} eps/s")
        parts.append(f"opponents={train_summary.get('opponent_stats', {})}")
        parts.append(f"start_modes={train_summary.get('start_mode_stats', {})}")
        parts.append(f"burnin_profiles={train_summary.get('burnin_profile_stats', {})}")
        parts.append(f"layouts={train_summary.get('layout_stats', {})}")
        return "train=" + " | ".join(parts)

    _write_summary_snapshot(
        "initialized",
        [
            "before_training=pending",
            "training=pending",
            "after_training=pending",
            f"training_layout_mode={getattr(trainer, '_layout_mode', 'balanced')}",
            f"training_layout_seed={getattr(trainer, '_layout_seed', '17011')}",
            "",
        ],
    )

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

    if skip_prepost_eval:
        print("[*] Pre/post evaluation disabled; training-only run.")
        before_random = _make_skipped_eval_summary("random")
        before_random_history_path = None
        before_greedy = _make_skipped_eval_summary("greedy")
        before_greedy_history_path = None
        before_rule = _make_skipped_eval_summary("rule_based")
        before_rule_history_path = None
        before_self = _make_skipped_eval_summary("self")
        before_self_history_path = None
    elif resume_model_path and resume_skip_pre_eval:
        print("[*] Resume mode: skipping before-training evaluations.")
        before_random = _make_skipped_eval_summary("random")
        before_random_history_path = None
        before_greedy = _make_skipped_eval_summary("greedy")
        before_greedy_history_path = None
        before_rule = _make_skipped_eval_summary("rule_based")
        before_rule_history_path = None
        before_self = _make_skipped_eval_summary("self")
        before_self_history_path = None
    else:
        print(f"[*] Evaluating before training vs random across 8 combos ({eval_matches} each)...")
        before_random_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=random_eval_opponent,
            opponent_label="random",
            suite_title="Before Training vs Random",
            history_tag="se_evalhist_before_random",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_before_random",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        before_random = before_random_suite["history_summary"]
        before_random_history_path = None
        if include_eval_history:
            before_random_history_path = _save_history_report(
                prefix="se_evalhist_before_random",
                title="Before Training vs Random Histories",
                summary=before_random,
            )
            if before_random_history_path is not None:
                before_random["report_path"] = str(before_random_history_path)
        _write_summary_snapshot(
            "before_random_done",
            [
                "before_training=random done",
                f"before_random={before_random['report_path']}",
                "",
            ],
        )

        print(f"[*] Evaluating before training vs greedy across 8 combos ({eval_matches} each)...")
        before_greedy_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=greedy_eval_opponent,
            opponent_label="greedy",
            suite_title="Before Training vs Greedy",
            history_tag="se_evalhist_before_greedy",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_before_greedy",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        before_greedy = before_greedy_suite["history_summary"]
        before_greedy_history_path = None
        if include_eval_history:
            before_greedy_history_path = _save_history_report(
                prefix="se_evalhist_before_greedy",
                title="Before Training vs Greedy Histories",
                summary=before_greedy,
            )
            if before_greedy_history_path is not None:
                before_greedy["report_path"] = str(before_greedy_history_path)
        _write_summary_snapshot(
            "before_greedy_done",
            [
                "before_training=greedy done",
                f"before_random={before_random['report_path']}",
                f"before_greedy={before_greedy['report_path']}",
                "",
            ],
        )

        print(f"[*] Evaluating before training vs rule-based across 8 combos ({eval_matches} each)...")
        before_rule_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=rule_eval_opponent,
            opponent_label="rule_based",
            suite_title="Before Training vs Rule-Based",
            history_tag="se_evalhist_before_rule",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_before_rule",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        before_rule = before_rule_suite["history_summary"]
        before_rule_history_path = None
        if include_eval_history:
            before_rule_history_path = _save_history_report(
                prefix="se_evalhist_before_rule",
                title="Before Training vs Rule-Based Histories",
                summary=before_rule,
            )
            if before_rule_history_path is not None:
                before_rule["report_path"] = str(before_rule_history_path)
        _write_summary_snapshot(
            "before_rule_done",
            [
                "before_training=rule-based done",
                f"before_random={before_random['report_path']}",
                f"before_greedy={before_greedy['report_path']}",
                f"before_rule={before_rule['report_path']}",
                "",
            ],
        )

        print(f"[*] Evaluating before training vs self across 8 combos ({eval_matches} each)...")
        before_self_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=learning_agent,
            opponent_label="self",
            suite_title="Before Training vs Self",
            history_tag="se_evalhist_before_self",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_before_self",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        before_self = before_self_suite["history_summary"]
        before_self_history_path = None
        if include_eval_history:
            before_self_history_path = _save_history_report(
                prefix="se_evalhist_before_self",
                title="Before Training vs Self Histories",
                summary=before_self,
            )
            if before_self_history_path is not None:
                before_self["report_path"] = str(before_self_history_path)
        _write_summary_snapshot(
            "before_self_done",
            [
                "before_training=self done",
                f"before_random={before_random['report_path']}",
                f"before_greedy={before_greedy['report_path']}",
                f"before_rule={before_rule['report_path']}",
                f"before_self={before_self['report_path']}",
                "",
            ],
        )

    print("[*] Training starts...")
    checkpoints: list[Dict[str, object]] = []
    episodes_completed = resume_start_episodes
    last_train_summary: Dict[str, object] = {}
    recovery_next_chunk = False
    prev_checkpoint_greedy_wr: Optional[float] = None
    after_random = None
    after_greedy = None
    after_rule = None
    after_self = None

    while episodes_completed < train_episodes:
        chunk = min(checkpoint_interval, train_episodes - episodes_completed)
        recovery_override = False
        if recovery_next_chunk:
            recovery_override = True
            recovery_next_chunk = False
            print("[*] Recovery mode: next chunk schedule is stabilized (r/g heavy).")

        chunk_schedule = training_opponent_schedule[episodes_completed:episodes_completed + chunk]
        chunk_start_modes = deficit_start_schedule[episodes_completed:episodes_completed + chunk]
        if recovery_override:
            chunk_schedule = _build_recovery_schedule(
                chunk_episodes=chunk,
                num_envs=num_envs,
                opponent_pool=opponent_pool,
                seed=_seed_with_offset(seed, 7000 + episodes_completed),
            )
        print(f"[*] Training chunk {episodes_completed + 1}-{episodes_completed + chunk}...")
        chunk_train_start = time.perf_counter()
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
            start_mode_schedule=chunk_start_modes,
            log_interval=200,
            save_interval=save_interval,
            episode_offset=episodes_completed,
        )
        train_summary = dict(train_summary)
        train_summary["train_elapsed_sec"] = max(1e-9, time.perf_counter() - chunk_train_start)
        episodes_completed += chunk
        last_train_summary = train_summary

        suite = None
        rule_suite = None
        self_suite = None
        if episodes_completed < train_episodes:
            print(
                f"[*] Checkpoint {episodes_completed}/{train_episodes} -> "
                f"evaluating greedy/rule-based/self across {checkpoint_eval_matches * 24} matches..."
            )
            suite = _run_8combo_opponent_eval_suite(
                trainer=trainer,
                rl_agent=learning_agent,
                opponent_agent=SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 505 + episodes_completed)),
                opponent_label="greedy",
                suite_title=f"Checkpoint {episodes_completed} vs Greedy",
                history_tag=f"se_ckpt_{episodes_completed}",
                checkpoint_episodes=episodes_completed,
                num_matches_per_combo=checkpoint_eval_matches,
                card_data_path=card_data_path,
                max_turns=max_turns,
                scenario_report_prefix="se_ckpt",
                scenario_workers=scenario_workers,
                use_belief_mcts=eval_belief_mcts,
            )
            rule_suite = _run_8combo_opponent_eval_suite(
                trainer=trainer,
                rl_agent=learning_agent,
                opponent_agent=SeaEngineRuleBasedAgent(seed=_seed_with_offset(seed, 555 + episodes_completed)),
                opponent_label="rule_based",
                suite_title=f"Checkpoint {episodes_completed} vs Rule-Based",
                history_tag=f"se_ckpt_{episodes_completed}_rule",
                checkpoint_episodes=episodes_completed,
                num_matches_per_combo=checkpoint_eval_matches,
                card_data_path=card_data_path,
                max_turns=max_turns,
                scenario_report_prefix="se_ckpt_rule",
                scenario_workers=scenario_workers,
                use_belief_mcts=eval_belief_mcts,
            )
            self_suite = _run_8combo_opponent_eval_suite(
                trainer=trainer,
                rl_agent=learning_agent,
                opponent_agent=learning_agent,
                opponent_label="self",
                suite_title=f"Checkpoint {episodes_completed} vs Self",
                history_tag=f"se_ckpt_{episodes_completed}_self",
                checkpoint_episodes=episodes_completed,
                num_matches_per_combo=checkpoint_eval_matches,
                card_data_path=card_data_path,
                max_turns=max_turns,
                scenario_report_prefix="se_ckpt_self",
                scenario_workers=scenario_workers,
                use_belief_mcts=eval_belief_mcts,
            )
            checkpoint_text = "\n".join(
                [
                    f"=== Checkpoint {episodes_completed} Episodes ===",
                    f"opponent_stats={train_summary.get('opponent_stats', {})}",
                    suite["text"],
                    rule_suite["text"],
                    self_suite["text"],
                    "",
                    f"train_summary={train_summary}",
                    "",
                ]
            )
        else:
            print(f"[*] Final checkpoint {episodes_completed}/{train_episodes} saved (no checkpoint eval suite).")
            checkpoint_text = "\n".join(
                [
                    f"=== Checkpoint {episodes_completed} Episodes ===",
                    f"opponent_stats={train_summary.get('opponent_stats', {})}",
                    "=== Final checkpoint: checkpoint eval suite skipped ===",
                    "",
                    f"train_summary={train_summary}",
                    "",
                ]
            )
        population_score = _checkpoint_population_score(greedy_suite=suite, self_suite=self_suite)
        checkpoint_text += (
            "=== Population-Based Checkpoint Score ===\n"
            f"score={population_score['score']:.4f}\n"
            f"greedy_wr={population_score['greedy_wr'] * 100.0:.2f}%\n"
            f"self_wr={population_score['self_wr'] * 100.0:.2f}%\n"
            f"worst_combo_wr={population_score['worst_combo_wr'] * 100.0:.2f}%\n"
            f"max_side_gap={population_score['max_side_gap'] * 100.0:.2f}pp\n"
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
                "suite_results": [] if suite is None else suite["results"],
                "suite_text": "" if suite is None else suite["text"],
                "rule_suite_results": [] if rule_suite is None else rule_suite["results"],
                "rule_suite_text": "" if rule_suite is None else rule_suite["text"],
                "self_suite_results": [] if self_suite is None else self_suite["results"],
                "self_suite_text": "" if self_suite is None else self_suite["text"],
                "population_score": population_score,
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
        if suite is not None:
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

    if skip_prepost_eval:
        after_random = _make_skipped_eval_summary("random")
        after_random_history_path = None
        after_greedy = _make_skipped_eval_summary("greedy")
        after_greedy_history_path = None
        after_rule = _make_skipped_eval_summary("rule_based")
        after_rule_history_path = None
        after_self = _make_skipped_eval_summary("self")
        after_self_history_path = None
    else:
        print(f"[*] Evaluating after training vs random across 8 combos ({eval_matches} each)...")
        after_random_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=SeaEngineRandomAgent(seed=_seed_with_offset(seed, 404)),
            opponent_label="random",
            suite_title="After Training vs Random",
            history_tag="se_evalhist_after_random",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_after_random",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        after_random = after_random_suite["history_summary"]
        after_random_history_path = None
        if include_eval_history:
            after_random_history_path = _save_history_report(
                prefix="se_evalhist_after_random",
                title="After Training vs Random Histories",
                summary=after_random,
            )
            if after_random_history_path is not None:
                after_random["report_path"] = str(after_random_history_path)
        _write_summary_snapshot("after_random_done", [f"after_random={after_random['report_path']}", ""])

        print(f"[*] Evaluating after training vs greedy across 8 combos ({eval_matches} each)...")
        after_greedy_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 505)),
            opponent_label="greedy",
            suite_title="After Training vs Greedy",
            history_tag="se_evalhist_after_greedy",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_after_greedy",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        after_greedy = after_greedy_suite["history_summary"]
        after_greedy_history_path = None
        if include_eval_history:
            after_greedy_history_path = _save_history_report(
                prefix="se_evalhist_after_greedy",
                title="After Training vs Greedy Histories",
                summary=after_greedy,
            )
            if after_greedy_history_path is not None:
                after_greedy["report_path"] = str(after_greedy_history_path)
        _write_summary_snapshot(
            "after_greedy_done",
            [f"after_random={after_random['report_path']}", f"after_greedy={after_greedy['report_path']}", ""],
        )

        print(f"[*] Evaluating after training vs rule-based across 8 combos ({eval_matches} each)...")
        after_rule_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=SeaEngineRuleBasedAgent(seed=_seed_with_offset(seed, 555)),
            opponent_label="rule_based",
            suite_title="After Training vs Rule-Based",
            history_tag="se_evalhist_after_rule",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_after_rule",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        after_rule = after_rule_suite["history_summary"]
        after_rule_history_path = None
        if include_eval_history:
            after_rule_history_path = _save_history_report(
                prefix="se_evalhist_after_rule",
                title="After Training vs Rule-Based Histories",
                summary=after_rule,
            )
            if after_rule_history_path is not None:
                after_rule["report_path"] = str(after_rule_history_path)
        _write_summary_snapshot(
            "after_rule_done",
            [
                f"after_random={after_random['report_path']}",
                f"after_greedy={after_greedy['report_path']}",
                f"after_rule={after_rule['report_path']}",
                "",
            ],
        )

        print(f"[*] Evaluating after training vs self across 8 combos ({eval_matches} each)...")
        after_self_suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=learning_agent,
            opponent_label="self",
            suite_title="After Training vs Self",
            history_tag="se_evalhist_after_self",
            num_matches_per_combo=eval_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            scenario_report_prefix="se_after_self",
            scenario_workers=scenario_workers,
            use_belief_mcts=eval_belief_mcts,
        )
        after_self = after_self_suite["history_summary"]
        after_self_history_path = None
        if include_eval_history:
            after_self_history_path = _save_history_report(
                prefix="se_evalhist_after_self",
                title="After Training vs Self Histories",
                summary=after_self,
            )
            if after_self_history_path is not None:
                after_self["report_path"] = str(after_self_history_path)
        _write_summary_snapshot(
            "after_self_done",
            [
                f"after_random={after_random['report_path']}",
                f"after_greedy={after_greedy['report_path']}",
                f"after_rule={after_rule['report_path']}",
                f"after_self={after_self['report_path']}",
                "",
            ],
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
        "=== Before Training vs Rule-Based ===",
        f"report={before_rule['report_path']}",
        f"history={None if before_rule_history_path is None else str(before_rule_history_path)}",
        build_win_rate_report(before_rule),
        "",
        "=== Before Training vs Self ===",
        f"report={before_self['report_path']}",
        f"history={None if before_self_history_path is None else str(before_self_history_path)}",
        build_win_rate_report(before_self),
        "",
        "=== Training Summary ===",
        str(last_train_summary),
        "",
        "=== Checkpoints ===",
        "\n".join(f"- ep {ckpt['episodes_completed']}: {ckpt['report_path']}" for ckpt in checkpoints),
        "",
        "=== Population-Based Checkpoint Selection ===",
        "\n".join(
            f"- ep {ckpt['episodes_completed']}: score={dict(ckpt.get('population_score', {})).get('score', 0.0):.4f}, "
            f"greedy_wr={dict(ckpt.get('population_score', {})).get('greedy_wr', 0.0) * 100.0:.2f}%, "
            f"self_wr={dict(ckpt.get('population_score', {})).get('self_wr', 0.0) * 100.0:.2f}%, "
            f"worst_combo={dict(ckpt.get('population_score', {})).get('worst_combo_wr', 0.0) * 100.0:.2f}%, "
            f"max_side_gap={dict(ckpt.get('population_score', {})).get('max_side_gap', 0.0) * 100.0:.2f}pp"
            for ckpt in checkpoints
        ),
        f"selected_checkpoint_ep={max(checkpoints, key=lambda ckpt: dict(ckpt.get('population_score', {})).get('score', -999.0))['episodes_completed'] if checkpoints else ''}",
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
        "",
        "=== After Training vs Rule-Based ===",
        f"report={after_rule['report_path']}",
        f"history={None if after_rule_history_path is None else str(after_rule_history_path)}",
        build_win_rate_report(after_rule),
        "",
        "=== After Training vs Self ===",
        f"report={after_self['report_path']}",
        f"history={None if after_self_history_path is None else str(after_self_history_path)}",
        build_win_rate_report(after_self),
    ]

    report_text = "\n".join(report_lines)
    saved_path = save_report(report_text, _default_report_path() if report_path is None else report_path)
    if summary_snapshot_path is not None:
        checkpoint_lines = [
            f"checkpoint_count={len(checkpoints)}",
            *[
                f"checkpoint_ep={ckpt['episodes_completed']} | report={ckpt['report_path']} | score={dict(ckpt.get('population_score', {})).get('score', 0.0):.4f}"
                for ckpt in checkpoints
            ],
        ]
        _write_summary_snapshot(
            "final",
            [
                _compact_eval_line("before_random", before_random),
                _compact_eval_line("before_greedy", before_greedy),
                _compact_eval_line("before_rule", before_rule),
                _compact_eval_line("before_self", before_self),
                _compact_train_line(last_train_summary),
                _compact_eval_line("after_random", after_random),
                _compact_eval_line("after_greedy", after_greedy),
                _compact_eval_line("after_rule", after_rule),
                _compact_eval_line("after_self", after_self),
                f"total_wall_time_sec={max(0.0, time.perf_counter() - artifact_start_wall):.1f}",
                f"selected_checkpoint_ep={max(checkpoints, key=lambda ckpt: dict(ckpt.get('population_score', {})).get('score', -999.0))['episodes_completed'] if checkpoints else ''}",
                *checkpoint_lines,
                f"final_report={saved_path}",
                "",
            ],
        )
    zipped_logs = _zip_new_log_txt_files(
        since_timestamp=artifact_start_wall,
        output_path=Path(__file__).resolve().parent.parent / "log" / "start_latest.zip",
        cleanup_after_zip=True,
        keep_names={"start_summary.txt"},
    )
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
        "before_rule": before_rule,
        "before_random_history_path": None if before_random_history_path is None else str(before_random_history_path),
        "before_greedy_history_path": None if before_greedy_history_path is None else str(before_greedy_history_path),
        "before_rule_history_path": None if before_rule_history_path is None else str(before_rule_history_path),
        "before_self_history_path": None if before_self_history_path is None else str(before_self_history_path),
        "train": last_train_summary,
        "after_random": after_random,
        "after_greedy": after_greedy,
        "after_rule": after_rule,
        "after_self": after_self,
        "after_random_history_path": None if after_random_history_path is None else str(after_random_history_path),
        "after_greedy_history_path": None if after_greedy_history_path is None else str(after_greedy_history_path),
        "after_rule_history_path": None if after_rule_history_path is None else str(after_rule_history_path),
        "after_self_history_path": None if after_self_history_path is None else str(after_self_history_path),
        "checkpoints": checkpoints,
        "report_text": report_text,
        "report_path": str(saved_path),
        "summary_report_path": str(summary_snapshot_path or saved_path),
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
    zipped_logs = _zip_new_log_txt_files(
        since_timestamp=artifact_start_wall,
        output_path=Path(__file__).resolve().parent.parent / "log" / "start_latest.zip",
        cleanup_after_zip=True,
        keep_names={"start_summary.txt"},
    )
    zipped_models = _zip_new_model_files(since_timestamp=artifact_start_wall)
    return {
        "before_greedy": before_greedy,
        "checkpoints": checkpoints,
        "summary_text": summary_text,
        "summary_report_path": str(saved_path),
        "log_zip_path": None if zipped_logs is None else str(zipped_logs),
        "model_zip_path": None if zipped_models is None else str(zipped_models),
    }
