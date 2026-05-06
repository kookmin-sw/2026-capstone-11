#!/usr/bin/env python3
"""Bias / symmetry checks for SeaEngine RL agents.

This script keeps the environment bootstrap from start.py locally, while
running focused experiments for:
  - random/random, greedy/greedy, RL/RL self-play comparisons
  - normalized vs raw performance comparison
  - normalized-raw agreement measurement
  - checkpoint-by-checkpoint side-gap tracking

It intentionally does not modify start.py.
"""

from __future__ import annotations

import argparse
import copy
import concurrent.futures
import importlib
import importlib.util
import io
import json
import os
import multiprocessing as mp
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
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
            root_candidate = str(Path(env_root) / ("dotnet.exe" if os.name == "nt" else "dotnet"))
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
    env = _python_probe_env()
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
    probe_code = "import grpc; from google.protobuf import json_format; import pythonnet, clr_loader; print('grpc/pythonnet ok')"
    env = _python_probe_env()
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

    extra_ok, extra_output = _probe_extra_python_deps(python_cmd)
    if extra_ok:
        if extra_output:
            print(extra_output)
        return
    required = ["grpcio", "protobuf", "pythonnet", "clr_loader"]

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
    engine_csproj = project_root / "SeaEngine" / "SeaEngine.csproj"

    if not dotnet_cmd:
        if _has_engine_binary():
            print("[!] dotnet unavailable; using existing SeaEngine.dll without rebuilding.")
            return
        raise RuntimeError("dotnet is unavailable and no prebuilt SeaEngine.dll was found.")

    if engine_csproj.exists():
        subprocess.run([dotnet_cmd, "build", str(engine_csproj), "-c", "Release", "-v", "q"], check=True)
    else:
        raise FileNotFoundError(f"Missing engine project: {engine_csproj}")
    print("SeaEngine build ok")


def _configure_runtime_env() -> str:
    os.environ.setdefault("SEAENGINE_VECTOR_BACKEND", "local")
    os.environ.setdefault("SEAENGINE_LOCAL_THREADS", "1")
    os.environ.setdefault("SEAENGINE_QUIET_WORKER_LOG", "1")
    os.environ.setdefault("SEAENGINE_SUPPRESS_NATIVE_LOGS", "1")
    os.environ.setdefault("SEAENGINE_FAST_POOL", "0")
    os.environ.setdefault("SEAENGINE_TRAIN_MAX_TURNS", "100")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_MODE", "restore")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_SIMS", "2")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_TOP_K", "3")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS", "2")

    home = Path.home()
    if str(home) not in sys.path:
        sys.path.insert(0, str(home))

    dotnet_cmd = os.getenv("DOTNET_CMD", "").strip() or which("dotnet")
    if dotnet_cmd is None:
        fallback = home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
        if fallback.exists():
            dotnet_cmd = str(fallback)
    if dotnet_cmd:
        _set_dotnet_env(dotnet_cmd)
        dotnet_root = os.environ["DOTNET_ROOT"]
        print(f"[*] dotnet command: {dotnet_cmd}")
        print(f"[*] dotnet root: {dotnet_root}")
    return dotnet_cmd or "dotnet"


def _resolve_device(device: Optional[str]) -> str:
    requested = "auto" if device is None else str(device).strip().lower()
    if requested in {"auto", ""}:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    if requested in {"cuda", "gpu"}:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    return requested


def _latest_file(files: Iterable[Path]) -> Optional[Path]:
    candidates = [p for p in files if p.exists()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p.stat().st_mtime, p.name))
    return candidates[-1]


def _episode_from_name(path: Path) -> int:
    stem = path.stem
    if stem.startswith("model_ep_"):
        try:
            return int(stem.split("_")[-1])
        except Exception:
            return -1
    return -1


