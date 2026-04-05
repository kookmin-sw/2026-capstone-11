from __future__ import annotations

# 평가 결과를 사람이 읽기 쉬운 텍스트 리포트로 바꾸는 파일
# 현재는 승/패/무, 승률, 평균 스텝 수, 행동 타입 통계, 카드 사용 통계를 제공한다.

from pathlib import Path
from typing import Dict


def build_win_rate_report(summary: Dict[str, object]) -> str:
    episodes = int(summary.get("episodes", 0))
    p1_wins = int(summary.get("p1_wins", 0))
    p2_wins = int(summary.get("p2_wins", 0))
    draws = int(summary.get("draws", 0))
    avg_steps = float(summary.get("avg_steps", 0.0))
    p1_name = str(summary.get("p1_agent", "P1"))
    p2_name = str(summary.get("p2_agent", "P2"))
    action_type_counts = dict(summary.get("action_type_counts", {}))
    card_use_counts = dict(summary.get("card_use_counts", {}))

    def rate(count: int) -> float:
        return 0.0 if episodes == 0 else 100.0 * count / episodes

    lines = [
        "=== Evaluation Report ===",
        f"Episodes: {episodes}",
        f"P1 ({p1_name}) wins: {p1_wins} ({rate(p1_wins):.1f}%)",
        f"P2 ({p2_name}) wins: {p2_wins} ({rate(p2_wins):.1f}%)",
        f"Draws: {draws} ({rate(draws):.1f}%)",
        f"Average steps: {avg_steps:.2f}",
    ]

    if action_type_counts:
        lines.append("")
        lines.append("[Action Type Counts]")
        for action_type, count in action_type_counts.items():
            lines.append(f"- {action_type}: {count}")

    if card_use_counts:
        lines.append("")
        lines.append("[Card Use Counts]")
        for card_name, count in card_use_counts.items():
            lines.append(f"- {card_name}: {count}")

    return "\n".join(lines)


def save_report(report_text: str, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
    return path
