from __future__ import annotations

# 학습 전 평가 -> 학습 -> 학습 후 평가를 한 번에 실행하는 실험 파일
# 빠르게 RL 사이클을 돌려보고, 전후 비교 결과를 텍스트 리포트로 저장하는 데 사용한다.

from datetime import datetime
from pathlib import Path
import time
from typing import Dict, Optional

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.agents.greedy_agent import GreedyAgent
from RL_AI.agents.random_agent import RandomAgent
from RL_AI.agents.rl_agent import RLAgent
from RL_AI.analysis.reports import build_win_rate_report, save_report
from RL_AI.training.trainer import PPOTrainer


def _default_report_path(prefix: str = "train_eval_report") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.txt"


def _seed_with_offset(seed: Optional[int], offset: int) -> Optional[int]:
    return None if seed is None else seed + offset


def run_train_eval_experiment(
    *,
    agent: Optional[RLAgent] = None,
    opponent_agent: Optional[BaseAgent] = None,
    eval_matches_before: int = 20,
    train_episodes: int = 50,
    eval_matches_after: int = 20,
    p1_world: int = 2,
    p2_world: int = 6,
    card_data_path: str = "Cards.csv",
    seed: Optional[int] = None,
    max_steps: int = 200,
    max_turns: Optional[int] = None,
    report_path: Optional[str] = None,
) -> Dict[str, object]:
    learning_agent = RLAgent(seed=seed) if agent is None else agent
    opponent = RandomAgent(seed=seed) if opponent_agent is None else opponent_agent
    trainer = PPOTrainer(learning_agent)

    before_summary = trainer.evaluate(
        opponent_agent=opponent,
        num_matches=eval_matches_before,
        p1_world=p1_world,
        p2_world=p2_world,
        card_data_path=card_data_path,
        seed=seed,
        max_steps=max_steps,
        max_turns=max_turns,
        enable_logging=False,
        print_steps=False,
    )

    train_summary = trainer.train(
        num_episodes=train_episodes,
        opponent_agent=opponent,
        p1_world=p1_world,
        p2_world=p2_world,
        card_data_path=card_data_path,
        seed=None if seed is None else seed + 10_000,
        max_steps=max_steps,
        max_turns=max_turns,
    )

    after_summary = trainer.evaluate(
        opponent_agent=opponent,
        num_matches=eval_matches_after,
        p1_world=p1_world,
        p2_world=p2_world,
        card_data_path=card_data_path,
        seed=None if seed is None else seed + 20_000,
        max_steps=max_steps,
        max_turns=max_turns,
        enable_logging=False,
        print_steps=False,
    )

    report_lines = [
        "=== Before Training ===",
        build_win_rate_report(before_summary),
        "",
        "=== Training Summary ===",
        str(train_summary),
        "",
        "=== After Training ===",
        build_win_rate_report(after_summary),
    ]
    report_text = "\n".join(report_lines)
    saved_path = save_report(report_text, _default_report_path() if report_path is None else report_path)

    return {
        "before": before_summary,
        "train": train_summary,
        "after": after_summary,
        "report_text": report_text,
        "report_path": str(saved_path),
    }