def _resolve_model_source(model_path: str | None) -> Path:
    if model_path:
        path = Path(model_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    model_dir = Path.home() / "RL_AI" / "models"
    latest = _latest_file(list(model_dir.glob("model_*.zip")) + list(model_dir.glob("model_*.pt")))
    if latest is None:
        raise FileNotFoundError(f"No model archive or pt file found in {model_dir}")
    return latest


def _extract_model_archive(archive_path: Path, dest_dir: Path) -> list[Path]:
    if archive_path.suffix.lower() != ".zip":
        return [archive_path]
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(dest_dir)
    pt_files = sorted(dest_dir.glob("model_ep_*.pt"), key=_episode_from_name)
    if not pt_files:
        pt_files = sorted(dest_dir.glob("*.pt"))
    return pt_files


def _load_state_dict(model_path: Path) -> Dict[str, Any]:
    import torch

    return torch.load(model_path, map_location="cpu")


def _standard_decks() -> list[tuple[str, str]]:
    return [
        ("귤", json.dumps(["Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P"])),
        ("샤를로테", json.dumps(["Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P"])),
    ]


def _scenario_definitions(prefix: str) -> list[Dict[str, Any]]:
    decks = _standard_decks()
    scenarios: list[Dict[str, Any]] = []
    for self_deck_name, self_deck in decks:
        other_deck_name, other_deck = decks[1] if self_deck_name == decks[0][0] else decks[0]
        for side_name, self_is_p1 in [("선공", True), ("후공", False)]:
            for relation_name, use_same_deck in [("같은 덱", True), ("다른 덱", False)]:
                opp_deck = self_deck if use_same_deck else other_deck
                if self_is_p1:
                    p1_deck, p2_deck = self_deck, opp_deck
                else:
                    p1_deck, p2_deck = opp_deck, self_deck
                scenarios.append(
                    {
                        "label": f"{prefix}/{self_deck_name}/{side_name}/{relation_name}",
                        "self_is_p1": self_is_p1,
                        "self_deck_name": self_deck_name,
                        "opp_deck_name": self_deck_name if use_same_deck else other_deck_name,
                        "side_name": side_name,
                        "relation_name": relation_name,
                        "p1_deck": p1_deck,
                        "p2_deck": p2_deck,
                    }
                )
    return scenarios


def _human_rate(n: int, d: int) -> float:
    return 0.0 if d <= 0 else 100.0 * n / d


def _format_scenario_line(result: Dict[str, Any]) -> str:
    return (
        f"- {result['label']}: self={result['self_wins']}, opp={result['opp_wins']}, d={result['draws']}, "
        f"wr={result['win_rate_percent']:.1f}%, avg_steps={float(result['avg_steps']):.1f}, "
        f"avg_turn={float(result['avg_final_turn']):.1f}"
    )


def _scenario_report_path(prefix: str, index: int, label: str) -> Path:
    safe_label = label.replace("/", "_").replace(" ", "_")
    return Path.home() / "RL_AI" / "log" / f"{prefix}_{index:02d}_{safe_label}.txt"


def _zip_bias_text_logs(run_started_wall: float) -> Path | None:
    log_dir = Path.home() / "RL_AI" / "log"
    bias_txts = sorted(
        [
            path
            for path in log_dir.glob("bias_check*.txt")
            if path.stat().st_mtime >= run_started_wall - 1.0
        ],
        key=lambda path: path.name,
    )
    if not bias_txts:
        print("[*] no new bias txt logs to zip")
        return None
    zip_path = log_dir / "bias_check_latest.zip"
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in bias_txts:
            zf.write(path, arcname=path.name)
    for path in bias_txts:
        if path.name == "bias_check_summary.txt" or path.resolve() == zip_path.resolve():
            continue
        try:
            path.unlink()
        except OSError:
            pass
    print(f"[*] bias log zip saved: {zip_path}")
    return zip_path


def _summarize_scenario_results(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    episodes = sum(int(item["matches"]) for item in results)
    self_wins = sum(int(item["self_wins"]) for item in results)
    opp_wins = sum(int(item["opp_wins"]) for item in results)
    draws = sum(int(item["draws"]) for item in results)
    weighted_steps = sum(float(item["avg_steps"]) * int(item["matches"]) for item in results)
    weighted_turns = sum(float(item["avg_final_turn"]) * int(item["matches"]) for item in results)
    action_type_counts: Counter[str] = Counter()
    card_use_counts: Counter[str] = Counter()
    for item in results:
        action_type_counts.update(item.get("action_type_counts", {}))
        card_use_counts.update(item.get("card_use_counts", {}))

    avg_steps = 0.0 if episodes <= 0 else weighted_steps / episodes
    avg_turns = 0.0 if episodes <= 0 else weighted_turns / episodes

    def _avg_where(key: str, value: str) -> float:
        rows = [item for item in results if str(item.get(key, "")) == value]
        if not rows:
            return 0.0
        return sum(float(item["win_rate_percent"]) for item in rows) / len(rows)

    return {
        "episodes": episodes,
        "self_wins": self_wins,
        "opp_wins": opp_wins,
        "draws": draws,
        "self_win_rate_percent": _human_rate(self_wins, episodes),
        "opp_win_rate_percent": _human_rate(opp_wins, episodes),
        "side_gap_percent": _human_rate(self_wins - opp_wins, episodes),
        "avg_steps": avg_steps,
        "avg_final_turn": avg_turns,
        "same_avg": _avg_where("relation_name", "같은 덱"),
        "diff_avg": _avg_where("relation_name", "다른 덱"),
        "orange_avg": _avg_where("self_deck_name", "귤"),
        "charlotte_avg": _avg_where("self_deck_name", "샤를로테"),
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "card_use_counts": dict(card_use_counts.most_common()),
    }


def _build_python_observation(snapshot: Dict[str, Any], *, canonical: bool) -> Any:
    from RL_AI.SeaEngine import observation as obs_mod

    raw_snapshot = dict(snapshot)
    raw_snapshot["state_vector"] = None
    raw_snapshot["action_feature_vectors"] = None

    player_id = raw_snapshot.get("active_player", "P1")
    if canonical:
        return obs_mod.build_observation(raw_snapshot, player_id)

    ctx = obs_mod._build_context(raw_snapshot, player_id)
    ctx = obs_mod._SnapshotContext(
        snapshot=ctx.snapshot,
        player_id=ctx.player_id,
        enemy_id=ctx.enemy_id,
        mirror_view=False,
        own_player=ctx.own_player,
        enemy_player=ctx.enemy_player,
        board=ctx.board,
        own_board=ctx.own_board,
        enemy_board=ctx.enemy_board,
        own_hand=ctx.own_hand,
        own_leader=ctx.own_leader,
        enemy_leader=ctx.enemy_leader,
        board_by_uid=ctx.board_by_uid,
        action_map=ctx.action_map,
        actions=ctx.actions,
    )
    global_vector = obs_mod._build_global_vector_ctx(ctx)
    board_vector = obs_mod._build_board_vector_ctx(ctx)
    hand_vector = obs_mod._build_hand_vector_ctx(ctx)
    state_vector = global_vector + board_vector + hand_vector
    action_feature_vectors = [obs_mod._encode_action_features_ctx(ctx, action) for action in ctx.actions]
    return obs_mod.SeaEngineObservation(
        unit_list=[],
        hand_list=[],
        global_vector=global_vector,
        legal_action_mask=[1 for _ in ctx.actions],
        state_vector=state_vector,
        action_feature_vectors=action_feature_vectors,
    )


def _make_mirrored_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    mirrored = copy.deepcopy(snapshot)

    def _swap_pid(value: Any) -> Any:
        if value == "P1":
            return "P2"
        if value == "P2":
            return "P1"
        if value == "Player1":
            return "Player2"
        if value == "Player2":
            return "Player1"
        return value

    mirrored["active_player"] = _swap_pid(mirrored.get("active_player"))
    mirrored["winner_id"] = _swap_pid(mirrored.get("winner_id"))

    for player in mirrored.get("players", []):
        player["id"] = _swap_pid(player.get("id"))

    for card in mirrored.get("board", []):
        card["owner"] = _swap_pid(card.get("owner"))
        if bool(card.get("is_placed")):
            try:
                card["pos_x"] = 5 - int(card.get("pos_x", -1))
            except Exception:
                pass

    for action in mirrored.get("actions", []):
        target = action.get("target", {})
        if str(target.get("type", "None")) == "Cell":
            try:
                target["pos_x"] = 5 - int(target.get("pos_x", -1))
            except Exception:
                pass

    mirrored["state_vector"] = None
    mirrored["action_feature_vectors"] = None
    mirrored["global_vector"] = None
    return mirrored


def _action_signature(snapshot: Dict[str, Any], action: Dict[str, Any], *, unmirror_x: bool = False) -> tuple[Any, ...]:
    active_player = str(snapshot.get("active_player", ""))
    board_by_uid = {str(card.get("uid", "")): card for card in snapshot.get("board", [])}

    def _owner_relation(card: Optional[Dict[str, Any]]) -> str:
        if card is None:
            return "none"
        return "self" if str(card.get("owner", "")) == active_player else "opp"

    def _x(value: Any) -> Any:
        try:
            x = int(value)
        except Exception:
            return value
        return 5 - x if unmirror_x else x

    def _int_or_raw(value: Any) -> Any:
        try:
            return int(value)
        except Exception:
            return value

    source_card = board_by_uid.get(str(action.get("source", "")))
    target = action.get("target", {}) or {}
    target_type = str(target.get("type", "None"))
    target_bits: tuple[Any, ...]
    if target_type == "Cell":
        target_bits = ("Cell", _x(target.get("pos_x", -1)), _int_or_raw(target.get("pos_y", -1)))
    elif target_type == "Unit":
        target_card = board_by_uid.get(str(target.get("guid", "")))
        target_bits = (
            "Unit",
            _owner_relation(target_card),
            str(target_card.get("role", "")) if target_card is not None else "",
            str(target_card.get("card_id", "")) if target_card is not None else "",
        )
    else:
        target_bits = (target_type,)

    return (
        str(action.get("effect_id", "")),
        _owner_relation(source_card),
        str(source_card.get("role", "")) if source_card is not None else "",
        str(source_card.get("card_id", "")) if source_card is not None else "",
        target_bits,
    )


def _measure_mirror_agreement(
    *,
    agent_factory: Callable[[int], Any],
    total_matches: int,
    card_data_path: Optional[str],
    max_turns: int,
    seed: Optional[int],
    label: str,
    scenario_workers: int = 1,
) -> Dict[str, Any]:
    from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession

    scenarios = _scenario_definitions(label)
    per = total_matches // len(scenarios)
    rem = total_matches % len(scenarios)
    result_rows: list[Dict[str, Any]] = []
    total_states = 0
    total_uid_agree = 0
    total_signature_agree = 0
    scenario_worker_count = max(1, int(scenario_workers or 1))

    def _run_single_scenario(idx: int, scenario: Dict[str, Any], matches: int) -> Dict[str, Any]:
        if matches <= 0:
            return {
                "index": idx,
                "label": str(scenario["label"]),
                "states": 0,
                "agreement": 0,
                "agreement_rate": 0.0,
                "uid_agreement": 0,
                "uid_agreement_rate": 0.0,
            }
        agent = agent_factory((seed or 0) + 9000 + idx)
        agent.name = f"{label}_mir"
        uid_agreement = 0
        signature_agreement = 0
        states = 0
        scenario_start = time.time()
        session = PythonNetSession(card_data_path=card_data_path)
        session.start()
        try:
            for _ in range(matches):
                snapshot = session.init_game(
                    player1_deck=str(scenario["p1_deck"]),
                    player2_deck=str(scenario["p2_deck"]),
                )
                while snapshot["result"] == "Ongoing" and snapshot["turn"] <= max_turns:
                    legal_actions = snapshot.get("actions", [])
                    if not legal_actions:
                        break
                    _, orig_action = agent.select_action(snapshot, legal_actions)
                    mirrored_snapshot = _make_mirrored_snapshot(snapshot)
                    _, mirrored_action = agent.select_action(mirrored_snapshot, mirrored_snapshot.get("actions", []))
                    if str(orig_action.get("uid", "")) == str(mirrored_action.get("uid", "")):
                        uid_agreement += 1
                    if _action_signature(snapshot, orig_action) == _action_signature(mirrored_snapshot, mirrored_action, unmirror_x=True):
                        signature_agreement += 1
                    states += 1
                    if states == 1 or states % 1000 == 0:
                        elapsed = max(1e-9, time.time() - scenario_start)
                        print(
                            f"[*] normalize_raw_agree/{label} progress: states={states} "
                            f"states/s={states / elapsed:.2f} | signature_agree={signature_agreement} | uid_agree={uid_agreement}",
                            flush=True,
                        )
                    snapshot = session.apply_action(str(orig_action.get("uid", "")))
        finally:
            session.close()
        elapsed = max(1e-9, time.time() - scenario_start)
        print(
            f"[*] normalize_raw_agree/{label} scenario done: {scenario['label']} | states/s={states / elapsed:.2f}",
            flush=True,
        )
        return {
            "index": idx,
            "label": str(scenario["label"]),
            "states": states,
            "agreement": signature_agreement,
            "agreement_rate": _human_rate(signature_agreement, states),
            "signature_agreement": signature_agreement,
            "signature_agreement_rate": _human_rate(signature_agreement, states),
            "uid_agreement": uid_agreement,
            "uid_agreement_rate": _human_rate(uid_agreement, states),
        }

    if scenario_worker_count > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=scenario_worker_count, thread_name_prefix=f"bias-mir-{label}") as executor:
            futures = []
            for idx, scenario in enumerate(scenarios):
                matches = per + (1 if idx < rem else 0)
                if matches <= 0:
                    continue
                futures.append(executor.submit(_run_single_scenario, idx, scenario, matches))
            rows = [future.result() for future in concurrent.futures.as_completed(futures)]
            rows.sort(key=lambda row: int(row["index"]))
            for row in rows:
                total_states += int(row["states"])
                total_signature_agree += int(row["signature_agreement"])
                total_uid_agree += int(row["uid_agreement"])
                result_rows.append({k: v for k, v in row.items() if k != "index"})
    else:
        for idx, scenario in enumerate(scenarios):
            matches = per + (1 if idx < rem else 0)
            if matches <= 0:
                continue
            row = _run_single_scenario(idx, scenario, matches)
            total_states += int(row["states"])
            total_signature_agree += int(row["signature_agreement"])
            total_uid_agree += int(row["uid_agreement"])
            result_rows.append({k: v for k, v in row.items() if k != "index"})

    return {
        "label": label,
        "rows": result_rows,
        "states": total_states,
        "agreement": total_signature_agree,
        "agreement_rate": _human_rate(total_signature_agree, total_states),
        "signature_agreement": total_signature_agree,
        "signature_agreement_rate": _human_rate(total_signature_agree, total_states),
        "uid_agreement": total_uid_agree,
        "uid_agreement_rate": _human_rate(total_uid_agree, total_states),
    }


def _run_same_policy_suite(
    *,
    label: str,
    agent_factory: Callable[[int], Any],
    total_matches: int,
    card_data_path: Optional[str],
    max_turns: int,
    seed: Optional[int],
    include_history: bool = False,
    history_limit: Optional[int] = None,
    start_mode: str = "normal",
    burnin_profile: str = "fixed",
    scenario_workers: int = 1,
) -> Dict[str, Any]:
    from RL_AI.training import evaluate_agents

    scenarios = _scenario_definitions(label)
    per = total_matches // len(scenarios)
    rem = total_matches % len(scenarios)
    results: list[Dict[str, Any]] = []
    scenario_worker_count = max(1, int(scenario_workers or 1))

    def _run_single_scenario(idx: int, scenario: Dict[str, Any], matches: int) -> Dict[str, Any]:
        p1_agent = agent_factory((seed or 0) + idx * 2 + 1)
        p2_agent = agent_factory((seed or 0) + idx * 2 + 2)
        p1_agent.name = f"{label}_p1"
        p2_agent.name = f"{label}_p2"

        print(f"[*] Suite {label}: {scenario['label']} | n={matches}")
        scenario_report_path = _scenario_report_path("bias_check_eval", idx + 1, str(scenario["label"]))
        progress_callback = _make_speed_progress_callback(
            task_name=f"suite/{label}/{scenario['label']}",
            total_units=matches,
            unit_label="eps/s",
            interval=max(1, matches // 2),
        )
        summary = evaluate_agents(
            p1_agent,
            p2_agent,
            num_matches=matches,
            card_data_path=card_data_path,
            player1_deck=str(scenario["p1_deck"]),
            player2_deck=str(scenario["p2_deck"]),
            max_turns=max_turns,
            report_path=str(scenario_report_path),
            include_history=include_history,
            history_limit=history_limit,
            match_context={
                "mode_label": label,
                "side_label": str(scenario["side_name"]),
                "self_deck_label": str(scenario["self_deck_name"]),
                "opp_deck_label": str(scenario["opp_deck_name"]),
                "relation_label": str(scenario["relation_name"]),
            },
            progress_callback=progress_callback,
            start_mode=start_mode,
            start_focus_player="P1" if bool(scenario["self_is_p1"]) else "P2",
            burnin_profile=burnin_profile,
        )
        p1_wins = int(summary["p1_wins"])
        p2_wins = int(summary["p2_wins"])
        draws = int(summary["draws"])
        episodes = int(summary["episodes"])
        wr = _human_rate(p1_wins, episodes)
        opp_wr = _human_rate(p2_wins, episodes)
        row = {
            "index": idx,
            "label": str(scenario["label"]),
            "side_name": str(scenario["side_name"]),
            "self_deck_name": str(scenario["self_deck_name"]),
            "opp_deck_name": str(scenario["opp_deck_name"]),
            "relation_name": str(scenario["relation_name"]),
            "matches": episodes,
            "self_wins": p1_wins if bool(scenario["self_is_p1"]) else p2_wins,
            "opp_wins": p2_wins if bool(scenario["self_is_p1"]) else p1_wins,
            "draws": draws,
            "win_rate_percent": wr if bool(scenario["self_is_p1"]) else opp_wr,
            "avg_steps": float(summary["avg_steps"]),
            "avg_final_turn": float(summary["avg_final_turn"]),
            "action_type_counts": dict(summary.get("action_type_counts", {})),
            "card_use_counts": dict(summary.get("card_use_counts", {})),
            "report_path": str(summary.get("report_path", "")),
            "history_path": None,
        }

        if include_history:
            history_path = scenario_report_path.with_name(f"{scenario_report_path.stem}_hist.txt")
            saved_history_path = _save_history_report(
                title=f"Bias Check {label} / {scenario['label']} Histories",
                summary=summary,
                report_path=history_path,
            )
            if saved_history_path is not None:
                row["history_path"] = str(saved_history_path)
        return row

    if scenario_worker_count > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=scenario_worker_count, thread_name_prefix=f"bias-suite-{label}") as executor:
            futures = []
            for idx, scenario in enumerate(scenarios):
                matches = per + (1 if idx < rem else 0)
                if matches <= 0:
                    continue
                futures.append(executor.submit(_run_single_scenario, idx, scenario, matches))
            rows = [future.result() for future in concurrent.futures.as_completed(futures)]
            rows.sort(key=lambda row: int(row["index"]))
            for row in rows:
                results.append({k: v for k, v in row.items() if k != "index"})
    else:
        for idx, scenario in enumerate(scenarios):
            matches = per + (1 if idx < rem else 0)
            if matches <= 0:
                continue
            row = _run_single_scenario(idx, scenario, matches)
            results.append({k: v for k, v in row.items() if k != "index"})

    aggregate = _summarize_scenario_results(results)
    first_avg = 0.0
    second_avg = 0.0
    first_rows = [r for r in results if str(r["side_name"]) == "선공"]
    second_rows = [r for r in results if str(r["side_name"]) == "후공"]
    if first_rows:
        first_avg = sum(float(r["win_rate_percent"]) for r in first_rows) / len(first_rows)
    if second_rows:
        second_avg = sum(float(r["win_rate_percent"]) for r in second_rows) / len(second_rows)

    same_rows = [r for r in results if str(r["relation_name"]) == "같은 덱"]
    diff_rows = [r for r in results if str(r["relation_name"]) == "다른 덱"]
    same_avg = sum(float(r["win_rate_percent"]) for r in same_rows) / len(same_rows) if same_rows else 0.0
    diff_avg = sum(float(r["win_rate_percent"]) for r in diff_rows) / len(diff_rows) if diff_rows else 0.0

    orange_rows = [r for r in results if str(r["self_deck_name"]) == "귤"]
    char_rows = [r for r in results if str(r["self_deck_name"]) == "샤를로테"]
    orange_avg = sum(float(r["win_rate_percent"]) for r in orange_rows) / len(orange_rows) if orange_rows else 0.0
    char_avg = sum(float(r["win_rate_percent"]) for r in char_rows) / len(char_rows) if char_rows else 0.0

    best = max(results, key=lambda x: float(x["win_rate_percent"]), default=None)
    worst = min(results, key=lambda x: float(x["win_rate_percent"]), default=None)

    return {
        "label": label,
        "results": results,
        "aggregate": aggregate,
        "first_avg": first_avg,
        "second_avg": second_avg,
        "side_gap": first_avg - second_avg,
        "same_avg": same_avg,
        "diff_avg": diff_avg,
        "orange_avg": orange_avg,
        "charlotte_avg": char_avg,
        "best": best,
        "worst": worst,
    }


def _run_head_to_head_suite(
    *,
    label: str,
    self_factory: Callable[[int], Any],
    opp_factory: Callable[[int], Any],
    total_matches: int,
    card_data_path: Optional[str],
    max_turns: int,
    seed: Optional[int],
    include_history: bool = False,
    history_limit: Optional[int] = None,
    scenario_workers: int = 1,
) -> Dict[str, Any]:
    from RL_AI.training import evaluate_agents

    scenarios = _scenario_definitions(label)
    per = total_matches // len(scenarios)
    rem = total_matches % len(scenarios)
    results: list[Dict[str, Any]] = []
    scenario_worker_count = max(1, int(scenario_workers or 1))

    def _run_single_scenario(idx: int, scenario: Dict[str, Any], matches: int) -> Dict[str, Any]:
        self_agent = self_factory((seed or 0) + idx * 2 + 1)
        opp_agent = opp_factory((seed or 0) + idx * 2 + 2)
        self_agent.name = f"{label}_self"
        opp_agent.name = f"{label}_opp"
        p1_agent = self_agent if bool(scenario["self_is_p1"]) else opp_agent
        p2_agent = opp_agent if bool(scenario["self_is_p1"]) else self_agent
        scenario_report_path = _scenario_report_path("bias_check_eval", idx + 1, str(scenario["label"]))
        summary = evaluate_agents(
            p1_agent,
            p2_agent,
            num_matches=matches,
            card_data_path=card_data_path,
            player1_deck=str(scenario["p1_deck"]),
            player2_deck=str(scenario["p2_deck"]),
            max_turns=max_turns,
            report_path=str(scenario_report_path),
            include_history=include_history,
            history_limit=history_limit,
            match_context={
                "mode_label": label,
                "side_label": str(scenario["side_name"]),
                "self_deck_label": str(scenario["self_deck_name"]),
                "opp_deck_label": str(scenario["opp_deck_name"]),
                "relation_label": str(scenario["relation_name"]),
            },
        )
        p1_wins = int(summary["p1_wins"])
        p2_wins = int(summary["p2_wins"])
        episodes = int(summary["episodes"])
        row = {
            "index": idx,
            "label": str(scenario["label"]),
            "side_name": str(scenario["side_name"]),
            "self_deck_name": str(scenario["self_deck_name"]),
            "opp_deck_name": str(scenario["opp_deck_name"]),
            "relation_name": str(scenario["relation_name"]),
            "matches": episodes,
            "self_wins": p1_wins if bool(scenario["self_is_p1"]) else p2_wins,
            "opp_wins": p2_wins if bool(scenario["self_is_p1"]) else p1_wins,
            "draws": int(summary["draws"]),
            "win_rate_percent": _human_rate(p1_wins if bool(scenario["self_is_p1"]) else p2_wins, episodes),
            "avg_steps": float(summary["avg_steps"]),
            "avg_final_turn": float(summary["avg_final_turn"]),
            "action_type_counts": dict(summary.get("action_type_counts", {})),
            "card_use_counts": dict(summary.get("card_use_counts", {})),
            "report_path": str(summary.get("report_path", "")),
            "history_path": None,
        }
        if include_history:
            history_path = scenario_report_path.with_name(f"{scenario_report_path.stem}_hist.txt")
            saved_history_path = _save_history_report(
                title=f"Bias Check {label} / {scenario['label']} Histories",
                summary=summary,
                report_path=history_path,
            )
            if saved_history_path is not None:
                row["history_path"] = str(saved_history_path)
        return row

    if scenario_worker_count > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=scenario_worker_count, thread_name_prefix=f"bias-h2h-{label}") as executor:
            futures = []
            for idx, scenario in enumerate(scenarios):
                matches = per + (1 if idx < rem else 0)
                if matches > 0:
                    futures.append(executor.submit(_run_single_scenario, idx, scenario, matches))
            rows = [future.result() for future in concurrent.futures.as_completed(futures)]
            rows.sort(key=lambda row: int(row["index"]))
            results.extend({k: v for k, v in row.items() if k != "index"} for row in rows)
    else:
        for idx, scenario in enumerate(scenarios):
            matches = per + (1 if idx < rem else 0)
            if matches > 0:
                row = _run_single_scenario(idx, scenario, matches)
                results.append({k: v for k, v in row.items() if k != "index"})

    aggregate = _summarize_scenario_results(results)
    first_rows = [r for r in results if str(r["side_name"]) == "선공"]
    second_rows = [r for r in results if str(r["side_name"]) == "후공"]
    same_rows = [r for r in results if str(r["relation_name"]) == "같은 덱"]
    diff_rows = [r for r in results if str(r["relation_name"]) == "다른 덱"]
    orange_rows = [r for r in results if str(r["self_deck_name"]) == "귤"]
    char_rows = [r for r in results if str(r["self_deck_name"]) == "샤를로테"]
    first_avg = sum(float(r["win_rate_percent"]) for r in first_rows) / len(first_rows) if first_rows else 0.0
    second_avg = sum(float(r["win_rate_percent"]) for r in second_rows) / len(second_rows) if second_rows else 0.0
    return {
        "label": label,
        "results": results,
        "aggregate": aggregate,
        "first_avg": first_avg,
        "second_avg": second_avg,
        "side_gap": first_avg - second_avg,
        "same_avg": sum(float(r["win_rate_percent"]) for r in same_rows) / len(same_rows) if same_rows else 0.0,
        "diff_avg": sum(float(r["win_rate_percent"]) for r in diff_rows) / len(diff_rows) if diff_rows else 0.0,
        "orange_avg": sum(float(r["win_rate_percent"]) for r in orange_rows) / len(orange_rows) if orange_rows else 0.0,
        "charlotte_avg": sum(float(r["win_rate_percent"]) for r in char_rows) / len(char_rows) if char_rows else 0.0,
        "best": max(results, key=lambda x: float(x["win_rate_percent"]), default=None),
        "worst": min(results, key=lambda x: float(x["win_rate_percent"]), default=None),
    }


