#!/usr/bin/env python3
"""Microbenchmark parallel settings and optionally launch start.py with the result."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent


def _candidate_start_scripts() -> list[Path]:
    candidates = [
        Path.home() / "start.py",
        Path.home() / "RL_AI" / "start.py",
        _workspace_root() / "start.py",
        _workspace_root() / "RL_AI" / "start.py",
    ]
    seen: list[Path] = []
    for candidate in candidates:
        if candidate.exists() and candidate not in seen:
            seen.append(candidate)
    return seen


def _find_start_script() -> Path:
    candidates = _candidate_start_scripts()
    if not candidates:
        raise FileNotFoundError("Could not find start.py in the workspace or home directory.")
    return candidates[0]


def _ensure_sys_path() -> None:
    root = _workspace_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _prepare_project_dir() -> None:
    home = Path.home()
    zip_candidates = [Path.cwd() / "RL_AI.zip", home / "RL_AI.zip"]
    zip_path = next((path for path in zip_candidates if path.exists()), None)
    target_dir = home / "RL_AI"

    if zip_path is None:
        print("RL_AI.zip not found, skipping unzip")
        return

    print(f"[*] preparing RL_AI workspace from {zip_path}...")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)
        nested_root = tmp_path / "RL_AI"
        source_root = nested_root if nested_root.exists() else tmp_path
        for item in source_root.iterdir():
            if item.is_dir():
                shutil.copytree(item, target_dir / item.name)
            else:
                shutil.copy2(item, target_dir / item.name)
    print("RL_AI ready")


def _parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values


def _format_list(values: Sequence[int]) -> str:
    return ",".join(str(v) for v in values)


def _parallel_opt_config_path() -> Path:
    return Path.home() / ".seaengine_parallel_opt.json"


def _save_parallel_opt_config(report: dict[str, object]) -> Path:
    path = _parallel_opt_config_path()
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _candidate_num_envs(cpu_count: int) -> list[int]:
    base = [4, 8, 12, 16, 24, 32]
    cpu_targets = [max(1, cpu_count // 2), max(1, cpu_count), max(1, min(32, cpu_count * 2))]
    values = sorted({v for v in base + cpu_targets if v > 0})
    return values


def _candidate_local_threads(cpu_count: int) -> list[int]:
    base = [0, 1, 2, 4, 8, 16]
    cpu_targets = [max(1, cpu_count // 4), max(1, cpu_count // 2), max(1, min(16, cpu_count))]
    values = sorted({v for v in base + cpu_targets if v >= 0})
    return values


def _candidate_scenario_workers(cpu_count: int) -> list[int]:
    base = [1, 2, 4, 8]
    cpu_targets = [max(1, cpu_count // 8), max(1, cpu_count // 4), max(1, cpu_count // 2)]
    values = sorted({v for v in base + cpu_targets if v > 0})
    return values


def _candidate_parallel_workers(cpu_count: int) -> list[int]:
    base = [1, 2, 4, 8]
    cpu_targets = [max(1, cpu_count // 8), max(1, cpu_count // 4), max(1, cpu_count // 2)]
    values = sorted({v for v in base + cpu_targets if v > 0})
    return values


def _apply_env(overrides: dict[str, str]) -> dict[str, str]:
    previous: dict[str, str] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key, "")
        if value == "":
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str]) -> None:
    for key, value in previous.items():
        if value == "":
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _bootstrap_runtime(*, skip_unzip: bool) -> None:
    _ensure_sys_path()
    if not skip_unzip:
        _prepare_project_dir()
    from RL_AI.start import _ensure_workspace_venv

    python_cmd = _ensure_workspace_venv()
    if Path(sys.executable).resolve() != Path(python_cmd).resolve() or os.environ.get("SEAENGINE_PYTHON_SELECTED", "").strip() != "1":
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["SEAENGINE_PYTHON_SELECTED"] = "1"
        env["PYTHON_CMD"] = python_cmd
        env["SEAENGINE_PYTHON"] = python_cmd
        argv = [python_cmd]
        if getattr(sys.flags, "unbuffered", 0):
            argv.append("-u")
        argv.append(str(Path(__file__).resolve()))
        argv.extend(sys.argv[1:])
        os.execvpe(python_cmd, argv, env)


@dataclass
class TrainBenchmarkResult:
    num_envs: int
    local_threads: int
    episodes: int
    elapsed: float
    eps_per_sec: float


@dataclass
class EvalBenchmarkResult:
    scenario_workers: int
    matches: int
    elapsed: float
    matches_per_sec: float


@dataclass
class BalanceBenchmarkResult:
    scenario_workers: int
    total_matches: int
    elapsed: float
    matches_per_sec: float


@dataclass
class BiasParallelBenchmarkResult:
    parallel_workers: int
    task_count: int
    total_matches: int
    elapsed: float
    matches_per_sec: float


def _make_training_trainer(seed: int, device: str):
    from RL_AI.agents import SeaEngineRLAgent
    from RL_AI.training.trainer import SeaEnginePPOTrainer

    agent = SeaEngineRLAgent(seed=seed, device=device)
    return SeaEnginePPOTrainer(agent)


def _benchmark_training(
    *,
    num_envs: int,
    local_threads: int,
    episodes: int,
    max_turns: int,
    update_interval: int,
    seed: int,
    device: str,
) -> TrainBenchmarkResult:
    from RL_AI.training.trainer import SeaEnginePPOTrainer

    _ = SeaEnginePPOTrainer  # keep import explicit for clarity
    previous = _apply_env(
        {
            "SEAENGINE_VECTOR_BACKEND": "isolated",
            "SEAENGINE_FAST_POOL": "0",
            "SEAENGINE_QUIET_WORKER_LOG": "1",
            "SEAENGINE_SUPPRESS_NATIVE_LOGS": "1",
            "SEAENGINE_TRAIN_MAX_TURNS": str(max_turns),
            "SEAENGINE_MIN_UPDATE_INTERVAL": str(update_interval),
            "SEAENGINE_LOCAL_THREADS": "1" if local_threads == 1 else str(local_threads),
            "SEAENGINE_WORKERS": "" if local_threads in {0, 1} else str(local_threads),
            "SEAENGINE_LOCAL_MAX_WORKERS": "" if local_threads in {0, 1} else str(local_threads),
        }
    )
    try:
        trainer = _make_training_trainer(seed=seed, device=device)
        opponent_pool = trainer.build_default_opponent_pool(seed=seed + 303)
        start = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = trainer.train(
                num_episodes=episodes,
                opponent_pool=opponent_pool,
                max_turns=max_turns,
                update_interval=update_interval,
                save_interval=10**9,
                log_interval=0,
                num_envs=num_envs,
            )
        elapsed = max(1e-9, time.perf_counter() - start)
        achieved = float(result.get("episodes", episodes)) / elapsed
        return TrainBenchmarkResult(
            num_envs=num_envs,
            local_threads=local_threads,
            episodes=int(result.get("episodes", episodes)),
            elapsed=elapsed,
            eps_per_sec=achieved,
        )
    finally:
        _restore_env(previous)


def _benchmark_eval(
    *,
    scenario_workers: int,
    matches_per_combo: int,
    max_turns: int,
    seed: int,
    device: str,
    use_belief_mcts: bool,
) -> EvalBenchmarkResult:
    from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRLAgent
    from RL_AI.training.experiment import _run_8combo_opponent_eval_suite
    from RL_AI.training.trainer import SeaEnginePPOTrainer

    previous = _apply_env(
        {
            "SEAENGINE_SCENARIO_WORKERS": str(scenario_workers),
            "SEAENGINE_QUIET_WORKER_LOG": "1",
            "SEAENGINE_SUPPRESS_NATIVE_LOGS": "1",
        }
    )
    try:
        trainer = _make_training_trainer(seed=seed, device=device)
        rl_agent = trainer.agent
        opponent_agent = SeaEngineGreedyAgent(seed=seed + 202)
        start = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            summary = _run_8combo_opponent_eval_suite(
                trainer=trainer,
                rl_agent=rl_agent,
                opponent_agent=opponent_agent,
                opponent_label="greedy",
                suite_title="find_opt_par_eval",
                history_tag="find_opt_par",
                num_matches_per_combo=matches_per_combo,
                card_data_path=None,
                max_turns=max_turns,
                scenario_report_prefix="find_opt_par",
                checkpoint_episodes=None,
                start_mode="normal",
                burnin_profile="fixed",
                scenario_workers=scenario_workers,
                use_belief_mcts=use_belief_mcts,
            )
        elapsed = max(1e-9, time.perf_counter() - start)
        episodes = int(summary.get("episodes", matches_per_combo * 8))
        achieved = float(episodes) / elapsed
        return EvalBenchmarkResult(
            scenario_workers=scenario_workers,
            matches=episodes,
            elapsed=elapsed,
            matches_per_sec=achieved,
        )
    finally:
        _restore_env(previous)


def _benchmark_balance(
    *,
    scenario_workers: int,
    total_matches: int,
    max_turns: int,
    seed: int,
    device: str,
    use_belief_mcts: bool,
) -> BalanceBenchmarkResult:
    from RL_AI.make_balance import _resolve_model_path, _run_balance

    previous = _apply_env(
        {
            "SEAENGINE_SCENARIO_WORKERS": str(scenario_workers),
            "SEAENGINE_QUIET_WORKER_LOG": "1",
            "SEAENGINE_SUPPRESS_NATIVE_LOGS": "1",
        }
    )
    try:
        model_path = _resolve_model_path("")
        start = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _run_balance(
                model_path=model_path,
                total_matches=total_matches,
                max_turns=max_turns,
                seed=seed,
                device=device,
                progress_interval=10**9,
                scenario_workers=scenario_workers,
                scenario_shards=1,
                include_history=False,
                history_limit=None,
                use_belief_mcts=use_belief_mcts,
            )
        elapsed = max(1e-9, time.perf_counter() - start)
        achieved = float(total_matches) / elapsed
        return BalanceBenchmarkResult(
            scenario_workers=scenario_workers,
            total_matches=total_matches,
            elapsed=elapsed,
            matches_per_sec=achieved,
        )
    finally:
        _restore_env(previous)


def _benchmark_bias_parallel(
    *,
    parallel_workers: int,
    scenario_workers: int,
    total_matches_per_task: int,
    max_turns: int,
    seed: int,
    device: str,
    use_belief_mcts: bool,
) -> BiasParallelBenchmarkResult:
    from RL_AI.bias_check import _extract_model_archive, _process_pool_context, _resolve_model_source, _run_bias_task

    previous = _apply_env(
        {
            "SEAENGINE_SCENARIO_WORKERS": str(scenario_workers),
            "SEAENGINE_PARALLEL_WORKERS": str(parallel_workers),
            "SEAENGINE_QUIET_WORKER_LOG": "1",
            "SEAENGINE_SUPPRESS_NATIVE_LOGS": "1",
        }
    )
    temp_mgr: tempfile.TemporaryDirectory[str] | None = None
    try:
        model_source = _resolve_model_source(None)
        if model_source.suffix.lower() == ".zip":
            temp_mgr = tempfile.TemporaryDirectory(prefix="find_opt_par_bias_")
            extract_root = Path(temp_mgr.name)
            extracted = _extract_model_archive(model_source, extract_root)
            current_model_path = extracted[-1]
        else:
            current_model_path = model_source

        task_specs: list[dict[str, object]] = [
            {
                "task_name": "random_random",
                "kind": "same_policy",
                "label": "random",
                "agent_kind": "random",
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "greedy_greedy",
                "kind": "same_policy",
                "label": "greedy",
                "agent_kind": "greedy",
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed + 100,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "rule_based_rule_based",
                "kind": "same_policy",
                "label": "rule_based",
                "agent_kind": "rule_based",
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed + 150,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "rl_family",
                "kind": "same_policy",
                "label": "rl",
                "agent_kind": "rl",
                "observation_mode": "python_canonical",
                "model_path": str(current_model_path),
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed + 200,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "random_slight_deficit",
                "kind": "same_policy",
                "label": "random_slight",
                "agent_kind": "random",
                "start_mode": "slight",
                "burnin_profile": "mixed",
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed + 210,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "greedy_slight_deficit",
                "kind": "same_policy",
                "label": "greedy_slight",
                "agent_kind": "greedy",
                "start_mode": "slight",
                "burnin_profile": "mixed",
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed + 310,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "rule_based_slight_deficit",
                "kind": "same_policy",
                "label": "rule_based_slight",
                "agent_kind": "rule_based",
                "start_mode": "slight",
                "burnin_profile": "mixed",
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed + 330,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "rl_slight_deficit",
                "kind": "same_policy",
                "label": "rl_slight",
                "agent_kind": "rl",
                "observation_mode": "python_canonical",
                "start_mode": "slight",
                "burnin_profile": "mixed",
                "model_path": str(current_model_path),
                "total_matches": total_matches_per_task,
                "card_data_path": None,
                "max_turns": max_turns,
                "seed": seed + 410,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
        ]
        for task in task_specs:
            if str(task.get("agent_kind")) == "rl":
                task["use_belief_mcts"] = bool(use_belief_mcts)

        start = time.perf_counter()
        with concurrent.futures.ProcessPoolExecutor(max_workers=parallel_workers, mp_context=_process_pool_context()) as executor:
            futures = [executor.submit(_run_bias_task, task) for task in task_specs]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        elapsed = max(1e-9, time.perf_counter() - start)
        achieved = float(total_matches_per_task * len(task_specs)) / elapsed
        return BiasParallelBenchmarkResult(
            parallel_workers=parallel_workers,
            task_count=len(task_specs),
            total_matches=total_matches_per_task * len(task_specs),
            elapsed=elapsed,
            matches_per_sec=achieved,
        )
    finally:
        if temp_mgr is not None:
            temp_mgr.cleanup()
        _restore_env(previous)


def _pick_best_train(
    *,
    num_envs_candidates: Sequence[int],
    local_threads_candidates: Sequence[int],
    episodes: int,
    max_turns: int,
    update_interval: int,
    seed: int,
    device: str,
) -> TrainBenchmarkResult:
    best: TrainBenchmarkResult | None = None
    for num_envs in num_envs_candidates:
        for local_threads in local_threads_candidates:
            result = _benchmark_training(
                num_envs=num_envs,
                local_threads=local_threads,
                episodes=episodes,
                max_turns=max_turns,
                update_interval=update_interval,
                seed=seed,
                device=device,
            )
            if best is None or result.eps_per_sec > best.eps_per_sec:
                best = result
            print(
                f"[train] num_envs={result.num_envs:>2} | local_threads={result.local_threads:>2} | "
                f"speed={result.eps_per_sec:>6.2f} eps/s | elapsed={result.elapsed:>6.1f}s"
            )
    if best is None:
        raise RuntimeError("Training benchmark did not produce any result.")
    return best


def _pick_best_eval(
    *,
    scenario_workers_candidates: Sequence[int],
    matches_per_combo: int,
    max_turns: int,
    seed: int,
    device: str,
    use_belief_mcts: bool,
) -> EvalBenchmarkResult:
    best: EvalBenchmarkResult | None = None
    for scenario_workers in scenario_workers_candidates:
        result = _benchmark_eval(
            scenario_workers=scenario_workers,
            matches_per_combo=matches_per_combo,
            max_turns=max_turns,
            seed=seed,
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        if best is None or result.matches_per_sec > best.matches_per_sec:
            best = result
        print(
            f"[eval ] scenario_workers={result.scenario_workers:>2} | "
            f"speed={result.matches_per_sec:>6.2f} matches/s | elapsed={result.elapsed:>6.1f}s"
        )
    if best is None:
        raise RuntimeError("Evaluation benchmark did not produce any result.")
    return best


def _pick_best_balance(
    *,
    scenario_workers_candidates: Sequence[int],
    total_matches: int,
    max_turns: int,
    seed: int,
    device: str,
    use_belief_mcts: bool,
) -> BalanceBenchmarkResult:
    best: BalanceBenchmarkResult | None = None
    for scenario_workers in scenario_workers_candidates:
        result = _benchmark_balance(
            scenario_workers=scenario_workers,
            total_matches=total_matches,
            max_turns=max_turns,
            seed=seed,
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        if best is None or result.matches_per_sec > best.matches_per_sec:
            best = result
        print(
            f"[balance] scenario_workers={result.scenario_workers:>2} | "
            f"speed={result.matches_per_sec:>6.2f} matches/s | elapsed={result.elapsed:>6.1f}s"
        )
    if best is None:
        raise RuntimeError("Balance benchmark did not produce any result.")
    return best


def _pick_best_bias_scenario_workers(
    *,
    scenario_workers_candidates: Sequence[int],
    total_matches_per_task: int,
    max_turns: int,
    seed: int,
    device: str,
    use_belief_mcts: bool,
) -> int:
    best_workers: int | None = None
    best_speed: float | None = None
    for scenario_workers in scenario_workers_candidates:
        result = _benchmark_bias_parallel(
            parallel_workers=1,
            scenario_workers=scenario_workers,
            total_matches_per_task=total_matches_per_task,
            max_turns=max_turns,
            seed=seed,
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        if best_speed is None or result.matches_per_sec > best_speed:
            best_speed = result.matches_per_sec
            best_workers = scenario_workers
        print(
            f"[bias ] scenario_workers={scenario_workers:>2} | "
            f"speed={result.matches_per_sec:>6.2f} matches/s | elapsed={result.elapsed:>6.1f}s"
        )
    if best_workers is None:
        raise RuntimeError("Bias scenario worker benchmark did not produce any result.")
    return best_workers


def _pick_best_bias_parallel(
    *,
    parallel_workers_candidates: Sequence[int],
    scenario_workers: int,
    total_matches_per_task: int,
    max_turns: int,
    seed: int,
    device: str,
    use_belief_mcts: bool,
) -> BiasParallelBenchmarkResult:
    best: BiasParallelBenchmarkResult | None = None
    for parallel_workers in parallel_workers_candidates:
        result = _benchmark_bias_parallel(
            parallel_workers=parallel_workers,
            scenario_workers=scenario_workers,
            total_matches_per_task=total_matches_per_task,
            max_turns=max_turns,
            seed=seed,
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        if best is None or result.matches_per_sec > best.matches_per_sec:
            best = result
        print(
            f"[bias ] parallel_workers={result.parallel_workers:>2} | "
            f"speed={result.matches_per_sec:>6.2f} matches/s | elapsed={result.elapsed:>6.1f}s"
        )
    if best is None:
        raise RuntimeError("Bias parallel benchmark did not produce any result.")
    return best


def _find_total_runtime(train_speed: float, eval_speed: float, train_episodes: int, eval_matches_total: int) -> float:
    return (train_episodes / max(train_speed, 1e-9)) + (eval_matches_total / max(eval_speed, 1e-9))


def _set_start_env(train_best: TrainBenchmarkResult, eval_best: EvalBenchmarkResult) -> dict[str, str]:
    env: dict[str, str] = {}
    env["SEAENGINE_NUM_ENVS"] = str(train_best.num_envs)
    if train_best.local_threads == 0:
        env["SEAENGINE_LOCAL_THREADS"] = "0"
        env["SEAENGINE_WORKERS"] = "0"
        env["SEAENGINE_LOCAL_MAX_WORKERS"] = "0"
    elif train_best.local_threads == 1:
        env["SEAENGINE_LOCAL_THREADS"] = "1"
        env["SEAENGINE_WORKERS"] = "0"
        env["SEAENGINE_LOCAL_MAX_WORKERS"] = "0"
    else:
        env["SEAENGINE_LOCAL_THREADS"] = str(train_best.local_threads)
        env["SEAENGINE_WORKERS"] = str(train_best.local_threads)
        env["SEAENGINE_LOCAL_MAX_WORKERS"] = str(train_best.local_threads)
    env["SEAENGINE_SCENARIO_WORKERS"] = str(eval_best.scenario_workers)
    return env


def _set_balance_env(eval_best: EvalBenchmarkResult) -> dict[str, str]:
    return {
        "SEAENGINE_SCENARIO_WORKERS": str(eval_best.scenario_workers),
    }


def _set_bias_env(scenario_workers: int, bias_best: BiasParallelBenchmarkResult) -> dict[str, str]:
    return {
        "SEAENGINE_SCENARIO_WORKERS": str(scenario_workers),
        "SEAENGINE_PARALLEL_WORKERS": str(bias_best.parallel_workers),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark parallel settings and apply them before start.py")
    parser.add_argument("--benchmark-only", action="store_true", help="Only benchmark; do not run start.py afterwards")
    parser.add_argument("--train-episodes", type=int, default=24)
    parser.add_argument("--train-max-turns", type=int, default=60)
    parser.add_argument("--train-update-interval", type=int, default=16)
    parser.add_argument("--eval-matches-per-combo", type=int, default=2)
    parser.add_argument("--eval-max-turns", type=int, default=60)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--num-envs-candidates", type=str, default="")
    parser.add_argument("--local-thread-candidates", type=str, default="")
    parser.add_argument("--scenario-workers-candidates", type=str, default="")
    parser.add_argument("--parallel-workers-candidates", type=str, default="")
    parser.add_argument("--use-belief-mcts", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--balance-total-matches", type=int, default=16)
    parser.add_argument("--bias-task-matches", type=int, default=8)
    parser.add_argument("--summary-file", type=str, default="")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-unzip", action="store_true")
    args, start_args = parser.parse_known_args()

    _bootstrap_runtime(skip_unzip=bool(args.skip_unzip))
    _ensure_sys_path()

    from RL_AI.start import _build_csharp, _ensure_dotnet, _has_engine_binary, _prepare_project_dir, _set_dotnet_env

    workspace_root = _workspace_root()
    start_script = _find_start_script()
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    dotnet_cmd = _ensure_dotnet()
    if dotnet_cmd:
        _set_dotnet_env(dotnet_cmd)
    if not args.skip_build and not _has_engine_binary():
        _build_csharp(dotnet_cmd)

    cpu_count = os.cpu_count() or 1
    num_envs_candidates = _parse_csv_ints(args.num_envs_candidates) or _candidate_num_envs(cpu_count)
    local_thread_candidates = _parse_csv_ints(args.local_thread_candidates) or _candidate_local_threads(cpu_count)
    scenario_workers_candidates = _parse_csv_ints(args.scenario_workers_candidates) or _candidate_scenario_workers(cpu_count)
    parallel_workers_candidates = _parse_csv_ints(args.parallel_workers_candidates) or _candidate_parallel_workers(cpu_count)

    num_envs_candidates = [v for v in sorted(set(num_envs_candidates)) if v > 0]
    local_thread_candidates = [v for v in sorted(set(local_thread_candidates)) if v >= 0]
    scenario_workers_candidates = [v for v in sorted(set(scenario_workers_candidates)) if v > 0]
    parallel_workers_candidates = [v for v in sorted(set(parallel_workers_candidates)) if v > 0]

    print(f"[*] start script: {start_script}")
    print(f"[*] cpu_count={cpu_count}")
    print(f"[*] train num_envs candidates: {_format_list(num_envs_candidates)}")
    print(f"[*] train local_threads candidates: {_format_list(local_thread_candidates)}")
    print(f"[*] eval scenario_workers candidates: {_format_list(scenario_workers_candidates)}")
    print(f"[*] bias parallel_workers candidates: {_format_list(parallel_workers_candidates)}")

    train_best = _pick_best_train(
        num_envs_candidates=num_envs_candidates,
        local_threads_candidates=local_thread_candidates,
        episodes=max(8, int(args.train_episodes)),
        max_turns=max(20, int(args.train_max_turns)),
        update_interval=max(4, int(args.train_update_interval)),
        seed=int(args.seed),
        device=str(args.device),
    )
    eval_best = _pick_best_eval(
        scenario_workers_candidates=scenario_workers_candidates,
        matches_per_combo=max(1, int(args.eval_matches_per_combo)),
        max_turns=max(20, int(args.eval_max_turns)),
        seed=int(args.seed),
        device=str(args.device),
        use_belief_mcts=bool(args.use_belief_mcts),
    )
    balance_best = _pick_best_balance(
        scenario_workers_candidates=scenario_workers_candidates,
        total_matches=max(8, int(args.balance_total_matches)),
        max_turns=max(20, int(args.eval_max_turns)),
        seed=int(args.seed),
        device=str(args.device),
        use_belief_mcts=bool(args.use_belief_mcts),
    )
    bias_scenario_best = _pick_best_bias_scenario_workers(
        scenario_workers_candidates=scenario_workers_candidates,
        total_matches_per_task=max(1, int(args.bias_task_matches)),
        max_turns=max(20, int(args.eval_max_turns)),
        seed=int(args.seed),
        device=str(args.device),
        use_belief_mcts=bool(args.use_belief_mcts),
    )
    bias_best = _pick_best_bias_parallel(
        parallel_workers_candidates=parallel_workers_candidates,
        scenario_workers=bias_scenario_best,
        total_matches_per_task=max(1, int(args.bias_task_matches)),
        max_turns=max(20, int(args.eval_max_turns)),
        seed=int(args.seed),
        device=str(args.device),
        use_belief_mcts=bool(args.use_belief_mcts),
    )

    start_env = _set_start_env(train_best, eval_best)
    balance_env = _set_balance_env(balance_best)
    bias_env = _set_bias_env(bias_scenario_best, bias_best)
    estimated_total = _find_total_runtime(
        train_best.eps_per_sec,
        eval_best.matches_per_sec,
        train_episodes=10000,
        eval_matches_total=1600,
    )

    report = {
        "train": {
            "num_envs": train_best.num_envs,
            "local_threads": train_best.local_threads,
            "episodes": train_best.episodes,
            "elapsed": round(train_best.elapsed, 3),
            "eps_per_sec": round(train_best.eps_per_sec, 3),
        },
        "eval": {
            "scenario_workers": eval_best.scenario_workers,
            "matches": eval_best.matches,
            "elapsed": round(eval_best.elapsed, 3),
            "matches_per_sec": round(eval_best.matches_per_sec, 3),
        },
        "make_balance": {
            "scenario_workers": balance_best.scenario_workers,
            "matches": balance_best.total_matches,
            "elapsed": round(balance_best.elapsed, 3),
            "matches_per_sec": round(balance_best.matches_per_sec, 3),
        },
        "bias_check": {
            "scenario_workers": bias_scenario_best,
            "parallel_workers": bias_best.parallel_workers,
            "task_count": bias_best.task_count,
            "matches": bias_best.total_matches,
            "elapsed": round(bias_best.elapsed, 3),
            "matches_per_sec": round(bias_best.matches_per_sec, 3),
        },
        "estimated_total_runtime_for_start_defaults_sec": round(estimated_total, 1),
        "selected_env": {
            "start": start_env,
            "make_balance": balance_env,
            "bias_check": bias_env,
        },
    }

    summary_text = json.dumps(report, ensure_ascii=False, indent=2)
    print("=== Parallel Optimization Summary ===")
    print(summary_text)
    print(f"[*] start env: {', '.join(f'{k}={v}' for k, v in start_env.items())}")
    print(f"[*] make_balance env: {', '.join(f'{k}={v}' for k, v in balance_env.items())}")
    print(f"[*] bias_check env: {', '.join(f'{k}={v}' for k, v in bias_env.items())}")

    summary_path = Path(args.summary_file) if args.summary_file else workspace_root / "log" / "find_opt_par_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_text + "\n", encoding="utf-8")
    print(f"[*] summary saved: {summary_path}")

    config_path = _save_parallel_opt_config(report)
    print(f"[*] optimization config saved: {config_path}")

    if args.benchmark_only:
        return 0

    return 0


if __name__ == "__main__":
    _script_started_at = time.perf_counter()
    try:
        _exit_code = main()
        print(f"[*] find_opt_par.py total runtime: {time.perf_counter() - _script_started_at:.1f}s")
        raise SystemExit(_exit_code)
    except Exception as exc:
        print("[!] find_opt_par.py failed")
        print(f"[!] error: {exc}")
        print(f"[*] find_opt_par.py total runtime: {time.perf_counter() - _script_started_at:.1f}s")
        raise SystemExit(1) from exc