def run_checkpoint_training_experiment(
    *,
    agent: Optional[RLAgent] = None,
    train_opponent_agent: Optional[BaseAgent] = None,
    eval_opponent_agent: Optional[BaseAgent] = None,
    final_eval_opponent_agent: Optional[BaseAgent] = None,
    eval_matches: int = 100,
    total_train_episodes: int = 300,
    eval_interval: int = 100,
    final_random_eval_matches: int = 100,
    p1_world: int = 2,
    p2_world: int = 6,
    card_data_path: str = "Cards.csv",
    seed: Optional[int] = None,
    max_steps: int = 200,
    max_turns: Optional[int] = None,
    summary_report_path: Optional[str] = None,
) -> Dict[str, object]:
    learning_agent = RLAgent(seed=seed) if agent is None else agent
    trainer = PPOTrainer(learning_agent)

    train_opponent = RandomAgent(seed=_seed_with_offset(seed, 1_000)) if train_opponent_agent is None else train_opponent_agent
    eval_opponent = GreedyAgent(seed=_seed_with_offset(seed, 2_000)) if eval_opponent_agent is None else eval_opponent_agent
    final_eval_opponent = (
        RandomAgent(seed=_seed_with_offset(seed, 3_000))
        if final_eval_opponent_agent is None
        else final_eval_opponent_agent
    )

    summary_lines = [
        "=== Checkpoint Training Experiment ===",
        f"total_train_episodes={total_train_episodes}",
        f"eval_interval={eval_interval}",
        f"eval_matches={eval_matches}",
        f"final_random_eval_matches={final_random_eval_matches}",
        f"train_opponent={train_opponent.name}",
        f"eval_opponent={eval_opponent.name}",
        f"final_eval_opponent={final_eval_opponent.name}",
        f"max_steps={max_steps}",
        f"max_turns={max_turns}",
        "",
    ]

    checkpoint_results = []
    overall_start = time.time()

    before_start = time.time()
    before_summary = trainer.evaluate(
        opponent_agent=eval_opponent,
        num_matches=eval_matches,
        p1_world=p1_world,
        p2_world=p2_world,
        card_data_path=card_data_path,
        seed=_seed_with_offset(seed, 10_000),
        max_steps=max_steps,
        max_turns=max_turns,
        enable_logging=False,
        print_steps=False,
    )
    before_elapsed = time.time() - before_start
    summary_lines.extend(
        [
            "=== Before Training vs Greedy ===",
            f"time={before_elapsed:.2f}s",
            f"report={before_summary['report_path']}",
            build_win_rate_report(before_summary),
            "",
        ]
    )

    episodes_completed = 0
    checkpoint_index = 0
    while episodes_completed < total_train_episodes:
        chunk_size = min(eval_interval, total_train_episodes - episodes_completed)
        train_start = time.time()
        train_summary = trainer.train(
            num_episodes=chunk_size,
            opponent_agent=train_opponent,
            p1_world=p1_world,
            p2_world=p2_world,
            card_data_path=card_data_path,
            seed=_seed_with_offset(seed, 20_000 + episodes_completed),
            max_steps=max_steps,
            max_turns=max_turns,
        )
        train_elapsed = time.time() - train_start
        episodes_completed += chunk_size

        eval_start = time.time()
        checkpoint_summary = trainer.evaluate(
            opponent_agent=eval_opponent,
            num_matches=eval_matches,
            p1_world=p1_world,
            p2_world=p2_world,
            card_data_path=card_data_path,
            seed=_seed_with_offset(seed, 30_000 + checkpoint_index * 1_000),
            max_steps=max_steps,
            max_turns=max_turns,
            enable_logging=False,
            print_steps=False,
        )
        eval_elapsed = time.time() - eval_start

        checkpoint_record = {
            "episodes_completed": episodes_completed,
            "train_summary": train_summary,
            "train_time_sec": train_elapsed,
            "eval_summary": checkpoint_summary,
            "eval_time_sec": eval_elapsed,
        }
        checkpoint_results.append(checkpoint_record)

        summary_lines.extend(
            [
                f"=== Checkpoint {episodes_completed} Episodes vs Greedy ===",
                f"train_time={train_elapsed:.2f}s",
                f"eval_time={eval_elapsed:.2f}s",
                f"report={checkpoint_summary['report_path']}",
                f"train_summary={train_summary}",
                build_win_rate_report(checkpoint_summary),
                "",
            ]
        )
        checkpoint_index += 1

    final_random_start = time.time()
    final_random_summary = trainer.evaluate(
        opponent_agent=final_eval_opponent,
        num_matches=final_random_eval_matches,
        p1_world=p1_world,
        p2_world=p2_world,
        card_data_path=card_data_path,
        seed=_seed_with_offset(seed, 40_000),
        max_steps=max_steps,
        max_turns=max_turns,
        enable_logging=False,
        print_steps=False,
    )
    final_random_elapsed = time.time() - final_random_start
    total_elapsed = time.time() - overall_start

    summary_lines.extend(
        [
            f"=== Final Evaluation vs {final_eval_opponent.name} ===",
            f"time={final_random_elapsed:.2f}s",
            f"report={final_random_summary['report_path']}",
            build_win_rate_report(final_random_summary),
            "",
            f"TOTAL_TIME={total_elapsed:.2f}s",
        ]
    )

    summary_text = "\n".join(summary_lines)
    summary_path = save_report(
        summary_text,
        _default_report_path("checkpoint_training_report") if summary_report_path is None else summary_report_path,
    )

    return {
        "before": before_summary,
        "before_time_sec": before_elapsed,
        "checkpoints": checkpoint_results,
        "final_random": final_random_summary,
        "final_random_time_sec": final_random_elapsed,
        "total_time_sec": total_elapsed,
        "summary_text": summary_text,
        "summary_report_path": str(summary_path),
    }



