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
import json
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
    print(f"[*] script start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def _format_elapsed(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours, remainder = divmod(int(seconds), 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d} ({seconds:.1f}s)"


def _parallel_opt_config_path() -> Path:
    return Path.home() / ".seaengine_parallel_opt.json"


def _load_parallel_opt_section(section: str) -> dict[str, str]:
    path = _parallel_opt_config_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    selected = payload.get("selected_env", {}) if isinstance(payload, dict) else {}
    if not isinstance(selected, dict):
        return {}
    section_data = selected.get(section, {})
    if not isinstance(section_data, dict):
        return {}
    resolved: dict[str, str] = {}
    for key, value in section_data.items():
        if not isinstance(key, str):
            continue
        if value is None:
            continue
        resolved[key] = str(value)
    return resolved


def _apply_parallel_opt_env(section: str) -> None:
    for key, value in _load_parallel_opt_section(section).items():
        os.environ.setdefault(key, value)


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


def _dotnet_root_from_cmd(dotnet_cmd: str) -> str:
    try:
        info = subprocess.run([dotnet_cmd, "--info"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        for line in (info.stdout or "").splitlines():
            if "Base Path:" in line:
                base_path = line.split("Base Path:", 1)[1].strip()
                base_dir = Path(base_path).resolve().parents[1]
                return str(base_dir)
    except Exception:
        pass
    cmd_path = Path(dotnet_cmd).resolve()
    if cmd_path.parent.name == "bin" and cmd_path.parent.parent.name:
        return str(cmd_path.parent.parent)
    return str(cmd_path.parent)


def _dotnet_executable(root: Path) -> Path:
    return root / ("dotnet.exe" if os.name == "nt" else "dotnet")


def _dotnet_required_sdk_major() -> int:
    raw = os.getenv("SEAENGINE_DOTNET_SDK_MAJOR", "10").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 10


def _dotnet_has_required_sdk(dotnet_cmd: str) -> bool:
    required = _dotnet_required_sdk_major()
    if required <= 0:
        return True
    try:
        info = subprocess.run(
            [dotnet_cmd, "--list-sdks"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, OSError):
        return False
    prefix = f"{required}."
    return any(line.strip().startswith(prefix) for line in (info.stdout or "").splitlines())


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
        info = subprocess.run([dotnet_cmd, "--info"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        first_line = next((line.strip() for line in (info.stdout or "").splitlines() if line.strip().startswith("Version:")), "")
        if not _dotnet_has_required_sdk(dotnet_cmd):
            print(f"[!] dotnet found but missing .NET {_dotnet_required_sdk_major()} SDK: {dotnet_cmd}")
            return False
        _set_dotnet_env(dotnet_cmd)
        print(f"dotnet ok: {dotnet_cmd}" + (f" ({first_line})" if first_line else ""))
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, OSError):
        return False


def _install_home_dotnet() -> str:
    home_dotnet = Path.home() / ".dotnet"
    dotnet_cmd = _dotnet_executable(home_dotnet)
    home_dotnet.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        install_script = home_dotnet / "dotnet-install.ps1"
        if not install_script.exists():
            print("[*] installing dotnet SDK to ~/.dotnet via dotnet-install.ps1...")
            download_command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"Invoke-WebRequest -Uri 'https://dot.net/v1/dotnet-install.ps1' -OutFile '{install_script}'",
            ]
            completed = subprocess.run(
                download_command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.stdout:
                print(completed.stdout)
            if completed.stderr:
                print(completed.stderr)

        if not install_script.exists():
            print("[!] dotnet-install.ps1 download failed; ~/.dotnet install unavailable.")
            return ""

        install_commands = [
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(install_script), "-Version", "10.0.107", "-InstallDir", str(home_dotnet), "-NoPath"],
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(install_script), "-Channel", "10.0", "-Quality", "GA", "-InstallDir", str(home_dotnet), "-NoPath"],
        ]
        for command in install_commands:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.stdout:
                print(completed.stdout)
            if completed.stderr:
                print(completed.stderr)
            if completed.returncode == 0 and dotnet_cmd.exists() and _try_dotnet(str(dotnet_cmd)):
                return str(dotnet_cmd)
            print(f"[!] home dotnet install step failed: {' '.join(command)} :: exit {completed.returncode}")
        return ""

    install_script = home_dotnet / "dotnet-install.sh"

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
        str(home / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")),
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
    for dll_path in [
        home / "RL_AI" / "SeaEngine" / "csharp" / "SeaEngine" / "bin" / "Release" / "net10.0" / "SeaEngine.dll",
        home / "RL_AI" / "SeaEngine" / "csharp" / "SeaEngine" / "bin" / "Debug" / "net10.0" / "SeaEngine.dll",
    ]:
        if dll_path.exists() and (dll_path.parent / "Newtonsoft.Json.dll").exists():
            return True
    return False


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

    extra_ok, extra_output = _probe_extra_python_deps(python_cmd)
    if extra_ok:
        print(f"python deps ok: {python_cmd}")
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

    print(
        f"python deps ok: {sys.executable} | "
        f"torch={torch.__version__} | numpy={numpy.__version__} | "
        f"setuptools={setuptools.__version__} | cuda={torch.cuda.is_available()}"
    )


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
        raise RuntimeError("dotnet is unavailable and SeaEngine must be rebuilt.")
    home = Path.home()
    project_root = home / "RL_AI" / "SeaEngine" / "csharp"
    engine_csproj = project_root / "SeaEngine" / "SeaEngine.csproj"

    env = os.environ.copy()
    env.setdefault("DOTNET_CLI_UI_LANGUAGE", "en")
    completed = subprocess.run(
        [dotnet_cmd, "build", str(engine_csproj), "-c", "Release", "-v", "q"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr)
    if completed.returncode != 0:
        completed.check_returncode()
    print("SeaEngine build ok")


def _default_num_envs() -> int:
    return 4


def _set_single_worker_defaults() -> None:
    os.environ.setdefault("SEAENGINE_VECTOR_BACKEND", "isolated")
    os.environ.setdefault("SEAENGINE_NUM_ENVS", str(_default_num_envs()))
    os.environ.setdefault("SEAENGINE_LOCAL_THREADS", "0")
    os.environ.setdefault("SEAENGINE_WORKERS", "0")
    os.environ.setdefault("SEAENGINE_LOCAL_MAX_WORKERS", "0")
    os.environ.setdefault("SEAENGINE_SCENARIO_WORKERS", "2")
    os.environ.setdefault("SEAENGINE_PARALLEL_WORKERS", "1")
    os.environ.setdefault("SEAENGINE_QUIET_WORKER_LOG", "1")
    os.environ.setdefault("SEAENGINE_SUPPRESS_NATIVE_LOGS", "1")
    os.environ.setdefault("SEAENGINE_FAST_POOL", "0")
    os.environ.setdefault("SEAENGINE_TRAIN_MAX_TURNS", "70")
    os.environ.setdefault("SEAENGINE_TRAIN_LAYOUT_MODE", "hard_mixed")
    os.environ.setdefault("SEAENGINE_TRAIN_LAYOUT_HARD_RATIO", "0.40")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_MODE", "restore")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_SIMS", "1")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_TOP_K", "2")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS", "1")
    os.environ.setdefault("SEAENGINE_BELIEF_MCTS_CANDIDATE_MIXING_STRATEGY", "policy_prior_plus_heuristic_topk")
    os.environ.setdefault("SEAENGINE_OPENING_NOISE_TURNS", "2")
    os.environ.setdefault("SEAENGINE_OPENING_NOISE_PROB", "0.08")
    os.environ.setdefault("SEAENGINE_OPENING_TEACHER_PROB", "0.18")
    os.environ.setdefault("SEAENGINE_OPENING_TEACHER_TURNS", "5")
    os.environ.setdefault("SEAENGINE_TACTICAL_TEACHER_PROB", "0.16")
    os.environ.setdefault("SEAENGINE_IMITATION_COEF", "0.05")
    os.environ.setdefault("SEAENGINE_EARLY_LOSS_LOG", "1")
    os.environ.setdefault("SEAENGINE_EARLY_LOSS_EPISODES", "100")
    os.environ.setdefault("SEAENGINE_PPO_LR", "0.00015")
    os.environ.setdefault("SEAENGINE_PPO_ENTROPY", "0.004")
    os.environ.setdefault("SEAENGINE_PPO_TARGET_KL", "0.08")
    os.environ.setdefault("SEAENGINE_PPO_MAX_GRAD_NORM", "0.5")
    os.environ.setdefault("SEAENGINE_SAVE_SCENARIO_REPORTS", "0")
    os.environ.setdefault("SEAENGINE_SAVE_SCENARIO_HISTORIES", "0")
    os.environ.setdefault("SEAENGINE_EVAL_HISTORY_LIMIT", "50")
    os.environ.setdefault("SEAENGINE_LOG_ARCHIVE_MODE", "compact")


def _format_wld(summary: dict[str, object]) -> str:
    wins = int(summary.get("wins", 0))
    losses = int(summary.get("losses", 0))
    draws = int(summary.get("draws", 0))
    total = max(1, wins + losses + draws)
    non_draw_total = max(1, wins + losses)
    total_rate = 100.0 * wins / total
    non_draw_rate = 100.0 * wins / non_draw_total
    return (
        f"w/l/d={wins}/{losses}/{draws} | "
        f"win={total_rate:.1f}% | win(non-draw)={non_draw_rate:.1f}%"
    )
def _run_train_eval(
    eval_matches: int,
    train_episodes: int,
    max_turns: int,
    update_interval: int,
    seed: int,
    *,
    resume_model_path: str = "",
    resume_episodes_completed: int = 0,
    eval_belief_mcts: bool = True,
    skip_initial_eval: bool = False,
) -> None:
    _set_single_worker_defaults()
    _apply_parallel_opt_env("start")

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

    for module_name in list(sys.modules):
        if module_name == "RL_AI" or module_name.startswith("RL_AI."):
            del sys.modules[module_name]
    importlib.invalidate_caches()

    from RL_AI.training import trainer as seaengine_trainer_module
    from RL_AI.SeaEngine.bridge import pythonnet_session as pythonnet_session_module
    from RL_AI.training import run_train_eval_experiment

    print(f"trainer source: {seaengine_trainer_module.__file__}")
    print(f"pythonnet source: {pythonnet_session_module.__file__}")

    checkpoint_interval = 2500

    result = run_train_eval_experiment(
        eval_matches=eval_matches,
        train_episodes=train_episodes,
        max_turns=max_turns,
        update_interval=update_interval,
        checkpoint_interval=checkpoint_interval,
        seed=seed,
        resume_model_path=resume_model_path or None,
        resume_episodes_completed=resume_episodes_completed if resume_model_path else None,
        summary_report_path=str(Path.home() / "RL_AI" / "log" / "start_summary.txt"),
        eval_belief_mcts=eval_belief_mcts,
        skip_initial_eval=skip_initial_eval,
    )

    summary_copy = _publish_latest_artifact(
        result.get("summary_report_path"),
        Path.home() / "RL_AI" / "log" / "start_summary.txt",
    )
    latest_model_zip = _publish_latest_artifact(
        result.get("model_zip_path"),
        Path.home() / "RL_AI" / "models" / "start_latest.zip",
    )
    model_copy = _publish_latest_artifact(
        result.get("model_zip_path"),
        Path.home() / "RL_AI" / "models" / "start_model.zip",
    )

    print("=== SeaEngine Train/Eval Experiment ===")
    print(result["train"])
    print(f"artifact log zip: {result.get('log_zip_path')}")
    print(f"artifact summary: {summary_copy}")
    print(f"artifact model zip: {latest_model_zip}")
    print(f"artifact model alias: {model_copy}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SeaEngine train/eval runner")
    parser.add_argument("--eval-matches", type=int, default=50)
    parser.add_argument("--train-episodes", type=int, default=10000)
    parser.add_argument("--max-turns", type=int, default=70)
    parser.add_argument("--update-interval", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--skip-unzip", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--log-file", type=str, default="")
    parser.add_argument("--resume-model-path", type=str, default="")
    parser.add_argument("--resume-episodes-completed", type=int, default=0)
    parser.add_argument(
        "--eval-belief-mcts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use shallow belief-MCTS wrapper for evaluation suites only",
    )
    parser.add_argument(
        "--skip-initial-eval",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip checkpoint 0 initial evaluation and start training immediately.",
    )
    args = parser.parse_args()

    default_log = Path.home() / "start.log"
    log_file = Path(args.log_file) if args.log_file else default_log
    _setup_logger(log_file)

    _set_single_worker_defaults()
    dotnet_cmd = _ensure_dotnet()

    _ensure_python_deps()
    _apply_parallel_opt_env("start")

    if not args.skip_unzip:
        _prepare_project_dir()

    print("[*] start.py launched")
    print(f"[*] pid={os.getpid()}")
    print(
        f"[*] args: eval_matches_per_combo={args.eval_matches}, train_episodes={args.train_episodes}, checkpoint_interval=2500, "
        f"max_turns={args.max_turns}, update_interval={args.update_interval}, seed={args.seed}, "
        f"model_hidden_dim={os.environ.get('SEAENGINE_MODEL_HIDDEN_DIM', '192')}, "
        f"belief_mcts_sims={os.environ.get('SEAENGINE_BELIEF_MCTS_SIMS', '1')}, "
        f"belief_mcts_top_k={os.environ.get('SEAENGINE_BELIEF_MCTS_TOP_K', '2')}, "
        f"belief_mcts_rollout_steps={os.environ.get('SEAENGINE_BELIEF_MCTS_ROLLOUT_STEPS', '1')}, "
        f"belief_mcts_candidate_mixing_strategy={os.environ.get('SEAENGINE_BELIEF_MCTS_CANDIDATE_MIXING_STRATEGY', 'policy_prior_plus_heuristic_topk')}, "
        f"eval_belief_mcts={args.eval_belief_mcts}, belief_mcts_mode={os.environ.get('SEAENGINE_BELIEF_MCTS_MODE', 'restore')}, "
        f"skip_unzip={args.skip_unzip}, skip_build={args.skip_build}, "
        f"skip_initial_eval={args.skip_initial_eval}"
    )

    if not args.skip_build:
        _build_csharp(dotnet_cmd)

    _run_train_eval(
        eval_matches=args.eval_matches,
        train_episodes=args.train_episodes,
        max_turns=args.max_turns,
        update_interval=args.update_interval,
        seed=int(args.seed),
        resume_model_path=args.resume_model_path,
        resume_episodes_completed=args.resume_episodes_completed,
        eval_belief_mcts=args.eval_belief_mcts,
        skip_initial_eval=args.skip_initial_eval,
    )
    print("[*] start.py finished successfully")
    return 0


if __name__ == "__main__":
    _script_started_at = time.perf_counter()
    try:
        _exit_code = main()
        print(f"[*] start.py total runtime: {_format_elapsed(time.perf_counter() - _script_started_at)}")
        raise SystemExit(_exit_code)
    except Exception as exc:
        print("[!] start.py failed")
        print(f"[!] error: {exc}")
        print(traceback.format_exc())
        print(f"[*] start.py total runtime: {_format_elapsed(time.perf_counter() - _script_started_at)}")
        raise SystemExit(1) from exc
