from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import time
from typing import Dict, Optional, Sequence

from RL_AI.SeaEngine.agents import SeaEngineAgent, SeaEngineGreedyAgent, SeaEngineRLAgent, SeaEngineRandomAgent
from RL_AI.SeaEngine.trainer import SeaEnginePPOTrainer
from RL_AI.analysis.reports import build_win_rate_report, save_report


def _default_report_path(prefix: str = "seaengine_train_eval_report") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.txt"


def _seed_with_offset(seed: Optional[int], offset: int) -> Optional[int]:
    return None if seed is None else seed + offset


def _progress_print_interval(total: int) -> int:
    if total <= 100:
        return 100
    if total <= 1000:
        return 250
    return max(500, total // 4)


def _verbose_experiment_logs() -> bool:
    return os.getenv("SEAENGINE_VERBOSE_EXPERIMENT_LOG", "0") == "1"


def run_train_eval_experiment(
    *,
    agent: Optional[SeaEngineRLAgent] = None,
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
) -> Dict[str, object]:
    learning_agent = SeaEngineRLAgent(seed=seed) if agent is None else agent
    trainer = SeaEnginePPOTrainer(learning_agent)
    overall_start = time.time()

    # Fast-path defaults for large-scale simulation throughput.
    train_turn_cap = int(os.getenv("SEAENGINE_TRAIN_MAX_TURNS", "60"))
    min_update_interval = int(os.getenv("SEAENGINE_MIN_UPDATE_INTERVAL", "32"))
    fast_pool_enabled = os.getenv("SEAENGINE_FAST_POOL", "1") == "1"

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

    train_max_turns = min(max_turns, train_turn_cap)
    train_update_interval = max(update_interval, min_update_interval)

    backend = os.getenv("SEAENGINE_VECTOR_BACKEND", "local")
    local_threads = os.getenv("SEAENGINE_LOCAL_THREADS", "1")
    print(
        f"[*] Experiment start | eval_matches={eval_matches} | train_episodes={train_episodes} | "
        f"max_turns={max_turns} | update_interval={update_interval} | num_envs={num_envs} | "
        f"vector_backend={backend} | local_threads={local_threads} | "
        f"train_max_turns={train_max_turns} | train_update_interval={train_update_interval} | "
        f"fast_pool={fast_pool_enabled}"
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
    train_start = time.time()
    train_summary = trainer.train(
        num_episodes=train_episodes,
        opponent_pool=opponent_pool,
        card_data_path=card_data_path,
        player1_deck=player1_deck,
        player2_deck=player2_deck,
        max_turns=train_max_turns,
        update_interval=train_update_interval,
        progress_callback=log_train_progress if _verbose_experiment_logs() else None,
        num_envs=num_envs,
        log_interval=200,
    )
    train_elapsed = time.time() - train_start

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
        str(train_summary),
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

    return {
        "before_random": before_random,
        "before_greedy": before_greedy,
        "before_random_time_sec": before_random_elapsed,
        "before_greedy_time_sec": before_greedy_elapsed,
        "train": train_summary,
        "train_time_sec": train_elapsed,
        "after_random": after_random,
        "after_greedy": after_greedy,
        "after_random_time_sec": after_random_elapsed,
        "after_greedy_time_sec": after_greedy_elapsed,
        "total_time_sec": total_elapsed,
        "report_text": report_text,
        "report_path": str(saved_path),
    }


def run_checkpoint_training_experiment(
    *,
    agent: Optional[SeaEngineRLAgent] = None,
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
    learning_agent = SeaEngineRLAgent(seed=seed) if agent is None else agent
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
        _default_report_path("seaengine_checkpoint_training_report")
        if summary_report_path is None
        else summary_report_path,
    )
    return {
        "before_greedy": before_greedy,
        "checkpoints": checkpoints,
        "total_time_sec": total_elapsed,
        "summary_text": summary_text,
        "summary_report_path": str(saved_path),
    }