def _format_suite_report(title: str, suite: Dict[str, Any]) -> str:
    aggregate = suite["aggregate"]
    lines = [
        f"=== {title} ===",
        f"label={suite['label']}",
        f"episodes={aggregate['episodes']}",
        f"self_wins={aggregate['self_wins']}",
        f"opp_wins={aggregate['opp_wins']}",
        f"draws={aggregate['draws']}",
        f"self_win_rate_percent={aggregate['self_win_rate_percent']:.2f}",
        f"opp_win_rate_percent={aggregate['opp_win_rate_percent']:.2f}",
        f"side_gap_percent={aggregate['side_gap_percent']:.2f}",
        f"avg_steps={aggregate['avg_steps']:.2f}",
        f"avg_final_turn={aggregate['avg_final_turn']:.2f}",
        f"same_avg={aggregate['same_avg']:.2f}",
        f"diff_avg={aggregate['diff_avg']:.2f}",
        f"orange_avg={aggregate['orange_avg']:.2f}",
        f"charlotte_avg={aggregate['charlotte_avg']:.2f}",
        f"first_avg={suite['first_avg']:.2f}",
        f"second_avg={suite['second_avg']:.2f}",
        "",
    ]
    for row in suite["results"]:
        history_path = row.get("history_path")
        lines.append(
            f"- {row['label']}: self={row['self_wins']}, opp={row['opp_wins']}, d={row['draws']}, "
            f"wr={float(row['win_rate_percent']):.1f}%, avg_steps={float(row['avg_steps']):.1f}, "
            f"avg_turn={float(row['avg_final_turn']):.1f}"
            + (f", history={history_path}" if history_path else "")
        )
    if suite.get("best") is not None:
        best = suite["best"]
        lines.append("")
        lines.append(f"best={best['label']} ({float(best['win_rate_percent']):.1f}%)")
    if suite.get("worst") is not None:
        worst = suite["worst"]
        lines.append(f"worst={worst['label']} ({float(worst['win_rate_percent']):.1f}%)")
    return "\n".join(lines)


