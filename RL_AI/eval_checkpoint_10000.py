"""Evaluate the 10000-episode checkpoint against chosen opponent suites.

Default behavior:
  - load the already extracted model_ep_10000.pt from ~/RL_AI/models
  - evaluate random / greedy / rule_based / self suites
  - run 8 combo matches per suite with 100 matches per combo
  - save a start_latest.zip-like bundle to ~/eval_checkpoint_10000.zip

This script is intentionally standalone so it can be used even when training
was run without pre/post evaluation enabled.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from RL_AI.analysis.reports import build_win_rate_report, save_report
from RL_AI.start import _apply_parallel_opt_env, _build_csharp, _ensure_dotnet, _ensure_python_deps, _prepare_project_dir, _set_single_worker_defaults


class _Tee(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase) -> None:
        self.streams = streams

    def write(self, s: str) -> int:
        for stream in self.streams:
            stream.write(s)
            stream.flush()
        return len(s)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def _setup_logger(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    f = open(log_file, "w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.stdout, f)
    sys.stderr = _Tee(sys.stderr, f)
    print(f"[*] log file: {log_file}")


def _extract_pt_from_zip(model_zip: Path, member_name: str = "model_ep_10000.pt") -> Path:
    if not model_zip.exists():
        raise FileNotFoundError(f"Model zip not found: {model_zip}")
    cache_dir = Path(tempfile.gettempdir()) / "rl_ai_eval_checkpoint_10000" / model_zip.stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    pt_path = cache_dir / member_name
    if pt_path.exists():
        return pt_path
    with zipfile.ZipFile(model_zip, "r") as zf:
        names = set(zf.namelist())
        if member_name not in names:
            available = ", ".join(sorted(names))
            raise FileNotFoundError(
                f"{member_name} not found in {model_zip}. Available entries: {available}"
            )
        zf.extract(member_name, path=cache_dir)
    return pt_path


def _resolve_model_path(model_path: str, model_zip: str) -> Path:
    if model_path:
        path = Path(model_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Model path not found: {path}")
        if path.suffix.lower() == ".zip":
            return _extract_pt_from_zip(path)
        return path
    zip_path = Path(model_zip).expanduser().resolve()
    return _extract_pt_from_zip(zip_path)


def _parse_opponents(raw: str) -> list[str]:
    values: list[str] = []
    for part in str(raw or "").split(","):
        name = part.strip().lower()
        if not name:
            continue
        if name in {"random", "greedy", "rule_based", "rule", "self"}:
            values.append("rule_based" if name == "rule" else name)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _make_opponent(label: str, seed: int):
    from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRandomAgent, SeaEngineRuleBasedAgent

    if label == "random":
        return SeaEngineRandomAgent(seed=seed)
    if label == "greedy":
        return SeaEngineGreedyAgent(seed=seed)
    if label == "rule_based":
        return SeaEngineRuleBasedAgent(seed=seed)
    if label == "self":
        return None
    raise ValueError(f"Unsupported opponent label: {label}")


def _default_log_path() -> Path:
    return Path.home() / "eval_checkpoint_10000.log"


def _default_report_path() -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return Path.home() / "RL_AI" / "log" / f"se_ckpt_10000_{stamp}.txt"


def _default_zip_path() -> Path:
    return Path.home() / "eval_checkpoint_10000.zip"


def _zip_selected_files(zip_path: Path, files: list[Path]) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            if file_path.exists() and file_path.is_file():
                zf.write(file_path, arcname=file_path.name)
    return zip_path


def _suite_rl_win_rate(suite_pack: Optional[dict[str, object]]) -> float:
    if not suite_pack:
        return 0.0
    total_wins = 0
    total_episodes = 0
    for row in list(suite_pack.get("results", [])):
        total_wins += int(row.get("rl_wins", 0))
        total_episodes += int(row.get("episodes", 0))
    if total_episodes <= 0:
        return 0.0
    return total_wins / float(total_episodes)


def _suite_worst_combo_rate(suite_pack: Optional[dict[str, object]]) -> float:
    if not suite_pack:
        return 0.0
    worst = 1.0
    for row in list(suite_pack.get("results", [])):
        episodes = int(row.get("episodes", 0))
        wins = int(row.get("rl_wins", 0))
        if episodes <= 0:
            continue
        worst = min(worst, wins / float(episodes))
    return 0.0 if worst == 1.0 else worst


def _suite_side_gap_abs(suite_pack: Optional[dict[str, object]]) -> float:
    if not suite_pack:
        return 1.0
    first_wins = first_n = second_wins = second_n = 0
    for row in list(suite_pack.get("results", [])):
        episodes = int(row.get("episodes", 0))
        wins = int(row.get("rl_wins", 0))
        label = str(row.get("label", row.get("side", "")))
        if "선공" in label or str(row.get("side", "")) == "선공":
            first_wins += wins
            first_n += episodes
        elif "후공" in label or str(row.get("side", "")) == "후공":
            second_wins += wins
            second_n += episodes
    if first_n <= 0 or second_n <= 0:
        return 1.0
    return abs(first_wins / float(first_n) - second_wins / float(second_n))


def _checkpoint_population_score(
    *,
    random_suite: Optional[dict[str, object]],
    greedy_suite: Optional[dict[str, object]],
    rule_suite: Optional[dict[str, object]],
    self_suite: Optional[dict[str, object]],
) -> dict[str, float]:
    random_wr = _suite_rl_win_rate(random_suite)
    greedy_wr = _suite_rl_win_rate(greedy_suite)
    rule_wr = _suite_rl_win_rate(rule_suite)
    self_wr = _suite_rl_win_rate(self_suite)
    worst_combo = min(
        _suite_worst_combo_rate(random_suite),
        _suite_worst_combo_rate(greedy_suite),
        _suite_worst_combo_rate(rule_suite),
        _suite_worst_combo_rate(self_suite),
    )
    side_gap = max(
        _suite_side_gap_abs(random_suite),
        _suite_side_gap_abs(greedy_suite),
        _suite_side_gap_abs(rule_suite),
        _suite_side_gap_abs(self_suite),
    )
    avg_wr = (random_wr + greedy_wr + rule_wr + self_wr) / 4.0
    score = avg_wr + (0.20 * worst_combo) - (0.10 * side_gap)
    return {
        "score": score,
        "random_wr": random_wr,
        "greedy_wr": greedy_wr,
        "rule_wr": rule_wr,
        "self_wr": self_wr,
        "worst_combo_wr": worst_combo,
        "max_side_gap": side_gap,
        "avg_wr": avg_wr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the 10000-episode checkpoint")
    parser.add_argument(
        "--model-path",
        type=str,
        default=str(Path.home() / "RL_AI" / "models" / "model_ep_10000.pt"),
        help="Path to the already extracted model_ep_10000.pt",
    )
    parser.add_argument(
        "--model-zip",
        type=str,
        default=str(Path.home() / "RL_AI" / "models" / "model_20260508_005938.zip"),
        help="Optional fallback zip path that contains model_ep_10000.pt",
    )
    parser.add_argument("--report-path", type=str, default=str(_default_report_path()))
    parser.add_argument("--log-file", type=str, default=str(_default_log_path()))
    parser.add_argument("--zip-path", type=str, default=str(_default_zip_path()))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--matches-per-combo", type=int, default=100)
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--card-data-path", type=str, default="")
    parser.add_argument(
        "--opponents",
        type=str,
        default="random,greedy,rule_based,self",
        help="Comma-separated opponent suites to evaluate",
    )
    parser.add_argument(
        "--use-belief-mcts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use shallow belief-MCTS wrapper during evaluation",
    )
    args = parser.parse_args()

    _setup_logger(Path(args.log_file))
    _set_single_worker_defaults()
    _prepare_project_dir()
    home = Path.home()
    if str(home) not in sys.path:
        sys.path.insert(0, str(home))
    _ensure_python_deps()
    _apply_parallel_opt_env("start")
    dotnet_cmd = _ensure_dotnet()
    if dotnet_cmd:
        print(f"[*] dotnet command: {dotnet_cmd}")
        print(f"[*] dotnet root: {os.environ.get('DOTNET_ROOT', '')}")
    _build_csharp(dotnet_cmd)

    from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRandomAgent, SeaEngineRuleBasedAgent
    from RL_AI.training import SeaEnginePPOTrainer
    from RL_AI.training.experiment import _load_saved_rl_agent, _run_8combo_opponent_eval_suite

    if args.matches_per_combo <= 0:
        raise ValueError("--matches-per-combo must be positive")

    model_path = _resolve_model_path(args.model_path, args.model_zip)
    print(f"[*] checkpoint model: {model_path}")
    print(f"[*] matches per combo: {args.matches_per_combo}")
    print(f"[*] opponents: {args.opponents}")
    print(f"[*] max_turns: {args.max_turns}")

    learning_agent = _load_saved_rl_agent(model_path=str(model_path), seed=args.seed, device=args.device)
    trainer = SeaEnginePPOTrainer(learning_agent)

    card_data_path: Optional[str] = args.card_data_path.strip() or None
    opponent_labels = _parse_opponents(args.opponents)
    if not opponent_labels:
        raise ValueError("No valid opponent suites selected")

    artifact_start_wall = time.time()
    suite_results: list[dict[str, object]] = []
    suite_results_by_label: dict[str, dict[str, object]] = {}
    generated_files: list[Path] = []
    suite_titles = {
        "random": "Checkpoint 10000 vs Random",
        "greedy": "Checkpoint 10000 vs Greedy",
        "rule_based": "Checkpoint 10000 vs Rule-Based",
        "self": "Checkpoint 10000 vs Self",
    }
    for idx, label in enumerate(opponent_labels):
        suite_start = time.perf_counter()
        opponent_agent = _make_opponent(label, args.seed + 1000 + idx * 13)
        print(f"[*] Starting suite: {label}")
        suite = _run_8combo_opponent_eval_suite(
            trainer=trainer,
            rl_agent=learning_agent,
            opponent_agent=learning_agent if label == "self" else opponent_agent,
            opponent_label=label,
            suite_title=suite_titles.get(label, f"Checkpoint 10000 vs {label}"),
            history_tag=f"se_eval_ckpt10000_{label}",
            checkpoint_episodes=10000,
            num_matches_per_combo=args.matches_per_combo,
            card_data_path=card_data_path,
            max_turns=args.max_turns,
            scenario_report_prefix=f"se_eval_ckpt10000_{label}",
            scenario_workers=1,
            use_belief_mcts=args.use_belief_mcts,
        )
        suite_results.append(
            {
                "label": label,
                "elapsed_sec": max(1e-9, time.perf_counter() - suite_start),
                "results": suite["results"],
                "history_summary": suite["history_summary"],
                "text": suite["text"],
            }
        )
        suite_results_by_label[label] = suite
        suite_report_path = Path(args.report_path).with_name(
            f"{Path(args.report_path).stem}_{label}.txt"
        )
        suite_elapsed = max(1e-9, time.perf_counter() - suite_start)
        suite_report_text = "\n".join(
            [
                f"=== {suite_titles.get(label, f'Checkpoint 10000 vs {label}')} ===",
                f"elapsed_sec={suite_elapsed:.2f}",
                "",
                build_win_rate_report(dict(suite["history_summary"])),
                "",
                str(suite["text"]).rstrip(),
                "",
            ]
        )
        generated_files.append(save_report(suite_report_text.rstrip() + "\n", suite_report_path))

    total_matches = args.matches_per_combo * 8 * len(opponent_labels)
    total_rl_wins = sum(int(s["history_summary"].get("p1_wins", 0)) for s in suite_results)
    total_opp_wins = sum(int(s["history_summary"].get("p2_wins", 0)) for s in suite_results)
    total_draws = sum(int(s["history_summary"].get("draws", 0)) for s in suite_results)
    total_n = max(1, total_rl_wins + total_opp_wins + total_draws)
    total_wr = 100.0 * total_rl_wins / total_n

    report_lines = [
        "=== Checkpoint 10000 Evaluation ===",
        f"model_path={model_path}",
        f"matches_per_combo={args.matches_per_combo}",
        f"opponents={opponent_labels}",
        f"max_turns={args.max_turns}",
        f"total_matches={total_matches}",
        "",
    ]
    checkpoint_score = _checkpoint_population_score(
        random_suite=suite_results_by_label.get("random"),
        greedy_suite=suite_results_by_label.get("greedy"),
        rule_suite=suite_results_by_label.get("rule_based"),
        self_suite=suite_results_by_label.get("self"),
    )
    report_lines.extend(
        [
            "=== Population-Based Checkpoint Score ===",
            f"score={checkpoint_score['score']:.4f}",
            f"random_wr={checkpoint_score['random_wr'] * 100.0:.2f}%",
            f"greedy_wr={checkpoint_score['greedy_wr'] * 100.0:.2f}%",
            f"rule_wr={checkpoint_score['rule_wr'] * 100.0:.2f}%",
            f"self_wr={checkpoint_score['self_wr'] * 100.0:.2f}%",
            f"worst_combo_wr={checkpoint_score['worst_combo_wr'] * 100.0:.2f}%",
            f"max_side_gap={checkpoint_score['max_side_gap'] * 100.0:.2f}pp",
            "",
        ]
    )
    for suite in suite_results:
        summary = dict(suite["history_summary"])
        label = str(suite["label"])
        report_lines.extend(
            [
                f"=== {label} ===",
                f"elapsed_sec={float(suite['elapsed_sec']):.2f}",
                f"report={summary.get('report_path', '')}",
                build_win_rate_report(summary),
                "",
            ]
        )

    report_lines.extend(
        [
            "=== Aggregate ===",
            f"episodes={total_matches}",
            f"rl_wins={total_rl_wins}",
            f"opp_wins={total_opp_wins}",
            f"draws={total_draws}",
            f"rl_win_rate_percent={total_wr:.2f}",
            "",
        ]
    )
    report_path = save_report("\n".join(report_lines).rstrip() + "\n", Path(args.report_path))
    generated_files.insert(0, report_path)

    log_dir = Path.home() / "RL_AI" / "log"
    generated_files.extend(
        sorted(
            p
            for p in log_dir.glob("se_eval_ckpt10000_*.txt")
            if p.is_file() and p.stat().st_mtime >= artifact_start_wall - 1.0
        )
    )
    generated_files.extend(
        sorted(
            p
            for p in log_dir.glob("se_ckpt_10000_*_hist.txt")
            if p.is_file() and p.stat().st_mtime >= artifact_start_wall - 1.0
        )
    )
    generated_files = list(dict.fromkeys(generated_files))
    zip_path = _zip_selected_files(Path(args.zip_path), generated_files)
    print(f"[*] summary report: {report_path}")
    print(f"[*] bundle zip: {zip_path}")
    print(f"[*] total matches: {total_matches}")
    print(f"[*] aggregate win rate: {total_wr:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
