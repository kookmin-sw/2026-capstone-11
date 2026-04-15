from __future__ import annotations

from datetime import datetime
from collections import Counter
import os
import random
from pathlib import Path
import time
import zipfile
from typing import Dict, Optional, Sequence

from RL_AI.SeaEngine.agents import SeaEngineAgent, SeaEngineGreedyAgent, SeaEngineRLAgent, SeaEngineRandomAgent
from RL_AI.SeaEngine.evaluator import evaluate_agents
from RL_AI.SeaEngine.trainer import SeaEnginePPOTrainer
from RL_AI.analysis.reports import build_win_rate_report, save_report


def _default_report_path(prefix: str = "se_te") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.txt"


def _default_log_zip_path(prefix: str = "se_logs") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.zip"


def _default_model_zip_path(prefix: str = "se_models") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "models" / f"{prefix}_{ts}.zip"


def _seed_with_offset(seed: Optional[int], offset: int) -> Optional[int]:
    return None if seed is None else seed + offset


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

    for episode_start in range(0, train_episodes, num_envs):
        actual_num_envs = min(num_envs, train_episodes - episode_start)
        progress = (episode_start + actual_num_envs) / max(1, train_episodes)

        if progress <= 0.3:
            target_weights: Dict[str, float] = {"random": 1.0}
        elif progress <= 0.7:
            target_weights = {"random": 0.6, "greedy": 0.4}
        else:
            target_weights = {"random": 0.35, "greedy": 0.35}
            self_names = [name for name in current_pool_names if name.startswith("self_ep_")]
            if self_names:
                self_weight = 0.30 / len(self_names)
                for self_name in self_names:
                    target_weights[self_name] = self_weight
            else:
                target_weights["random"] += 0.15
                target_weights["greedy"] += 0.15

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
    lines = [
        f"--- Match {int(match_history.get('match_index', 0))} ---",
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
) -> Dict[str, object]:
    resolved_device = _resolve_device(device)
    learning_agent = SeaEngineRLAgent(seed=seed, device=resolved_device) if agent is None else agent
    trainer = SeaEnginePPOTrainer(learning_agent)
    overall_start = time.time()

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

    print("[*] Evaluating before training vs random...")
    before_random_start = time.time()
    before_random = trainer.evaluate(
        opponent_agent=random_eval_opponent,
        num_matches=eval_matches,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=max_turns,
        progress_callback=log_eval_progress("before-random"),
    )
    before_random_elapsed = time.time() - before_random_start

    print("[*] Evaluating before training vs greedy...")
    before_greedy_start = time.time()
    before_greedy = trainer.evaluate(
        opponent_agent=greedy_eval_opponent,
        num_matches=eval_matches,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=max_turns,
        progress_callback=log_eval_progress("before-greedy"),
    )
    before_greedy_elapsed = time.time() - before_greedy_start

    print("[*] Training starts...")
    train_elapsed = 0.0
    checkpoints: list[Dict[str, object]] = []
    episodes_completed = 0
    last_train_summary: Dict[str, object] = {}
    after_random = None
    after_greedy = None
    after_random_elapsed = 0.0
    after_greedy_elapsed = 0.0

    while episodes_completed < train_episodes:
        chunk = min(checkpoint_interval, train_episodes - episodes_completed)
        print(f"[*] Training chunk {episodes_completed + 1}-{episodes_completed + chunk}...")
        train_start = time.time()
        train_summary = trainer.train(
            num_episodes=chunk,
            opponent_pool=opponent_pool,
            opponent_schedule=training_opponent_schedule[episodes_completed:episodes_completed + chunk],
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
        chunk_elapsed = time.time() - train_start
        train_elapsed += chunk_elapsed
        episodes_completed += chunk
        last_train_summary = train_summary

        print(f"[*] Checkpoint {episodes_completed}/{train_episodes} -> evaluating {checkpoint_eval_matches * 8} matches...")
        suite_start = time.time()
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
        suite_elapsed = time.time() - suite_start
        checkpoint_text = "\n".join(
            [
                f"=== Checkpoint {episodes_completed} Episodes ===",
                f"train_time_sec={chunk_elapsed:.2f}",
                f"suite_time_sec={suite_elapsed:.2f}",
                suite["text"],
                "",
                f"train_summary={train_summary}",
                "",
            ]
        )
        checkpoint_path = save_report(checkpoint_text, _default_report_path(f"se_ckpt_{episodes_completed}"))
        checkpoints.append(
            {
                "episodes_completed": episodes_completed,
                "train_summary": train_summary,
                "train_time_sec": chunk_elapsed,
                "suite_time_sec": suite_elapsed,
                "suite_results": suite["results"],
                "suite_text": suite["text"],
                "report_path": str(checkpoint_path),
            }
        )

    print("[*] Evaluating after training vs random...")
    after_random_start = time.time()
    after_random = trainer.evaluate(
        opponent_agent=SeaEngineRandomAgent(seed=_seed_with_offset(seed, 404)),
        num_matches=eval_matches,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=max_turns,
        progress_callback=log_eval_progress("after-random"),
    )
    after_random_elapsed = time.time() - after_random_start

    print("[*] Evaluating after training vs greedy...")
    after_greedy_start = time.time()
    after_greedy = trainer.evaluate(
        opponent_agent=SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 505)),
        num_matches=eval_matches,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=max_turns,
        progress_callback=log_eval_progress("after-greedy"),
    )
    after_greedy_elapsed = time.time() - after_greedy_start
    total_elapsed = time.time() - overall_start

    report_lines = [
        "=== SeaEngine Train/Eval Experiment ===",
        f"train_episodes={train_episodes}",
        f"eval_matches={eval_matches}",
        f"max_turns={max_turns}",
        f"update_interval={update_interval}",
        f"opponent_pool={[agent.name for agent in opponent_pool]}",
        f"before_random_time_sec={before_random_elapsed:.2f}",
        f"before_greedy_time_sec={before_greedy_elapsed:.2f}",
        f"train_time_sec={train_elapsed:.2f}",
        f"after_random_time_sec={after_random_elapsed:.2f}",
        f"after_greedy_time_sec={after_greedy_elapsed:.2f}",
        f"total_time_sec={total_elapsed:.2f}",
        "",
        "=== Before Training vs Random ===",
        f"report={before_random['report_path']}",
        build_win_rate_report(before_random),
        "",
        "=== Before Training vs Greedy ===",
        f"report={before_greedy['report_path']}",
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
        build_win_rate_report(after_random),
        "",
        "=== After Training vs Greedy ===",
        f"report={after_greedy['report_path']}",
        build_win_rate_report(after_greedy),
    ]

    report_text = "\n".join(report_lines)
    saved_path = save_report(report_text, _default_report_path() if report_path is None else report_path)
    zipped_logs = _zip_new_log_txt_files(since_timestamp=overall_start)
    zipped_models = _zip_new_model_files(since_timestamp=overall_start)

    return {
        "before_random": before_random,
        "before_greedy": before_greedy,
        "before_random_time_sec": before_random_elapsed,
        "before_greedy_time_sec": before_greedy_elapsed,
        "train": last_train_summary,
        "train_time_sec": train_elapsed,
        "after_random": after_random,
        "after_greedy": after_greedy,
        "after_random_time_sec": after_random_elapsed,
        "after_greedy_time_sec": after_greedy_elapsed,
        "total_time_sec": total_elapsed,
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

    overall_start = time.time()
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
    )
    summary_lines.extend(
        [
            "=== Before Training vs Greedy ===",
            f"report={before_greedy['report_path']}",
            build_win_rate_report(before_greedy),
            "",
        ]
    )

    episodes_completed = 0
    while episodes_completed < total_train_episodes:
        chunk = min(eval_interval, total_train_episodes - episodes_completed)
        train_start = time.time()
        train_summary = trainer.train(
            num_episodes=chunk,
            opponent_pool=opponent_pool,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
            update_interval=update_interval,
        )
        train_elapsed = time.time() - train_start
        episodes_completed += chunk

        greedy_summary = trainer.evaluate(
            opponent_agent=SeaEngineGreedyAgent(seed=_seed_with_offset(seed, 900 + episodes_completed)),
            num_matches=eval_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
        )
        random_summary = trainer.evaluate(
            opponent_agent=SeaEngineRandomAgent(seed=_seed_with_offset(seed, 1200 + episodes_completed)),
            num_matches=eval_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
        )

        checkpoints.append(
            {
                "episodes_completed": episodes_completed,
                "train_summary": train_summary,
                "train_time_sec": train_elapsed,
                "greedy_summary": greedy_summary,
                "random_summary": random_summary,
            }
        )
        summary_lines.extend(
            [
                f"=== Checkpoint {episodes_completed} Episodes ===",
                f"train_time_sec={train_elapsed:.2f}",
                f"greedy_report={greedy_summary['report_path']}",
                build_win_rate_report(greedy_summary),
                "",
                f"random_report={random_summary['report_path']}",
                build_win_rate_report(random_summary),
                "",
                f"train_summary={train_summary}",
                "",
            ]
        )

    total_elapsed = time.time() - overall_start
    summary_lines.append(f"TOTAL_TIME_SEC={total_elapsed:.2f}")

    summary_text = "\n".join(summary_lines)
    saved_path = save_report(
        summary_text,
        _default_report_path("se_ckpt")
        if summary_report_path is None
        else summary_report_path,
    )
    zipped_logs = _zip_new_log_txt_files(since_timestamp=overall_start)
    zipped_models = _zip_new_model_files(since_timestamp=overall_start)
    return {
        "before_greedy": before_greedy,
        "checkpoints": checkpoints,
        "total_time_sec": total_elapsed,
        "summary_text": summary_text,
        "summary_report_path": str(saved_path),
        "log_zip_path": None if zipped_logs is None else str(zipped_logs),
        "model_zip_path": None if zipped_models is None else str(zipped_models),
    }