def _save_history_report(
    *,
    title: str,
    summary: Dict[str, Any],
    report_path: Path,
) -> Optional[Path]:
    from RL_AI.analysis.reports import build_win_rate_report, save_report
    from RL_AI.training.experiment import _format_match_history

    histories = list(summary.get("histories", []))
    if not histories:
        return None
    lines = [
        f"=== {title} ===",
        f"report={summary.get('report_path', '')}",
        "",
        build_win_rate_report(summary),
        "",
    ]
    for match_history in histories:
        lines.append(_format_match_history(match_history))
        lines.append("")
    return save_report("\n".join(lines).rstrip() + "\n", report_path)


def _make_rl_agent_factory(
    *,
    state_dict: Dict[str, Any],
    observation_mode: str,
    device: str,
    hidden_dim: Optional[int] = None,
    use_belief_mcts: bool = True,
) -> Callable[[int], Any]:
    from RL_AI.agents import (
        SeaEngineBeliefMCTSAgent,
        SeaEngineRLAgent,
        infer_hidden_dim_from_state_dict,
        load_state_dict_flexible,
    )
    from RL_AI.SeaEngine.observation import STATE_VECTOR_DIM
    resolved_hidden_dim = infer_hidden_dim_from_state_dict(state_dict, fallback=hidden_dim)

    def _factory(seed: int) -> Any:
        agent = SeaEngineRLAgent(
            hidden_dim=resolved_hidden_dim,
            sample_actions=False,
            device=device,
            seed=seed,
        )
        agent.ensure_model(state_dim=STATE_VECTOR_DIM)
        assert agent.model is not None
        load_state_dict_flexible(agent.model, state_dict)
        agent.model.eval()
        agent.name = f"rl_{observation_mode}"
        belief_agent = SeaEngineBeliefMCTSAgent.from_env(agent, seed=seed) if use_belief_mcts else None
        return _BiasCheckRLAgentWrapper(agent, observation_mode=observation_mode, belief_agent=belief_agent)

    return _factory


