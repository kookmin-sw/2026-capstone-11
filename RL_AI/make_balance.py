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


def _apply_parallel_opt_env(section: str) -> None:
    from RL_AI.start import _apply_parallel_opt_env as _shared_apply_parallel_opt_env

    _shared_apply_parallel_opt_env(section)


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


def _dotnet_executable(root: Path) -> Path:
    return root / ("dotnet.exe" if os.name == "nt" else "dotnet")


def _set_dotnet_env(dotnet_cmd: str) -> None:
    dotnet_root = _dotnet_root_from_cmd(dotnet_cmd)
    os.environ["DOTNET_CMD"] = dotnet_cmd
    os.environ["DOTNET_ROOT"] = dotnet_root
    os.environ["DOTNET_ROOT_X64"] = dotnet_root
    path_parts = os.environ.get("PATH", "").split(os.pathsep) if os.environ.get("PATH") else []
    dotnet_dir = str(Path(dotnet_cmd).resolve().parent)
    if dotnet_dir not in path_parts:
        os.environ["PATH"] = dotnet_dir + os.pathsep + os.environ.get("PATH", "")


def _try_dotnet(dotnet_cmd: str) -> bool:
    try:
        info = subprocess.run([dotnet_cmd, "--info"], capture_output=True, text=True, check=True)
        first_line = next((line.strip() for line in info.stdout.splitlines() if line.strip().startswith("Version:")), "")
        _set_dotnet_env(dotnet_cmd)
        print(f"dotnet ok: {dotnet_cmd}" + (f" ({first_line})" if first_line else ""))
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, OSError):
        return False


def _install_home_dotnet() -> str:
    if os.name == "nt":
        return ""
    home_dotnet = Path.home() / ".dotnet"
    dotnet_cmd = _dotnet_executable(home_dotnet)
    install_script = home_dotnet / "dotnet-install.sh"
    home_dotnet.mkdir(parents=True, exist_ok=True)

    if not install_script.exists():
        print("[*] installing dotnet SDK to ~/.dotnet via dotnet-install.sh...")
        download_commands = [
            ["curl", "-fsSL", "https://dot.net/v1/dotnet-install.sh", "-o", str(install_script)],
            ["wget", "-q", "https://dot.net/v1/dotnet-install.sh", "-O", str(install_script)],
        ]
        for command in download_commands:
            try:
                completed = subprocess.run(command, check=False, capture_output=True, text=True)
            except FileNotFoundError:
                continue
            if completed.returncode == 0 and install_script.exists():
                break
            if completed.stderr:
                print(completed.stderr)

    if not install_script.exists():
        print("[!] dotnet-install.sh download failed; ~/.dotnet install unavailable.")
        return ""

    install_commands = [
        ["bash", str(install_script), "--version", "10.0.107", "--install-dir", str(home_dotnet), "--no-path"],
        ["bash", str(install_script), "--channel", "10.0", "--quality", "ga", "--install-dir", str(home_dotnet), "--no-path"],
    ]
    for command in install_commands:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)
        if completed.returncode == 0 and dotnet_cmd.exists() and _try_dotnet(str(dotnet_cmd)):
            return str(dotnet_cmd)
        print(f"[!] home dotnet install step failed: {' '.join(command)} :: exit {completed.returncode}")
    return ""


def _ensure_dotnet() -> str:
    home = Path.home()
    candidates: list[str] = []
    env_dotnet = os.getenv("DOTNET_CMD", "").strip()
    if env_dotnet:
        candidates.append(env_dotnet)
    for env_root_name in ("DOTNET_ROOT", "DOTNET_ROOT_X64"):
        env_root = os.getenv(env_root_name, "").strip()
        if env_root:
            root_candidate = str(_dotnet_executable(Path(env_root)))
            if root_candidate not in candidates:
                candidates.append(root_candidate)
    for candidate in [
        str(_dotnet_executable(home / ".dotnet")),
        shutil.which("dotnet"),
        "/usr/bin/dotnet",
        "/usr/share/dotnet/dotnet",
    ]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for dotnet_cmd in candidates:
        if _try_dotnet(dotnet_cmd):
            return dotnet_cmd
    home_dotnet = _install_home_dotnet()
    if home_dotnet:
        return home_dotnet
    print("[!] No usable dotnet command found. Tried: " + ", ".join(candidates or ["<none>"]) + ".")
    return ""


