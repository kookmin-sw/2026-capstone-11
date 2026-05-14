#!/usr/bin/env python3
r"""Windows launcher for SeaEngine RL_AI bias_check.py.

Expected layout:
  %USERPROFILE%\
    RL_AI.zip
    bias_check_w.py
    RL_AI\

Run:
  cd $env:USERPROFILE
  py -3.12 -u .\bias_check_w.py
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from datetime import datetime
from pathlib import Path


def _format_elapsed(seconds: float) -> str:
    seconds_i = int(max(0, seconds))
    hours, remainder = divmod(seconds_i, 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d} ({seconds:.1f}s)"


def _on_rm_error(func, path, exc_info) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


def _safe_rmtree(path: Path) -> None:
    if not path.exists():
        return
    last_exc: Exception | None = None
    for _ in range(5):
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            return
        except Exception as exc:
            last_exc = exc
            time.sleep(0.5)
    if last_exc:
        raise last_exc


def _prepare_project_dir_windows() -> None:
    home = Path.home().resolve()
    os.chdir(str(home))

    zip_path = home / "RL_AI.zip"
    target_dir = home / "RL_AI"
    log_backup_dir = home / ".rl_ai_log_backup_w"

    if not zip_path.exists():
        raise FileNotFoundError(f"RL_AI.zip not found: {zip_path}")

    if target_dir.exists() and (target_dir / "log").exists():
        _safe_rmtree(log_backup_dir)
        shutil.move(str(target_dir / "log"), str(log_backup_dir))

    _safe_rmtree(target_dir)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        nested = tmp_dir / "RL_AI"
        source_root = nested if nested.exists() else tmp_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        for item in source_root.iterdir():
            shutil.move(str(item), str(target_dir / item.name))

    if log_backup_dir.exists():
        if (target_dir / "log").exists():
            _safe_rmtree(target_dir / "log")
        shutil.move(str(log_backup_dir), str(target_dir / "log"))

    print(f"RL_AI ready: {target_dir}")


def _dotnet_executable(root: Path) -> Path:
    return root / "dotnet.exe"


def _dotnet_has_required_sdk(dotnet_cmd: str, required_major: int = 10) -> bool:
    try:
        completed = subprocess.run(
            [dotnet_cmd, "--list-sdks"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, OSError):
        return False
    prefix = f"{required_major}."
    return any(line.strip().startswith(prefix) for line in (completed.stdout or "").splitlines())


def _configure_dotnet_env(home: Path) -> None:
    candidates = [
        str(_dotnet_executable(home / ".dotnet")),
        shutil.which("dotnet"),
    ]
    for dotnet in candidates:
        if not dotnet or not _dotnet_has_required_sdk(dotnet):
            continue
        dotnet_dir = str(Path(dotnet).resolve().parent)
        os.environ.setdefault("DOTNET_CMD", dotnet)
        os.environ.setdefault("DOTNET_ROOT", dotnet_dir)
        os.environ.setdefault("DOTNET_ROOT_X64", dotnet_dir)
        return


def _configure_windows_env() -> None:
    home = Path.home().resolve()
    os.chdir(str(home))

    if str(home) not in sys.path:
        sys.path.insert(0, str(home))

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONNOUSERSITE", "1")

    os.environ.setdefault("DOTNET_NOLOGO", "1")
    os.environ.setdefault("DOTNET_CLI_TELEMETRY_OPTOUT", "1")
    os.environ.setdefault("DOTNET_CLI_UI_LANGUAGE", "en")

    _configure_dotnet_env(home)

    os.environ.setdefault("SEAENGINE_VECTOR_BACKEND", "isolated")
    os.environ.setdefault("SEAENGINE_NUM_ENVS", "4")
    os.environ.setdefault("SEAENGINE_LOCAL_THREADS", "0")
    os.environ.setdefault("SEAENGINE_WORKERS", "0")
    os.environ.setdefault("SEAENGINE_LOCAL_MAX_WORKERS", "0")
    os.environ.setdefault("SEAENGINE_SCENARIO_WORKERS", "2")
    os.environ.setdefault("SEAENGINE_PARALLEL_WORKERS", "1")
    os.environ.setdefault("SEAENGINE_FAST_POOL", "0")
    os.environ.setdefault("SEAENGINE_QUIET_WORKER_LOG", "1")
    os.environ.setdefault("SEAENGINE_SUPPRESS_NATIVE_LOGS", "1")
    os.environ.setdefault("SEAENGINE_TRAIN_MAX_TURNS", "70")

    # Keep Windows launcher aligned with the current training/evaluation defaults.
    os.environ.setdefault("SEAENGINE_TRAIN_LAYOUT_MODE", "hard_mixed")

    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_MODE", "restore")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_SIMS", "1")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_TOP_K", "2")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS", "1")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_CANDIDATE_MIXING_STRATEGY", "policy_prior_plus_heuristic_topk")

    os.environ.setdefault("SEAENGINE_PPO_LR", "0.0001")
    os.environ.setdefault("SEAENGINE_PPO_ENTROPY", "0.006")
    os.environ.setdefault("SEAENGINE_PPO_TARGET_KL", "0.08")
    os.environ.setdefault("SEAENGINE_PPO_MAX_GRAD_NORM", "0.5")

    os.environ.setdefault("SEAENGINE_SAVE_SCENARIO_REPORTS", "0")
    os.environ.setdefault("SEAENGINE_SAVE_SCENARIO_HISTORIES", "0")
    os.environ.setdefault("SEAENGINE_EVAL_HISTORY_LIMIT", "50")
    os.environ.setdefault("SEAENGINE_LOG_ARCHIVE_MODE", "compact")


def main() -> int:
    started_at = time.perf_counter()
    print(f"[*] bias_check_w.py start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        _configure_windows_env()
        _prepare_project_dir_windows()

        import RL_AI.bias_check as bias_module

        if "--skip-unzip" not in sys.argv:
            sys.argv.append("--skip-unzip")
        if "--log-file" not in sys.argv:
            sys.argv.extend(["--log-file", str(Path.home() / "bias_check.log")])

        return int(bias_module.main())

    except Exception as exc:
        print("[!] bias_check_w.py failed")
        print(f"[!] error: {exc}")
        print(traceback.format_exc())
        return 1

    finally:
        print(f"[*] bias_check_w.py total runtime: {_format_elapsed(time.perf_counter() - started_at)}")


if __name__ == "__main__":
    raise SystemExit(main())