class _BiasCheckRLAgentWrapper:
    def __init__(self, agent: Any, observation_mode: str, belief_agent: Any = None) -> None:
        self._agent = agent
        self._belief_agent = belief_agent
        self.observation_mode = observation_mode
        suffix = "_belief_mcts" if belief_agent is not None else ""
        self.name = f"{getattr(agent, 'name', 'rl')}{suffix}"

    @property
    def device(self):
        return self._agent.device

    def sampling_mode(self, enabled: bool):
        return self._agent.sampling_mode(enabled)

    def select_action(self, snapshot: Dict[str, Any], legal_actions: Sequence[Dict[str, Any]]):
        if self.observation_mode == "auto":
            if self._belief_agent is not None:
                return self._belief_agent.select_action(snapshot, legal_actions)
            return self._agent.select_action(snapshot, legal_actions)
        if self.observation_mode == "python_canonical":
            obs = _build_python_observation(snapshot, canonical=True)
        elif self.observation_mode == "python_raw":
            obs = _build_python_observation(snapshot, canonical=False)
        else:
            obs = _build_python_observation(snapshot, canonical=True)

        if self._belief_agent is not None:
            search_snapshot = dict(snapshot)
            search_snapshot["global_vector"] = obs.global_vector
            search_snapshot["state_vector"] = obs.state_vector
            search_snapshot["action_feature_vectors"] = obs.action_feature_vectors
            return self._belief_agent.select_action(search_snapshot, legal_actions)

        import torch
        from torch.distributions import Categorical

        with torch.no_grad():
            logits_tensor, value_tensor = self._agent.forward_tensors(obs.state_vector, obs.action_feature_vectors)

        dist = Categorical(logits=logits_tensor)
        chosen_index = int(torch.argmax(logits_tensor).item())
        if self._agent.sample_actions:
            chosen_index = int(dist.sample().item())
        output = type(self._agent).compute_policy_output  # unused, keep mypy calm
        del output
        action = legal_actions[chosen_index]
        return chosen_index, action


def _make_basic_agent_factory(kind: str, *, device: str, seed_base: int = 0) -> Callable[[int], Any]:
    from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRandomAgent, SeaEngineRuleBasedAgent

    kind = kind.lower().strip()

    def _factory(seed: int) -> Any:
        if kind == "random":
            return SeaEngineRandomAgent(seed=seed_base + seed)
        if kind == "greedy":
            return SeaEngineGreedyAgent(seed=seed_base + seed)
        if kind in {"rule", "rule_based", "rule-based"}:
            return SeaEngineRuleBasedAgent(seed=seed_base + seed)
        raise ValueError(f"Unsupported basic agent kind: {kind}")

    return _factory


def _make_speed_progress_callback(
    *,
    task_name: str,
    total_units: int,
    unit_label: str = "eps/s",
    interval: int = 50,
) -> Callable[[int, int, str, str], None]:
    start = time.time()

    def _callback(current: int, total: int, result: str, matchup: str) -> None:
        should_print = current == 1 or current >= total or current % max(1, interval) == 0
        if not should_print:
            return
        elapsed = max(1e-9, time.time() - start)
        speed = current / elapsed
        print(
            f"[*] {task_name} progress: {current}/{total_units or total} {unit_label}={speed:.2f} | "
            f"last={result} | matchup={matchup}",
            flush=True,
        )

    return _callback


def _default_scenario_workers() -> int:
    return max(1, min(8, os.cpu_count() or 1))


def _resolve_checkpoint_paths(extracted_paths: Sequence[Path], checkpoint_limit: int) -> list[Path]:
    checkpoints = sorted(
        [p for p in extracted_paths if p.is_file() and p.name.startswith("model_ep_") and p.suffix == ".pt"],
        key=_episode_from_name,
    )
    selected_episodes = {2000, 4000, 6000, 8000, 10000}
    checkpoints = [p for p in checkpoints if _episode_from_name(p) in selected_episodes]
    if checkpoint_limit > 0:
        checkpoints = checkpoints[:checkpoint_limit]
    return checkpoints


def _process_pool_context():
    # CUDA-backed PyTorch objects do not survive fork safely.
    # Use spawn everywhere so worker processes initialize cleanly.
    return mp.get_context("spawn")


def _worker_bootstrap() -> None:
    _ensure_python_deps()
    _configure_runtime_env()
    for module_name in list(sys.modules):
        if module_name == "RL_AI" or module_name.startswith("RL_AI."):
            del sys.modules[module_name]
    importlib.invalidate_caches()


