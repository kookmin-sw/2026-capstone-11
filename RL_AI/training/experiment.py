from __future__ import annotations

# 학습 전 평가 -> 학습 -> 학습 후 평가를 한 번에 실행하는 실험 파일
# 빠르게 RL 사이클을 돌려보고, 전후 비교 결과를 텍스트 리포트로 저장하는 데 사용한다.

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.agents.random_agent import RandomAgent
from RL_AI.agents.rl_agent import RLAgent
from RL_AI.analysis.reports import build_win_rate_report, save_report
from RL_AI.training.trainer import PPOTrainer


def _default_report_path(prefix: str = "train_eval_report") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent.parent / "log" / f"{prefix}_{ts}.txt"


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



