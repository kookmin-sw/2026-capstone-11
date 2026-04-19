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
    candidates: list[str] = []
    env_dotnet = os.getenv("DOTNET_CMD", "").strip()
    if env_dotnet:
        candidates.append(env_dotnet)
    for env_root_name in ("DOTNET_ROOT", "DOTNET_ROOT_X64"):
        env_root = os.getenv(env_root_name, "").strip()
        if env_root:
            root_candidate = str(Path(env_root) / ("dotnet.exe" if os.name == "nt" else "dotnet"))
            if root_candidate not in candidates:
                candidates.append(root_candidate)
    for candidate in [
        shutil.which("dotnet"),
        "/usr/bin/dotnet",
        "/usr/share/dotnet/dotnet",
        str(home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")),
    ]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for dotnet_cmd in candidates:
        try:
            info = subprocess.run([dotnet_cmd, "--info"], capture_output=True, text=True, check=True)
            print(info.stdout)
            return dotnet_cmd
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    print(
        "[!] No usable dotnet command found. Tried: "
        + ", ".join(candidates or ["<none>"])
        + "."
    )
    return ""


def _has_engine_binary() -> bool:
    home = Path.home()
    candidates = [
        home / "RL_AI" / "SeaEngine" / "csharp" / "SeaEngine" / "bin" / "Release" / "net10.0" / "SeaEngine.dll",
        home / "RL_AI" / "SeaEngine" / "csharp" / "SeaEngine" / "bin" / "Debug" / "net10.0" / "SeaEngine.dll",
    ]
    return any(path.exists() for path in candidates)


def _module_is_under_dir(module_name: str, base_dir: Path) -> bool:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False
    locations: list[str] = []
    if spec.origin:
        locations.append(spec.origin)
    if spec.submodule_search_locations:
        locations.extend(list(spec.submodule_search_locations))
    base = base_dir.resolve()
    for location in locations:
        try:
            if base in Path(location).resolve().parents or Path(location).resolve() == base:
                return True
        except Exception:
            continue
    return False


def _python_candidate_paths() -> list[str]:
    home = Path.home()
    candidates: list[str] = []
    for candidate in [
        os.getenv("PYTHON_CMD", "").strip(),
        sys.executable,
        "/opt/python/bin/python",
        "/usr/bin/python3.12",
        "/usr/bin/python3",
        str(home / ".local" / "bin" / "python"),
    ]:
        if candidate and candidate not in candidates and Path(candidate).exists():
            candidates.append(candidate)
    return candidates


def _probe_core_python_deps(python_cmd: str) -> tuple[bool, str]:
    probe_code = (
        "import torch, numpy, setuptools; "
        "print(torch.__version__); "
        "print(numpy.__version__); "
        "print(setuptools.__version__); "
        "print(torch.cuda.is_available())"
    )
    env = os.environ.copy()
    completed = subprocess.run(
        [python_cmd, "-c", probe_code],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path.home()),
        env=env,
    )
    if completed.returncode == 0:
        return True, completed.stdout.strip()
    return False, (completed.stdout + completed.stderr).strip()


def _probe_extra_python_deps(python_cmd: str) -> tuple[bool, str]:
    probe_code = "import pythonnet, clr_loader; print('pythonnet ok')"
    env = os.environ.copy()
    completed = subprocess.run(
        [python_cmd, "-c", probe_code],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path.home()),
        env=env,
    )
    if completed.returncode == 0:
        return True, completed.stdout.strip()
    return False, (completed.stdout + completed.stderr).strip()


def _ensure_python_deps() -> None:
    python_cmd = None
    core_probe_output = ""
    for candidate in _python_candidate_paths():
        ok, probe_output = _probe_core_python_deps(candidate)
        if ok:
            python_cmd = candidate
            core_probe_output = probe_output
            break
    if python_cmd is None:
        raise RuntimeError(
            "Core Python deps (torch/numpy/setuptools) are unavailable in the current environment. "
            "Please free disk space or point to a working Python environment."
        )

    deps_dir = Path(tempfile.gettempdir()) / "rl_ai_deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    if str(deps_dir) not in sys.path:
        sys.path.insert(0, str(deps_dir))

    if core_probe_output:
        print(core_probe_output)

    extra_ok, extra_output = _probe_extra_python_deps(python_cmd)
    if extra_ok:
        if extra_output:
            print(extra_output)
        return
    required = ["pythonnet", "clr_loader"]

    missing = [pkg for pkg in required if not _module_is_under_dir(pkg, deps_dir)]

    if missing:
        pip_cache_dir = deps_dir / ".pip-cache"
        pip_cache_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PIP_CACHE_DIR"] = str(pip_cache_dir)
        env["TMPDIR"] = str(deps_dir)
        completed = subprocess.run(
            [python_cmd, "-m", "pip", "install", "-q", "--upgrade", "--force-reinstall", "--target", str(deps_dir), *missing],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(deps_dir),
            env=env,
        )
        if completed.returncode != 0:
            if completed.stdout:
                print(completed.stdout)
            if completed.stderr:
                print(completed.stderr)
            raise RuntimeError(f"pip install failed with exit code {completed.returncode}")

    if str(deps_dir) not in sys.path:
        sys.path.insert(0, str(deps_dir))
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
    if not dotnet_cmd:
        if _has_engine_binary():
            print("[!] dotnet unavailable; using existing SeaEngine.dll without rebuilding.")
            return
        raise RuntimeError("dotnet is unavailable and no prebuilt SeaEngine.dll was found.")
    home = Path.home()
    project_root = home / "RL_AI" / "SeaEngine" / "csharp"
    engine_csproj = project_root / "SeaEngine" / "SeaEngine.csproj"

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

    from RL_AI.training import trainer as seaengine_trainer_module
    from RL_AI.SeaEngine.bridge import pythonnet_session as pythonnet_session_module
    from RL_AI.training import run_train_eval_experiment

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
        f"[*] args: eval_matches_per_combo={args.eval_matches} (total {args.eval_matches * 8}), train_episodes={args.train_episodes}, "
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