def _run_bias_task(task: Dict[str, Any]) -> Dict[str, Any]:
    _worker_bootstrap()

    from RL_AI.training import evaluate_agents

    task_kind = str(task["kind"])
    task_name = str(task["task_name"])
    label = str(task["label"])
    device = str(task["device"])
    seed = int(task["seed"])
    card_data_path = task.get("card_data_path")
    max_turns = int(task.get("max_turns", 100))
    use_belief_mcts = bool(task.get("use_belief_mcts", False))

    print(f"[*] task start: {task_name} ({task_kind})")

    if task_kind == "same_policy":
        total_matches = int(task["total_matches"])
        include_history = bool(task.get("include_history", False))
        history_limit = task.get("history_limit")
        history_limit = None if history_limit is None else int(history_limit)
        scenario_workers = int(task.get("scenario_workers", 1))
        agent_kind = str(task["agent_kind"])
        if agent_kind in {"random", "greedy", "rule_based", "rule", "rule-based"}:
            agent_factory = _make_basic_agent_factory(agent_kind, device=device)
        elif agent_kind == "rl":
            model_path = Path(task["model_path"])
            observation_mode = str(task.get("observation_mode", "python_canonical"))
            state_dict = _load_state_dict(model_path)
            agent_factory = _make_rl_agent_factory(
                state_dict=state_dict,
                observation_mode=observation_mode,
                device=device,
                use_belief_mcts=use_belief_mcts,
            )
        else:
            raise ValueError(f"Unsupported agent_kind for same_policy task: {agent_kind}")

        result = _run_same_policy_suite(
            label=label,
            agent_factory=agent_factory,
            total_matches=total_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            seed=seed,
            include_history=include_history,
            history_limit=history_limit,
            start_mode=str(task.get("start_mode", "normal")),
            burnin_profile=str(task.get("burnin_profile", "fixed")),
            scenario_workers=scenario_workers,
        )
        return {
            "task_name": task_name,
            "task_kind": task_kind,
            "result": result,
        }

    if task_kind == "mirror":
        total_matches = int(task["total_matches"])
        observation_mode = str(task.get("observation_mode", "python_canonical"))
        scenario_workers = int(task.get("scenario_workers", 1))
        model_path = Path(task["model_path"])
        state_dict = _load_state_dict(model_path)
        agent_factory = _make_rl_agent_factory(
            state_dict=state_dict,
            observation_mode=observation_mode,
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        result = _measure_mirror_agreement(
            agent_factory=agent_factory,
            total_matches=total_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            seed=seed,
            label=label,
            scenario_workers=scenario_workers,
        )
        return {
            "task_name": task_name,
            "task_kind": task_kind,
            "result": result,
        }

    if task_kind == "checkpoint":
        total_matches = int(task["total_matches"])
        include_history = bool(task.get("include_history", True))
        history_limit = task.get("history_limit")
        history_limit = None if history_limit is None else int(history_limit)
        scenario_workers = int(task.get("scenario_workers", 1))
        model_path = Path(task["model_path"])
        state_dict = _load_state_dict(model_path)
        agent_factory = _make_rl_agent_factory(
            state_dict=state_dict,
            observation_mode="python_canonical",
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        result = _run_same_policy_suite(
            label=label,
            agent_factory=agent_factory,
            total_matches=total_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            seed=seed,
            include_history=include_history,
            history_limit=history_limit,
            scenario_workers=scenario_workers,
        )
        return {
            "task_name": task_name,
            "task_kind": task_kind,
            "result": result,
        }

    if task_kind == "head_to_head":
        total_matches = int(task["total_matches"])
        include_history = bool(task.get("include_history", False))
        history_limit = task.get("history_limit")
        history_limit = None if history_limit is None else int(history_limit)
        scenario_workers = int(task.get("scenario_workers", 1))
        self_state = _load_state_dict(Path(task["self_model_path"]))
        opp_state = _load_state_dict(Path(task["opp_model_path"]))
        self_factory = _make_rl_agent_factory(
            state_dict=self_state,
            observation_mode=str(task.get("self_observation_mode", "python_canonical")),
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        opp_factory = _make_rl_agent_factory(
            state_dict=opp_state,
            observation_mode=str(task.get("opp_observation_mode", "python_canonical")),
            device=device,
            use_belief_mcts=use_belief_mcts,
        )
        result = _run_head_to_head_suite(
            label=label,
            self_factory=self_factory,
            opp_factory=opp_factory,
            total_matches=total_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            seed=seed,
            include_history=include_history,
            history_limit=history_limit,
            scenario_workers=scenario_workers,
        )
        return {
            "task_name": task_name,
            "task_kind": task_kind,
            "result": result,
        }

    raise ValueError(f"Unsupported task kind: {task_kind}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SeaEngine bias / symmetry checks")
    parser.add_argument("--model-path", type=str, default="", help="Saved model .pt or .zip; defaults to latest model archive")
    parser.add_argument("--compare-model-path", type=str, default="", help="Optional second full-run model .pt/.zip for model-vs-model bias comparison")
    parser.add_argument("--total-matches", type=int, default=400, help="Total matches per same-policy suite (across 8 combos)")
    parser.add_argument("--comeback-matches", type=int, default=200, help="Total matches for comeback deficit suites (greedy/rule-based/self, across 8 combos)")
    parser.add_argument("--ablation-matches", type=int, default=400, help="Total matches for normalized vs raw performance suite")
    parser.add_argument("--mirror-matches", type=int, default=400, help="Total matches for normalized-raw agreement measurement")
    parser.add_argument("--checkpoint-matches", type=int, default=400, help="Total matches per checkpoint side-gap suite")
    parser.add_argument("--checkpoint-limit", type=int, default=0, help="Limit number of checkpoint files (0 = all)")
    parser.add_argument("--parallel-workers", type=int, default=0, help="Number of process workers for bias suites (0 = auto)")
    parser.add_argument("--scenario-workers", type=int, default=0, help="Number of scenario workers inside each suite (0 = auto)")
    parser.add_argument("--no-history", action="store_true", help="Skip representative history reports for faster large bias sweeps")
    parser.add_argument("--history-limit", type=int, default=0, help="Representative histories per scenario (0 = auto, negative = none)")
    parser.add_argument(
        "--use-belief-mcts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Evaluate RL suites through the shallow belief-MCTS wrapper",
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--skip-unzip", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--log-file", type=str, default="")
    args = parser.parse_args()

    home = Path.home()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_started_wall = time.time()
    default_log = home / "bias_check.log"
    log_file = Path(args.log_file) if args.log_file else default_log
    _setup_logger(log_file)

    dotnet_cmd = _ensure_dotnet()
    _ensure_python_deps()
    if not args.skip_unzip:
        _prepare_project_dir()

    print("[*] bias_check.py launched")
    print(f"[*] pid={os.getpid()}")
    print(
        f"[*] args: model_path={args.model_path or '<latest>'}, compare_model_path={args.compare_model_path or '<none>'}, total_matches={args.total_matches}, comeback_matches={args.comeback_matches}, "
        f"ablation_matches={args.ablation_matches}, mirror_matches={args.mirror_matches}, "
        f"checkpoint_matches={args.checkpoint_matches}, checkpoint_limit={args.checkpoint_limit}, "
        f"parallel_workers={args.parallel_workers}, scenario_workers={args.scenario_workers}, seed={args.seed}, device={args.device}, "
        f"model_hidden_dim={os.environ.get('SEAENGINE_MODEL_HIDDEN_DIM', '192')}, "
        f"belief_mcts_sims={os.environ.get('SEAENGINE_BELIEF_MCTS_SIMS', '2')}, "
        f"belief_mcts_top_k={os.environ.get('SEAENGINE_BELIEF_MCTS_TOP_K', '3')}, "
        f"belief_mcts_rollout_steps={os.environ.get('SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS', '2')}, "
        f"use_belief_mcts={args.use_belief_mcts}, belief_mcts_mode={os.environ.get('SEAENGINE_BELIEF_MCTS_MODE', 'restore')}, "
        f"include_history={not args.no_history and args.history_limit >= 0}, history_limit={args.history_limit}, "
        f"skip_unzip={args.skip_unzip}, skip_build={args.skip_build}"
    )

    if not args.skip_build:
        _build_csharp(dotnet_cmd)

    dotnet_cmd = _configure_runtime_env()
    for module_name in list(sys.modules):
        if module_name == "RL_AI" or module_name.startswith("RL_AI."):
            del sys.modules[module_name]
    importlib.invalidate_caches()

    from RL_AI.training import trainer as seaengine_trainer_module
    from RL_AI.SeaEngine import observation as observation_module
    from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRandomAgent
    from RL_AI.analysis.reports import save_report

    print(f"trainer source: {seaengine_trainer_module.__file__}")
    print(f"observation source: {observation_module.__file__}")

    model_source = _resolve_model_source(args.model_path or None)
    compare_model_source = _resolve_model_source(args.compare_model_path) if args.compare_model_path else None
    temp_dir_mgr: Optional[tempfile.TemporaryDirectory[str]] = None
    compare_temp_dir_mgr: Optional[tempfile.TemporaryDirectory[str]] = None
    extracted_checkpoints: list[Path] = []
    compare_model_path: Optional[Path] = None
    current_model_path: Path
    try:
        if model_source.suffix.lower() == ".zip":
            temp_dir_mgr = tempfile.TemporaryDirectory(prefix="rl_ai_bias_check_")
            extract_root = Path(temp_dir_mgr.name)
            extracted = _extract_model_archive(model_source, extract_root)
            extracted_checkpoints = _resolve_checkpoint_paths(extracted, args.checkpoint_limit)
            if not extracted_checkpoints:
                raise FileNotFoundError(f"No model_ep_*.pt found inside {model_source}")
            current_model_path = extracted_checkpoints[-1]
        else:
            current_model_path = model_source
            extracted_checkpoints = [model_source]

        if compare_model_source is not None:
            if compare_model_source.suffix.lower() == ".zip":
                compare_temp_dir_mgr = tempfile.TemporaryDirectory(prefix="rl_ai_bias_compare_")
                compare_extract_root = Path(compare_temp_dir_mgr.name)
                compare_extracted = _extract_model_archive(compare_model_source, compare_extract_root)
                compare_checkpoints = _resolve_checkpoint_paths(compare_extracted, 0)
                compare_model_path = compare_checkpoints[-1] if compare_checkpoints else compare_extracted[-1]
            else:
                compare_model_path = compare_model_source

        print(f"[*] model source: {model_source}")
        print(f"[*] current model: {current_model_path}")
        if compare_model_path is not None:
            print(f"[*] compare model source: {compare_model_source}")
            print(f"[*] compare model: {compare_model_path}")
        print(f"[*] checkpoint files: {len(extracted_checkpoints)}")
        if extracted_checkpoints:
            print(f"[*] checkpoints first/last: {extracted_checkpoints[0].name} / {extracted_checkpoints[-1].name}")

        device = _resolve_device(args.device)
        parallel_workers = args.parallel_workers if args.parallel_workers > 0 else (2 if device == "cuda" else 4)
        parallel_workers = max(1, min(parallel_workers, 8))
        scenario_workers = args.scenario_workers if args.scenario_workers > 0 else _default_scenario_workers()
        scenario_workers = max(1, min(scenario_workers, 8))
        include_histories = (not args.no_history) and args.history_limit >= 0
        history_limit = None if args.history_limit == 0 else max(0, args.history_limit)
        print(f"[*] resolved parallel_workers={parallel_workers} | scenario_workers={scenario_workers}")

        task_specs: list[Dict[str, Any]] = [
            {
                "task_name": "random_random",
                "kind": "same_policy",
                "label": "random",
                "agent_kind": "random",
                "total_matches": args.total_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "greedy_greedy",
                "kind": "same_policy",
                "label": "greedy",
                "agent_kind": "greedy",
                "total_matches": args.total_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 100,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "rule_based_rule_based",
                "kind": "same_policy",
                "label": "rule_based",
                "agent_kind": "rule_based",
                "total_matches": args.total_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 150,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "rl_family",
                "kind": "same_policy",
                "label": "rl",
                "agent_kind": "rl",
                "observation_mode": "python_canonical",
                "model_path": str(current_model_path),
                "total_matches": args.total_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 200,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "random_slight_deficit",
                "kind": "same_policy",
                "label": "random_slight",
                "agent_kind": "random",
                "start_mode": "slight",
                "burnin_profile": "mixed",
                "total_matches": args.total_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 210,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "random_heavy_deficit",
                "kind": "same_policy",
                "label": "random_heavy",
                "agent_kind": "random",
                "start_mode": "heavy",
                "burnin_profile": "mixed",
                "total_matches": args.total_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 220,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "greedy_slight_deficit",
                "kind": "same_policy",
                "label": "greedy_slight",
                "agent_kind": "greedy",
                "start_mode": "slight",
                "burnin_profile": "mixed",
                "total_matches": args.comeback_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 310,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "greedy_heavy_deficit",
                "kind": "same_policy",
                "label": "greedy_heavy",
                "agent_kind": "greedy",
                "start_mode": "heavy",
                "burnin_profile": "mixed",
                "total_matches": args.comeback_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 320,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "rule_based_slight_deficit",
                "kind": "same_policy",
                "label": "rule_based_slight",
                "agent_kind": "rule_based",
                "start_mode": "slight",
                "burnin_profile": "mixed",
                "total_matches": args.comeback_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 330,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "rule_based_heavy_deficit",
                "kind": "same_policy",
                "label": "rule_based_heavy",
                "agent_kind": "rule_based",
                "start_mode": "heavy",
                "burnin_profile": "mixed",
                "total_matches": args.comeback_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 340,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
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
                "total_matches": args.comeback_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 410,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "rl_heavy_deficit",
                "kind": "same_policy",
                "label": "rl_heavy",
                "agent_kind": "rl",
                "observation_mode": "python_canonical",
                "start_mode": "heavy",
                "burnin_profile": "mixed",
                "model_path": str(current_model_path),
                "total_matches": args.comeback_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 420,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": True,
            },
            {
                "task_name": "normalized_vs_raw_canonical",
                "kind": "same_policy",
                "label": "normalize_canonical",
                "agent_kind": "rl",
                "observation_mode": "python_canonical",
                "model_path": str(current_model_path),
                "total_matches": args.ablation_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 101,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "normalized_vs_raw_raw",
                "kind": "same_policy",
                "label": "normalize_raw",
                "agent_kind": "rl",
                "observation_mode": "python_raw",
                "model_path": str(current_model_path),
                "total_matches": args.ablation_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 202,
                "device": device,
                "scenario_workers": scenario_workers,
                "include_history": False,
            },
            {
                "task_name": "normalize_raw_agree_canonical",
                "kind": "mirror",
                "label": "normalize_canonical",
                "observation_mode": "python_canonical",
                "model_path": str(current_model_path),
                "total_matches": args.mirror_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 303,
                "device": device,
                "scenario_workers": scenario_workers,
            },
            {
                "task_name": "normalize_raw_agree_raw",
                "kind": "mirror",
                "label": "normalize_raw",
                "observation_mode": "python_raw",
                "model_path": str(current_model_path),
                "total_matches": args.mirror_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 404,
                "device": device,
                "scenario_workers": scenario_workers,
            },
        ]

        if extracted_checkpoints:
            print("[*] Running checkpoint side-gap sweep...")
        for ckpt_idx, ckpt_path in enumerate(extracted_checkpoints):
            task_specs.append(
                {
                    "task_name": f"ckpt_{_episode_from_name(ckpt_path)}",
                    "kind": "checkpoint",
                    "label": f"ckpt_{_episode_from_name(ckpt_path)}",
                    "model_path": str(ckpt_path),
                    "total_matches": args.checkpoint_matches,
                    "card_data_path": None,
                    "max_turns": 100,
                    "seed": args.seed + 5000 + ckpt_idx,
                    "device": device,
                    "scenario_workers": scenario_workers,
                    "episode": _episode_from_name(ckpt_path),
                    "checkpoint_path": str(ckpt_path),
                    "include_history": True,
                }
            )

        if compare_model_path is not None:
            task_specs.append(
                {
                    "task_name": "model_a_vs_model_b",
                    "kind": "head_to_head",
                    "label": "model_a_vs_model_b",
                    "self_model_path": str(current_model_path),
                    "opp_model_path": str(compare_model_path),
                    "total_matches": args.total_matches,
                    "card_data_path": None,
                    "max_turns": 100,
                    "seed": args.seed + 7000,
                    "device": device,
                    "scenario_workers": scenario_workers,
                    "include_history": True,
                }
            )

        for task in task_specs:
            if str(task.get("agent_kind")) == "rl" or str(task.get("kind")) in {"mirror", "checkpoint", "head_to_head"}:
                task["use_belief_mcts"] = bool(args.use_belief_mcts)
            if str(task.get("kind")) in {"same_policy", "checkpoint", "head_to_head"}:
                task["history_limit"] = history_limit
                if bool(task.get("include_history", False)):
                    task["include_history"] = include_histories

        print(f"[*] Parallel bias tasks: total={len(task_specs)} | workers={parallel_workers} | mode=process_pool_spawn")
        task_results: Dict[str, Dict[str, Any]] = {}
        with concurrent.futures.ProcessPoolExecutor(max_workers=parallel_workers, mp_context=_process_pool_context()) as executor:
            future_map = {executor.submit(_run_bias_task, task): task for task in task_specs}
            for future in concurrent.futures.as_completed(future_map):
                task = future_map[future]
                task_name = str(task["task_name"])
                try:
                    payload = future.result()
                except Exception as exc:
                    print(f"[!] task failed: {task_name}")
                    raise
                task_results[task_name] = payload["result"]
                print(f"[*] task done: {task_name}")

        family_runs: list[Tuple[str, Dict[str, Any]]] = [
            ("random/random", task_results["random_random"]),
            ("greedy/greedy", task_results["greedy_greedy"]),
            ("rule-based/rule-based", task_results["rule_based_rule_based"]),
            ("RL/RL", task_results["rl_family"]),
        ]
        weak_start_runs: list[Tuple[str, Dict[str, Any]]] = [
            ("random/slight deficit", task_results["random_slight_deficit"]),
            ("random/heavy deficit", task_results["random_heavy_deficit"]),
            ("greedy/slight deficit", task_results["greedy_slight_deficit"]),
            ("greedy/heavy deficit", task_results["greedy_heavy_deficit"]),
            ("rule-based/slight deficit", task_results["rule_based_slight_deficit"]),
            ("rule-based/heavy deficit", task_results["rule_based_heavy_deficit"]),
            ("RL/slight deficit", task_results["rl_slight_deficit"]),
            ("RL/heavy deficit", task_results["rl_heavy_deficit"]),
        ]
        normalized_vs_raw_canonical = task_results["normalized_vs_raw_canonical"]
        normalized_vs_raw_raw = task_results["normalized_vs_raw_raw"]
        normalize_raw_agree_canonical = task_results["normalize_raw_agree_canonical"]
        normalize_raw_agree_raw = task_results["normalize_raw_agree_raw"]

        checkpoint_rows: list[Dict[str, Any]] = []
        for task in task_specs:
            if str(task["kind"]) != "checkpoint":
                continue
            suite = task_results[str(task["task_name"])]
            checkpoint_rows.append(
                {
                    "path": str(task["checkpoint_path"]),
                    "episode": int(task["episode"]),
                    "suite": suite,
                }
            )
            agg = suite["aggregate"]
            history_count = sum(1 for row in suite.get("results", []) if row.get("history_path"))
            print(
                f"[*] checkpoint {Path(str(task['checkpoint_path'])).name}: self_wr={agg['self_win_rate_percent']:.1f}% | "
                f"side_gap={agg['side_gap_percent']:.1f}pp | avg_steps={agg['avg_steps']:.1f} | "
                f"history_files={history_count}"
            )

        report_lines = [
            "=== SeaEngine Bias Check ===",
            f"model_source={model_source}",
            f"current_model={current_model_path}",
            f"seed={args.seed}",
            f"device={device}",
            "",
            "NOTE: RL suites below rebuild Python observations so normalized/raw view can be isolated cleanly.",
            "",
            "=== Family Comparisons ===",
        ]
        for title, suite in family_runs:
            report_lines.append(_format_suite_report(title, suite))
            report_lines.append("")

        report_lines.extend(
            [
                "=== Weak Start Scenarios ===",
                "",
            ]
        )
        for title, suite in weak_start_runs:
            report_lines.append(_format_suite_report(title, suite))
            report_lines.append("")

        report_lines.extend(
            [
                "=== 정규화 vs raw 성능 비교 ===",
                _format_suite_report("normalize canonical", normalized_vs_raw_canonical),
                "",
                _format_suite_report("normalize raw", normalized_vs_raw_raw),
                "",
                "=== 정규화-raw 일치율 ===",
                f"canonical: states={normalize_raw_agree_canonical['states']}, agree={normalize_raw_agree_canonical['agreement']}, "
                f"agreement_rate={normalize_raw_agree_canonical['agreement_rate']:.2f}%, "
                f"uid_agreement_rate={normalize_raw_agree_canonical.get('uid_agreement_rate', 0.0):.2f}%",
                f"raw: states={normalize_raw_agree_raw['states']}, agree={normalize_raw_agree_raw['agreement']}, "
                f"agreement_rate={normalize_raw_agree_raw['agreement_rate']:.2f}%, "
                f"uid_agreement_rate={normalize_raw_agree_raw.get('uid_agreement_rate', 0.0):.2f}%",
                "",
                "=== Checkpoint Side Gap ===",
            ]
        )
        for row in checkpoint_rows:
            agg = row["suite"]["aggregate"]
            history_count = sum(1 for r in row["suite"].get("results", []) if r.get("history_path"))
            report_lines.append(
                f"- ep {row['episode']:>5}: self_wr={agg['self_win_rate_percent']:.2f}%, "
                f"opp_wr={agg['opp_win_rate_percent']:.2f}%, side_gap={agg['side_gap_percent']:.2f}pp, "
                f"avg_steps={agg['avg_steps']:.2f}, avg_turn={agg['avg_final_turn']:.2f}, "
                f"path={row['path']}, history_files={history_count}"
            )

        if compare_model_path is not None and "model_a_vs_model_b" in task_results:
            report_lines.extend(
                [
                    "",
                    "=== Full-Run Model A vs Model B ===",
                    f"model_a={current_model_path}",
                    f"model_b={compare_model_path}",
                    _format_suite_report("model_a_vs_model_b", task_results["model_a_vs_model_b"]),
                ]
            )

        summary_alias = Path.home() / "RL_AI" / "log" / "bias_check_summary.txt"
        report_text = "\n".join(report_lines).rstrip() + "\n"
        report_path = save_report(report_text, summary_alias)
        zip_path = _zip_bias_text_logs(run_started_wall)

        print(f"[*] bias report saved: {report_path}")
        print(f"[*] bias summary alias: {summary_alias}")
        if zip_path is not None:
            print(f"[*] bias log archive: {zip_path}")
        print(report_text)
        print("[*] bias_check.py finished successfully")
        return 0
    finally:
        if temp_dir_mgr is not None:
            temp_dir_mgr.cleanup()
        if compare_temp_dir_mgr is not None:
            compare_temp_dir_mgr.cleanup()


if __name__ == "__main__":
    _script_started_at = time.perf_counter()
    try:
        _exit_code = main()
        print(f"[*] bias_check.py total runtime: {_format_elapsed(time.perf_counter() - _script_started_at)}")
        raise SystemExit(_exit_code)
    except Exception as exc:
        print("[!] bias_check.py failed")
        print(f"[!] error: {exc}")
        print(traceback.format_exc())
        print(f"[*] bias_check.py total runtime: {_format_elapsed(time.perf_counter() - _script_started_at)}")
        raise SystemExit(1) from exc
