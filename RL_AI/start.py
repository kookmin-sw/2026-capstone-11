#!/usr/bin/env python3
"""Run SeaEngine train/eval pipeline without notebook.

Usage (DLPC):
  python -u ~/RL_AI/start.py
  nohup python -u ~/RL_AI/start.py > /dev/null 2>&1 &
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
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from shutil import which
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


def _publish_latest_artifact(src_path: str | Path | None, dst_path: Path) -> str | None:
    if not src_path:
        return None
    src = Path(src_path)
    if not src.exists():
        return None
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


def _ensure_dotnet() -> str:
    home = Path.home()
    dotnet_cmd = shutil.which("dotnet")
    if dotnet_cmd is None:
        bundled = home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
        if bundled.exists():
            dotnet_cmd = str(bundled)

    if dotnet_cmd is None:
        install_script = home / "dotnet-install.sh"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.sh", install_script)
        subprocess.run(
            ["bash", str(install_script), "--channel", "10.0", "--install-dir", str(home / ".dotnet")],
            check=True,
        )
        dotnet_cmd = str(home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet"))

    info = subprocess.run([dotnet_cmd, "--info"], capture_output=True, text=True, check=True)
    print(info.stdout)
    return dotnet_cmd


def _ensure_python_deps() -> None:
    deps_dir = Path.home() / ".rl_ai_deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    if str(deps_dir) not in sys.path:
        sys.path.insert(0, str(deps_dir))

    required = ["torch", "numpy", "pytest", "pythonnet", "clr_loader"]
    missing = [pkg for pkg in required if importlib.util.find_spec(pkg) is None]

    if missing:
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

    import numpy
    import setuptools
    import torch

    print(sys.executable)
    print(torch.__version__)
    print(numpy.__version__)
    print(setuptools.__version__)
    print(torch.cuda.is_available())


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


def _build_csharp(dotnet_cmd: str) -> None:
    home = Path.home()
    project_root = home / "RL_AI" / "SeaEngine" / "csharp"
    cli_csproj = project_root / "SeaEngineCli" / "SeaEngineCli.csproj"
    engine_csproj = project_root / "SeaEngine" / "SeaEngine.csproj"

    subprocess.run([dotnet_cmd, "build", str(cli_csproj), "-c", "Debug", "-v", "q"], check=True)
    subprocess.run([dotnet_cmd, "build", str(engine_csproj), "-c", "Release", "-v", "q"], check=True)
    print("SeaEngine build ok")


def _run_train_eval(
    eval_matches: int,
    train_episodes: int,
    max_turns: int,
    update_interval: int,
    seed: int,
    *,
    resume_model_path: str = "",
    resume_episodes_completed: int = 0,
    resume_skip_pre_eval: bool = False,
) -> None:
    os.environ.setdefault("SEAENGINE_VECTOR_BACKEND", "local")
    os.environ.setdefault("SEAENGINE_LOCAL_THREADS", "1")
    os.environ.setdefault("SEAENGINE_QUIET_WORKER_LOG", "1")
    os.environ.setdefault("SEAENGINE_FAST_POOL", "0")
    os.environ.setdefault("SEAENGINE_TRAIN_MAX_TURNS", "100")

    home = Path.home()
    if str(home) not in sys.path:
        sys.path.insert(0, str(home))

    dotnet_cmd = which("dotnet")
    if dotnet_cmd is None:
        fallback = home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
        if fallback.exists():
            dotnet_cmd = str(fallback)
    if dotnet_cmd:
        os.environ["DOTNET_CMD"] = dotnet_cmd
        dotnet_root = str(Path(dotnet_cmd).resolve().parent)
        os.environ.setdefault("DOTNET_ROOT", dotnet_root)
        os.environ.setdefault("DOTNET_ROOT_X64", dotnet_root)

    for module_name in list(sys.modules):
        if module_name == "RL_AI" or module_name.startswith("RL_AI."):
            del sys.modules[module_name]
    importlib.invalidate_caches()

    from RL_AI.SeaEngine import trainer as seaengine_trainer_module
    from RL_AI.SeaEngine.bridge import pythonnet_session as pythonnet_session_module
    from RL_AI.SeaEngine.experiment import run_train_eval_experiment

    print(f"trainer source: {seaengine_trainer_module.__file__}")
    print(f"pythonnet source: {pythonnet_session_module.__file__}")

    result = run_train_eval_experiment(
        eval_matches=eval_matches,
        train_episodes=train_episodes,
        max_turns=max_turns,
        update_interval=update_interval,
        seed=seed,
        resume_model_path=resume_model_path or None,
        resume_episodes_completed=resume_episodes_completed if resume_model_path else None,
        resume_skip_pre_eval=resume_skip_pre_eval,
    )

    latest_log_zip = _publish_latest_artifact(
        result.get("log_zip_path"),
        Path.home() / "RL_AI" / "log" / "start_latest.zip",
    )
    latest_model_zip = _publish_latest_artifact(
        result.get("model_zip_path"),
        Path.home() / "RL_AI" / "models" / "start_latest.zip",
    )

    print("=== SeaEngine Train/Eval Experiment ===")
    print(result["train"])
    print(f"artifact log zip: {latest_log_zip}")
    print(f"artifact model zip: {latest_model_zip}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SeaEngine train/eval runner")
    parser.add_argument("--eval-matches", type=int, default=50)
    parser.add_argument("--train-episodes", type=int, default=10000)
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--update-interval", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--skip-unzip", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--log-file", type=str, default="")
    parser.add_argument("--resume-model-path", type=str, default="")
    parser.add_argument("--resume-episodes-completed", type=int, default=0)
    parser.add_argument("--resume-skip-pre-eval", action="store_true")
    args = parser.parse_args()

    workspace_dir = Path.home() / "RL_AI"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_log = Path.home() / "start.log"
    log_file = Path(args.log_file) if args.log_file else default_log
    _setup_logger(log_file)

    dotnet_cmd = _ensure_dotnet()

    _ensure_python_deps()

    if not args.skip_unzip:
        _prepare_project_dir()

    print("[*] start.py launched")
    print(f"[*] pid={os.getpid()}")
    print(
        f"[*] args: eval_matches={args.eval_matches}, train_episodes={args.train_episodes}, "
        f"max_turns={args.max_turns}, update_interval={args.update_interval}, seed={args.seed}, "
        f"skip_unzip={args.skip_unzip}, skip_build={args.skip_build}"
    )

    if not args.skip_build:
        _build_csharp(dotnet_cmd)

    _run_train_eval(
        eval_matches=args.eval_matches,
        train_episodes=args.train_episodes,
        max_turns=args.max_turns,
        update_interval=args.update_interval,
        seed=args.seed,
        resume_model_path=args.resume_model_path,
        resume_episodes_completed=args.resume_episodes_completed,
        resume_skip_pre_eval=args.resume_skip_pre_eval,
    )
    print("[*] start.py finished successfully")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("[!] start.py failed")
        print(f"[!] error: {exc}")
        print(traceback.format_exc())
        raise
