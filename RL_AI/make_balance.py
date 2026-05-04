#!/usr/bin/env python3
"""Run saved-model balancing evaluation without notebook.

Usage (DLPC):
  python -u ~/RL_AI/make_balance.py
  nohup python -u ~/RL_AI/make_balance.py > /dev/null 2>&1 &
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from shutil import which
import threading
import time


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


def _format_elapsed(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours, remainder = divmod(int(seconds), 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d} ({seconds:.1f}s)"


def _install_dotnet_sdk() -> None:
    if os.name == "nt":
        return
    install_steps = [
        ["sudo", "apt", "update"],
        ["sudo", "apt", "install", "-y", "dotnet-sdk-10.0"],
    ]
    for step in install_steps:
        completed = subprocess.run(
            step,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
        )
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)
        if completed.returncode != 0:
            print(f"[!] dotnet auto-install step failed: {' '.join(step)} :: exit {completed.returncode}")
            break


def _dotnet_root_from_cmd(dotnet_cmd: str) -> str:
    try:
        info = subprocess.run([dotnet_cmd, "--info"], capture_output=True, text=True, check=True)
        for line in info.stdout.splitlines():
            if "Base Path:" in line:
                base_path = line.split("Base Path:", 1)[1].strip()
                return str(Path(base_path).resolve().parents[1])
    except Exception:
        pass
    cmd_path = Path(dotnet_cmd).resolve()
    if cmd_path.parent.name == "bin" and cmd_path.parent.parent.name:
        return str(cmd_path.parent.parent)
    return str(cmd_path.parent)


def _default_scenario_workers() -> int:
    return max(1, min(8, os.cpu_count() or 1))


def _publish_latest_artifact(src_path: str | Path | None, dst_path: Path) -> str | None:
    if not src_path:
        return None
    src = Path(src_path)
    if not src.exists():
        return None
    if src.resolve() == dst_path.resolve():
        return str(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_path)
    return str(dst_path)


def _zip_signature(zip_path: Path) -> str:
    stat = zip_path.stat()
    return f"{zip_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"


def _acquire_lock(lock_path: Path, *, timeout_sec: int = 1800) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_sec
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
                lock_file.write(str(os.getpid()))
            return
        except FileExistsError:
            if time.time() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock: {lock_path}")
            time.sleep(1)


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _ensure_python_deps() -> None:
    deps_dir = Path.home() / ".rl_ai_deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    if str(deps_dir) not in sys.path:
        sys.path.insert(0, str(deps_dir))

    required = ["torch", "numpy", "pytest", "pythonnet", "clr_loader"]
    missing = [pkg for pkg in required if importlib.util.find_spec(pkg) is None]
    if missing:
        import subprocess

        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--target", str(deps_dir), *missing],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            if completed.stdout:
                print(completed.stdout)
            if completed.stderr:
                print(completed.stderr)
            raise RuntimeError(f"pip install failed with exit code {completed.returncode}")


def _prepare_project_dir() -> None:
    home = Path.home()
    zip_candidates = [Path.cwd() / "RL_AI.zip", home / "RL_AI.zip"]
    zip_path = next((path for path in zip_candidates if path.exists()), None)
    target_dir = home / "RL_AI"
    lock_path = home / ".rl_ai_prepare.lock"
    marker_path = target_dir / ".source_zip_signature"
    log_backup_dir = home / ".rl_ai_log_backup"

    if zip_path is None:
        print("RL_AI.zip not found, skipping unzip")
        return

    signature = _zip_signature(zip_path)
    _acquire_lock(lock_path)
    try:
        if target_dir.exists() and marker_path.exists():
            try:
                if marker_path.read_text(encoding="utf-8").strip() == signature:
                    print("RL_AI ready")
                    return
            except Exception:
                pass

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmp_path)

            nested_root = tmp_path / "RL_AI"
            source_root = nested_root if nested_root.exists() else tmp_path
            if target_dir.exists() and (target_dir / "log").exists():
                if log_backup_dir.exists():
                    shutil.rmtree(log_backup_dir)
                shutil.move(str(target_dir / "log"), str(log_backup_dir))
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            for item in source_root.iterdir():
                shutil.move(str(item), str(target_dir / item.name))
            if log_backup_dir.exists():
                if (target_dir / "log").exists():
                    shutil.rmtree(target_dir / "log")
                shutil.move(str(log_backup_dir), str(target_dir / "log"))
            marker_path.write_text(signature, encoding="utf-8")
        print("RL_AI ready")
    finally:
        _release_lock(lock_path)


def _resolve_model_path(model_path: str) -> Path:
    def _extract_zip_model(zip_path: Path) -> Path:
        cache_root = Path.home() / ".rl_ai_model_cache"
        signature = _zip_signature(zip_path).replace(os.sep, "_").replace(":", "_").replace("|", "_")
        extract_dir = cache_root / zip_path.stem / signature
        extract_dir.mkdir(parents=True, exist_ok=True)
        marker = extract_dir / ".extracted"
        if not marker.exists():
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)
            marker.write_text(signature, encoding="utf-8")
        pt_candidates = sorted(extract_dir.rglob("*.pt"), key=lambda p: p.stat().st_mtime)
        if not pt_candidates:
            raise FileNotFoundError(f"No .pt model found inside zip: {zip_path}")
        preferred = [p for p in pt_candidates if p.name == "model_ep_10000.pt"]
        if preferred:
            return preferred[-1]
        return pt_candidates[-1]

    path = Path(model_path) if model_path else Path()
    if model_path and path.exists():
        return _extract_zip_model(path) if path.suffix.lower() == ".zip" else path

    models_dir = Path.home() / "RL_AI" / "models"
    direct_model = models_dir / "model_ep_10000.pt"
    if direct_model.exists():
        return direct_model

    zip_candidates = sorted(models_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    if not zip_candidates:
        raise FileNotFoundError("No model_ep_10000.pt or model zip found in ~/RL_AI/models")

    return _extract_zip_model(zip_candidates[-1])


def _collect_balance_artifacts(result: dict[str, object]) -> list[Path]:
    artifacts: list[Path] = []

    def _add(path_like: object) -> None:
        if not path_like:
            return
        path = Path(str(path_like))
        if path.exists() and path not in artifacts:
            artifacts.append(path)

    _add(result.get("summary_report_path"))
    _add(result.get("history_report_path"))
    for scenario in result.get("scenario_results", []):
        if not isinstance(scenario, dict):
            continue
        _add(scenario.get("report_path"))
        _add(scenario.get("history_path"))
        for path_like in scenario.get("shard_report_paths", []):
            _add(path_like)
        for path_like in scenario.get("shard_history_paths", []):
            _add(path_like)

    return sorted(artifacts, key=lambda p: p.name)


def _zip_balance_artifacts(artifact_paths: list[Path]) -> Path | None:
    if not artifact_paths:
        print("no balance artifacts to zip")
        return None
    log_dir = Path.home() / "RL_AI" / "log"
    zip_path = log_dir / "make_balance_latest.zip"
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in artifact_paths:
            zf.write(p, arcname=p.name)
    for p in artifact_paths:
        if p.name == "make_balance_summary.txt" or p.resolve() == zip_path.resolve():
            continue
        try:
            p.unlink()
        except OSError:
            pass
    print(f"log zip: {zip_path}")
    return zip_path


def _run_balance(
    *,
    model_path: Path,
    total_matches: int,
    max_turns: int,
    seed: int,
    device: str,
    progress_interval: int,
    scenario_workers: int,
    scenario_shards: int,
    include_history: bool,
    history_limit: int | None,
    use_belief_mcts: bool,
) -> dict[str, object]:
    run_started_at = time.perf_counter()
    scenario_started_at: dict[str, float] = {}
    scenario_totals: dict[str, int] = {}
    progress_lock = threading.Lock()
    home = Path.home()
    if str(home) not in sys.path:
        sys.path.insert(0, str(home))
    os.environ.setdefault("SEAENGINE_SUPPRESS_NATIVE_LOGS", "1")

    dotnet_cmd = which("dotnet")
    if dotnet_cmd is None:
        fallback = home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
        if fallback.exists():
            dotnet_cmd = str(fallback)
    if not dotnet_cmd:
        _install_dotnet_sdk()
        dotnet_cmd = which("dotnet")
        if dotnet_cmd is None:
            fallback = home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
            if fallback.exists():
                dotnet_cmd = str(fallback)
    if dotnet_cmd:
        os.environ["DOTNET_CMD"] = dotnet_cmd
        dotnet_root = _dotnet_root_from_cmd(dotnet_cmd)
        os.environ["DOTNET_ROOT"] = dotnet_root
        os.environ["DOTNET_ROOT_X64"] = dotnet_root
        print(f"[*] dotnet command: {dotnet_cmd}")
        print(f"[*] dotnet root: {dotnet_root}")

    for module_name in list(sys.modules):
        if module_name == "RL_AI" or module_name.startswith("RL_AI."):
            del sys.modules[module_name]
    importlib.invalidate_caches()

    from RL_AI.training import experiment as seaengine_experiment_module
    from RL_AI.training import run_saved_model_balance_experiment

    print(f"experiment source: {seaengine_experiment_module.__file__}")
    print(f"using model: {model_path}")

    def _progress_logger(label: str, current: int, total: int, result: str, matchup: str) -> None:
        interval = max(1, int(progress_interval))
        with progress_lock:
            if label not in scenario_started_at:
                scenario_started_at[label] = time.perf_counter()
                scenario_totals[label] = total
            if current != total and current % interval != 0:
                return
            scenario_elapsed = max(1e-9, time.perf_counter() - scenario_started_at[label])
            scenario_speed = current / scenario_elapsed
            overall_done = sum(
                total if key != label else current
                for key, total in scenario_totals.items()
            )
            overall_elapsed = max(1e-9, time.perf_counter() - run_started_at)
            overall_speed = overall_done / overall_elapsed
            print(
                f"[*] Balance progress | {label} | {current}/{total} "
                f"| speed={scenario_speed:.2f} eps/s | overall={overall_speed:.2f} eps/s "
                f"| last_result={result} | matchup={matchup}"
            )

    result = run_saved_model_balance_experiment(
        model_path=str(model_path),
        total_matches=total_matches,
        max_turns=max_turns,
        seed=seed,
        device=device,
        opponent_mode="self",
        include_history=include_history,
        history_limit=history_limit,
        progress_callback=_progress_logger,
        scenario_workers=scenario_workers,
        scenario_shards=scenario_shards,
        use_belief_mcts=use_belief_mcts,
    )

    summary_copy = _publish_latest_artifact(
        result.get("summary_report_path"),
        Path.home() / "RL_AI" / "log" / "make_balance_summary.txt",
    )
    print("=== SeaEngine Balance Experiment ===")
    total_elapsed = max(1e-9, time.perf_counter() - run_started_at)
    total_speed = total_matches / total_elapsed if total_matches > 0 else 0.0
    print(f"avg speed: {total_speed:.2f} eps/s")
    print(result["aggregate"])
    print(f"artifact summary: {summary_copy}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="SeaEngine saved-model balance runner")
    parser.add_argument("--model-path", type=str, default="")
    parser.add_argument("--total-matches", type=int, default=2000)
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--progress-interval", type=int, default=50)
    parser.add_argument("--scenario-workers", type=int, default=0)
    parser.add_argument("--scenario-shards", type=int, default=1, help="Split each of the 8 balance scenarios into N independent tasks")
    parser.add_argument("--no-history", action="store_true", help="Skip representative match histories for faster large runs")
    parser.add_argument("--history-limit", type=int, default=0, help="Representative histories per scenario (0 = auto, negative = none)")
    parser.add_argument("--use-belief-mcts", action="store_true", help="Evaluate saved RL through the shallow belief-MCTS wrapper")
    parser.add_argument("--log-file", type=str, default="")
    args = parser.parse_args()

    workspace_dir = Path.home() / "RL_AI"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_log = Path.home() / "make_balance.log"
    log_file = Path(args.log_file) if args.log_file else default_log
    _setup_logger(log_file)

    _ensure_python_deps()
    _prepare_project_dir()

    print("[*] make_balance.py launched")
    print(f"[*] pid={os.getpid()}")
    print(
        f"[*] args: model_path={args.model_path or '(auto-latest)'}, total_matches={args.total_matches}, "
        f"max_turns={args.max_turns}, seed={args.seed}, device={args.device}, "
        f"progress_interval={args.progress_interval}, scenario_workers={args.scenario_workers}, "
        f"scenario_shards={args.scenario_shards}, "
        f"use_belief_mcts={args.use_belief_mcts}, "
        f"include_history={not args.no_history and args.history_limit >= 0}, history_limit={args.history_limit}"
    )

    scenario_workers = args.scenario_workers if args.scenario_workers > 0 else _default_scenario_workers()
    scenario_shards = max(1, int(args.scenario_shards))
    include_history = (not args.no_history) and args.history_limit >= 0
    history_limit = None if args.history_limit == 0 else max(0, args.history_limit)
    print(f"[*] resolved scenario_workers={scenario_workers} | scenario_shards={scenario_shards}")
    model_path = _resolve_model_path(args.model_path)
    print(f"[*] resolved model: {model_path}")
    result = _run_balance(
        model_path=model_path,
        total_matches=args.total_matches,
        max_turns=args.max_turns,
        seed=args.seed,
        device=args.device,
        progress_interval=args.progress_interval,
        scenario_workers=scenario_workers,
        scenario_shards=scenario_shards,
        include_history=include_history,
        history_limit=history_limit,
        use_belief_mcts=args.use_belief_mcts,
    )
    artifact_paths = _collect_balance_artifacts(result)
    log_zip_path = _zip_balance_artifacts(artifact_paths)
    print(f"artifact log zip: {log_zip_path}")
    print("[*] make_balance.py finished successfully")
    return 0


if __name__ == "__main__":
    _script_started_at = time.perf_counter()
    try:
        _exit_code = main()
        print(f"[*] make_balance.py total runtime: {_format_elapsed(time.perf_counter() - _script_started_at)}")
        raise SystemExit(_exit_code)
    except Exception as exc:
        print("[!] make_balance.py failed")
        print(f"[!] error: {exc}")
        print(traceback.format_exc())
        print(f"[*] make_balance.py total runtime: {_format_elapsed(time.perf_counter() - _script_started_at)}")
        raise SystemExit(1) from exc