def _default_scenario_workers() -> int:
    return 1


def _env_positive_int(name: str) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return 0
    return value if value > 0 else 0


def _resolve_scenario_workers(requested: int) -> int:
    if requested > 0:
        return requested
    env_value = _env_positive_int("SEAENGINE_SCENARIO_WORKERS")
    if env_value > 0:
        return env_value
    return _default_scenario_workers()


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


def _workspace_venv_dir() -> Path:
    return Path.home() / ".seaengine-venv"


def _workspace_venv_python() -> Path:
    venv_dir = _workspace_venv_dir()
    return venv_dir / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def _ensure_workspace_venv() -> str:
    venv_dir = _workspace_venv_dir()
    venv_python = _workspace_venv_python()
    venv_dir.mkdir(parents=True, exist_ok=True)

    if not venv_python.exists():
        print(f"[*] creating Python venv at {venv_dir}...")
        creator = sys.executable if Path(sys.executable).exists() else (which("python3") or which("python"))
        if not creator:
            raise RuntimeError("No Python interpreter available to create a workspace venv.")
        env = _python_probe_env()
        subprocess.run(
            [creator, "-m", "venv", str(venv_dir)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path.home()),
            env=env,
        )

    ok, _ = _probe_core_python_deps(str(venv_python))
    if ok:
        return str(venv_python)

    print(f"[*] installing core Python deps into {venv_dir}...")
    pip_cache_dir = venv_dir / ".pip-cache"
    pip_cache_dir.mkdir(parents=True, exist_ok=True)
    env = _python_probe_env()
    env["PIP_CACHE_DIR"] = str(pip_cache_dir)
    env["TMPDIR"] = str(venv_dir)
    completed = subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-q",
            "--upgrade",
            "--force-reinstall",
            "torch",
            "numpy",
            "setuptools",
            "grpcio",
            "protobuf",
            "pythonnet",
            "clr_loader",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(venv_dir),
        env=env,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)
        raise RuntimeError(f"venv bootstrap pip install failed with exit code {completed.returncode}")

    ok, probe_output = _probe_core_python_deps(str(venv_python))
    if not ok:
        raise RuntimeError(
            "Workspace venv bootstrap finished but core Python deps are still unavailable."
        )
    print(f"[*] workspace python venv ready: {venv_python}")
    print(probe_output)
    return str(venv_python)


def _python_candidate_paths() -> list[str]:
    home = Path.home()
    candidates: list[str] = []
    for candidate in [
        str(_workspace_venv_python()),
        os.getenv("PYTHON_CMD", "").strip(),
        os.getenv("SEAENGINE_PYTHON", "").strip(),
        which("python"),
        which("python3"),
        "/opt/python/bin/python",
        "/opt/python/bin/python3",
        "/opt/python/bin/python3.12",
        sys.executable,
        "/usr/bin/python3.12",
        "/usr/bin/python3",
        str(home / ".local" / "bin" / "python"),
        str(home / ".local" / "bin" / "python3"),
    ]:
        if candidate and candidate not in candidates and Path(candidate).exists():
            candidates.append(candidate)
    return candidates


def _python_probe_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _probe_core_python_deps(python_cmd: str) -> tuple[bool, str]:
    probe_code = (
        "import torch, numpy, setuptools; "
        "print(torch.__version__); "
        "print(numpy.__version__); "
        "print(setuptools.__version__); "
        "print(torch.cuda.is_available())"
    )
    completed = subprocess.run(
        [python_cmd, "-c", probe_code],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path.home()),
        env=_python_probe_env(),
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
        python_cmd = _ensure_workspace_venv()
        ok, probe_output = _probe_core_python_deps(python_cmd)
        if not ok:
            raise RuntimeError(
                "Core Python deps (torch/numpy/setuptools) are unavailable even after workspace venv bootstrap. "
                "Please free disk space or point to a working Python environment."
            )
        core_probe_output = probe_output

    if os.environ.get("SEAENGINE_PYTHON_SELECTED", "").strip() != "1":
        if Path(python_cmd).resolve() != Path(sys.executable).resolve() or os.getenv("PYTHONPATH") or os.getenv("PYTHONHOME"):
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
            argv.extend(sys.argv)
            os.execvpe(python_cmd, argv, env)

    deps_dir = Path(tempfile.gettempdir()) / "rl_ai_deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    if str(deps_dir) not in sys.path:
        sys.path.insert(0, str(deps_dir))

    if core_probe_output:
        print(core_probe_output)

    required = ["pytest", "grpcio", "protobuf", "pythonnet", "clr_loader"]
    missing = [pkg for pkg in required if importlib.util.find_spec(pkg) is None]
    if missing:
        completed = subprocess.run(
            [python_cmd, "-m", "pip", "install", "-q", "--upgrade", "--force-reinstall", "--target", str(deps_dir), *missing],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(deps_dir),
            env=_python_probe_env() | {"PIP_CACHE_DIR": str(deps_dir / ".pip-cache"), "TMPDIR": str(deps_dir)},
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
    import pytest


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
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_MODE", "restore")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_SIMS", "1")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_TOP_K", "2")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS", "1")

    dotnet_cmd = _ensure_dotnet()
    if dotnet_cmd:
        dotnet_root = os.environ["DOTNET_ROOT"]
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
    parser.add_argument(
        "--use-belief-mcts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Evaluate saved RL through the shallow belief-MCTS wrapper",
    )
    parser.add_argument("--log-file", type=str, default="")
    args = parser.parse_args()

    workspace_dir = Path.home() / "RL_AI"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_log = Path.home() / "make_balance.log"
    log_file = Path(args.log_file) if args.log_file else default_log
    _setup_logger(log_file)

    os.environ.setdefault("SEAENGINE_VECTOR_BACKEND", "local")
    os.environ.setdefault("SEAENGINE_NUM_ENVS", "1")
    os.environ.setdefault("SEAENGINE_LOCAL_THREADS", "0")
    os.environ.setdefault("SEAENGINE_WORKERS", "0")
    os.environ.setdefault("SEAENGINE_LOCAL_MAX_WORKERS", "0")
    os.environ.setdefault("SEAENGINE_SCENARIO_WORKERS", "1")
    os.environ.setdefault("SEAENGINE_PARALLEL_WORKERS", "1")
    os.environ.setdefault("SEAENGINE_FAST_POOL", "0")
    _ensure_python_deps()
    _apply_parallel_opt_env("make_balance")
    _prepare_project_dir()

    print("[*] make_balance.py launched")
    print(f"[*] pid={os.getpid()}")
    print(
        f"[*] args: model_path={args.model_path or '(auto-latest)'}, total_matches={args.total_matches}, "
        f"max_turns={args.max_turns}, seed={args.seed}, device={args.device}, "
        f"model_hidden_dim={os.environ.get('SEAENGINE_MODEL_HIDDEN_DIM', '192')}, "
        f"progress_interval={args.progress_interval}, scenario_workers={args.scenario_workers}, "
        f"scenario_shards={args.scenario_shards}, "
        f"belief_mcts_sims={os.environ.get('SEAENGINE_BELIEF_MCTS_SIMS', '1')}, "
        f"belief_mcts_top_k={os.environ.get('SEAENGINE_BELIEF_MCTS_TOP_K', '2')}, "
        f"belief_mcts_rollout_steps={os.environ.get('SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS', '2')}, "
        f"use_belief_mcts={args.use_belief_mcts}, belief_mcts_mode={os.environ.get('SEAENGINE_BELIEF_MCTS_MODE', 'restore')}, "
        f"include_history={not args.no_history and args.history_limit >= 0}, history_limit={args.history_limit}"
    )

    scenario_workers = _resolve_scenario_workers(args.scenario_workers)
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
