#!/usr/bin/env python3
"""Bias / symmetry checks for SeaEngine RL agents.

This script keeps the environment bootstrap from start.py locally, while
running focused experiments for:
  - random/random, greedy/greedy, RL/RL self-play comparisons
  - canonical-view ablation
  - mirror agreement measurement
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
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = log_dir / f"bias_check_log_{ts}.zip"
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in bias_txts:
            zf.write(path, arcname=path.name)
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


def _measure_mirror_agreement(
    *,
    agent_factory: Callable[[int], Any],
    total_matches: int,
    card_data_path: Optional[str],
    max_turns: int,
    seed: Optional[int],
    label: str,
) -> Dict[str, Any]:
    from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession

    scenarios = _scenario_definitions(label)
    per = total_matches // len(scenarios)
    rem = total_matches % len(scenarios)
    result_rows: list[Dict[str, Any]] = []
    total_states = 0
    total_agree = 0
    session = PythonNetSession(card_data_path=card_data_path)
    session.start()
    try:
        for idx, scenario in enumerate(scenarios):
            matches = per + (1 if idx < rem else 0)
            if matches <= 0:
                continue
            agent = agent_factory((seed or 0) + 9000 + idx)
            agent.name = f"{label}_mir"
            agreement = 0
            states = 0
            scenario_start = time.time()
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
                        agreement += 1
                    states += 1
                    if states == 1 or states % 500 == 0:
                        elapsed = max(1e-9, time.time() - scenario_start)
                        print(
                            f"[*] mirror/{label} progress: states={states} "
                            f"states/s={states / elapsed:.2f} | agree={agreement}",
                            flush=True,
                        )
                    snapshot = session.apply_action(str(orig_action.get("uid", "")))
            total_states += states
            total_agree += agreement
            elapsed = max(1e-9, time.time() - scenario_start)
            print(
                f"[*] mirror/{label} scenario done: {scenario['label']} | states/s={states / elapsed:.2f}",
                flush=True,
            )
            result_rows.append(
                {
                    "label": str(scenario["label"]),
                    "states": states,
                    "agreement": agreement,
                    "agreement_rate": _human_rate(agreement, states),
                }
            )
    finally:
        session.close()

    return {
        "label": label,
        "rows": result_rows,
        "states": total_states,
        "agreement": total_agree,
        "agreement_rate": _human_rate(total_agree, total_states),
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
) -> Dict[str, Any]:
    from RL_AI.training import evaluate_agents

    scenarios = _scenario_definitions(label)
    per = total_matches // len(scenarios)
    rem = total_matches % len(scenarios)
    results: list[Dict[str, Any]] = []
    progress_callback = _make_speed_progress_callback(
        task_name=f"suite/{label}",
        total_units=total_matches,
        unit_label="eps/s",
        interval=max(1, total_matches // 4),
    )
    for idx, scenario in enumerate(scenarios):
        matches = per + (1 if idx < rem else 0)
        if matches <= 0:
            continue
        p1_agent = agent_factory((seed or 0) + idx * 2 + 1)
        p2_agent = agent_factory((seed or 0) + idx * 2 + 2)
        p1_agent.name = f"{label}_p1"
        p2_agent.name = f"{label}_p2"

        print(f"[*] Suite {label}: {scenario['label']} | n={matches}")
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
            progress_callback=progress_callback,
        )
        p1_wins = int(summary["p1_wins"])
        p2_wins = int(summary["p2_wins"])
        draws = int(summary["draws"])
        episodes = int(summary["episodes"])
        wr = _human_rate(p1_wins, episodes)
        opp_wr = _human_rate(p2_wins, episodes)
        results.append(
            {
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
        )

        if include_history:
            history_path = scenario_report_path.with_name(f"{scenario_report_path.stem}_hist.txt")
            saved_history_path = _save_history_report(
                title=f"Bias Check {label} / {scenario['label']} Histories",
                summary=summary,
                report_path=history_path,
                history_limit=history_limit,
            )
            if saved_history_path is not None:
                results[-1]["history_path"] = str(saved_history_path)

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
    history_limit: Optional[int] = None,
) -> Optional[Path]:
    from RL_AI.analysis.reports import build_win_rate_report, save_report
    from RL_AI.training.experiment import _format_match_history

    histories = list(summary.get("histories", []))
    if not histories:
        return None
    if history_limit is not None and history_limit >= 0:
        histories = histories[:history_limit]
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
    hidden_dim: int = 128,
) -> Callable[[int], Any]:
    from RL_AI.agents import SeaEngineRLAgent, load_state_dict_flexible
    from RL_AI.SeaEngine.observation import STATE_VECTOR_DIM

    def _factory(seed: int) -> Any:
        agent = SeaEngineRLAgent(
            hidden_dim=hidden_dim,
            sample_actions=False,
            device=device,
            seed=seed,
        )
        agent.ensure_model(state_dim=STATE_VECTOR_DIM)
        assert agent.model is not None
        load_state_dict_flexible(agent.model, state_dict)
        agent.model.eval()
        agent.name = f"rl_{observation_mode}"
        return _BiasCheckRLAgentWrapper(agent, observation_mode=observation_mode)

    return _factory


class _BiasCheckRLAgentWrapper:
    def __init__(self, agent: Any, observation_mode: str) -> None:
        self._agent = agent
        self.observation_mode = observation_mode
        self.name = getattr(agent, "name", "rl")

    @property
    def device(self):
        return self._agent.device

    def sampling_mode(self, enabled: bool):
        return self._agent.sampling_mode(enabled)

    def select_action(self, snapshot: Dict[str, Any], legal_actions: Sequence[Dict[str, Any]]):
        if self.observation_mode == "auto":
            return self._agent.select_action(snapshot, legal_actions)
        if self.observation_mode == "python_canonical":
            obs = _build_python_observation(snapshot, canonical=True)
        elif self.observation_mode == "python_raw":
            obs = _build_python_observation(snapshot, canonical=False)
        else:
            obs = _build_python_observation(snapshot, canonical=True)

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
    from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRandomAgent

    kind = kind.lower().strip()

    def _factory(seed: int) -> Any:
        if kind == "random":
            return SeaEngineRandomAgent(seed=seed_base + seed)
        if kind == "greedy":
            return SeaEngineGreedyAgent(seed=seed_base + seed)
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
    from RL_AI.agents import SeaEngineGreedyAgent, SeaEngineRandomAgent

    task_kind = str(task["kind"])
    task_name = str(task["task_name"])
    label = str(task["label"])
    device = str(task["device"])
    seed = int(task["seed"])
    card_data_path = task.get("card_data_path")
    max_turns = int(task.get("max_turns", 100))

    print(f"[*] task start: {task_name} ({task_kind})")

    if task_kind == "same_policy":
        total_matches = int(task["total_matches"])
        include_history = bool(task.get("include_history", False))
        history_limit = task.get("history_limit")
        history_limit_int = None if history_limit is None else int(history_limit)
        agent_kind = str(task["agent_kind"])
        if agent_kind in {"random", "greedy"}:
            agent_factory = _make_basic_agent_factory(agent_kind, device=device)
        elif agent_kind == "rl":
            model_path = Path(task["model_path"])
            observation_mode = str(task.get("observation_mode", "python_canonical"))
            state_dict = _load_state_dict(model_path)
            agent_factory = _make_rl_agent_factory(
                state_dict=state_dict,
                observation_mode=observation_mode,
                device=device,
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
            history_limit=history_limit_int,
        )
        return {
            "task_name": task_name,
            "task_kind": task_kind,
            "result": result,
        }

    if task_kind == "mirror":
        total_matches = int(task["total_matches"])
        observation_mode = str(task.get("observation_mode", "python_canonical"))
        model_path = Path(task["model_path"])
        state_dict = _load_state_dict(model_path)
        agent_factory = _make_rl_agent_factory(
            state_dict=state_dict,
            observation_mode=observation_mode,
            device=device,
        )
        result = _measure_mirror_agreement(
            agent_factory=agent_factory,
            total_matches=total_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            seed=seed,
            label=label,
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
        history_limit_int = None if history_limit is None else int(history_limit)
        model_path = Path(task["model_path"])
        state_dict = _load_state_dict(model_path)
        agent_factory = _make_rl_agent_factory(
            state_dict=state_dict,
            observation_mode="python_canonical",
            device=device,
        )
        result = _run_same_policy_suite(
            label=label,
            agent_factory=agent_factory,
            total_matches=total_matches,
            card_data_path=card_data_path,
            max_turns=max_turns,
            seed=seed,
            include_history=include_history,
            history_limit=history_limit_int,
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
    parser.add_argument("--total-matches", type=int, default=400, help="Total matches per same-policy suite (across 8 combos)")
    parser.add_argument("--ablation-matches", type=int, default=400, help="Total matches for canonical/raw ablation suite")
    parser.add_argument("--mirror-matches", type=int, default=400, help="Total matches for mirror agreement measurement")
    parser.add_argument("--checkpoint-matches", type=int, default=400, help="Total matches per checkpoint side-gap suite")
    parser.add_argument("--checkpoint-limit", type=int, default=0, help="Limit number of checkpoint files (0 = all)")
    parser.add_argument("--parallel-workers", type=int, default=0, help="Number of process workers for bias suites (0 = auto)")
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
        f"[*] args: model_path={args.model_path or '<latest>'}, total_matches={args.total_matches}, "
        f"ablation_matches={args.ablation_matches}, mirror_matches={args.mirror_matches}, "
        f"checkpoint_matches={args.checkpoint_matches}, checkpoint_limit={args.checkpoint_limit}, "
        f"parallel_workers={args.parallel_workers}, seed={args.seed}, device={args.device}, "
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
    temp_dir_mgr: Optional[tempfile.TemporaryDirectory[str]] = None
    extracted_checkpoints: list[Path] = []
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

        print(f"[*] model source: {model_source}")
        print(f"[*] current model: {current_model_path}")
        print(f"[*] checkpoint files: {len(extracted_checkpoints)}")
        if extracted_checkpoints:
            print(f"[*] checkpoints first/last: {extracted_checkpoints[0].name} / {extracted_checkpoints[-1].name}")

        device = _resolve_device(args.device)
        parallel_workers = args.parallel_workers if args.parallel_workers > 0 else (2 if device == "cuda" else 4)
        parallel_workers = max(1, min(parallel_workers, 8))

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
                "include_history": True,
                "history_limit": 5,
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
                "include_history": True,
                "history_limit": 5,
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
                "include_history": True,
                "history_limit": 5,
            },
            {
                "task_name": "ablation_canonical",
                "kind": "same_policy",
                "label": "rl_canonical",
                "agent_kind": "rl",
                "observation_mode": "python_canonical",
                "model_path": str(current_model_path),
                "total_matches": args.ablation_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 101,
                "device": device,
                "include_history": False,
            },
            {
                "task_name": "ablation_raw",
                "kind": "same_policy",
                "label": "rl_raw",
                "agent_kind": "rl",
                "observation_mode": "python_raw",
                "model_path": str(current_model_path),
                "total_matches": args.ablation_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 202,
                "device": device,
                "include_history": False,
            },
            {
                "task_name": "mirror_canonical",
                "kind": "mirror",
                "label": "rl_canonical",
                "observation_mode": "python_canonical",
                "model_path": str(current_model_path),
                "total_matches": args.mirror_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 303,
                "device": device,
            },
            {
                "task_name": "mirror_raw",
                "kind": "mirror",
                "label": "rl_raw",
                "observation_mode": "python_raw",
                "model_path": str(current_model_path),
                "total_matches": args.mirror_matches,
                "card_data_path": None,
                "max_turns": 100,
                "seed": args.seed + 404,
                "device": device,
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
                    "episode": _episode_from_name(ckpt_path),
                    "checkpoint_path": str(ckpt_path),
                    "include_history": True,
                    "history_limit": 5,
                }
            )

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
            ("RL/RL canonical", task_results["rl_family"]),
        ]
        ablation_canonical = task_results["ablation_canonical"]
        ablation_raw = task_results["ablation_raw"]
        mirror_canonical = task_results["mirror_canonical"]
        mirror_raw = task_results["mirror_raw"]

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
            "NOTE: RL suites below rebuild Python observations so canonical/raw view can be isolated cleanly.",
            "",
            "=== Family Comparisons ===",
        ]
        for title, suite in family_runs:
            report_lines.append(_format_suite_report(title, suite))
            report_lines.append("")

        report_lines.extend(
            [
                "=== Canonical View Ablation ===",
                _format_suite_report("RL canonical", ablation_canonical),
                "",
                _format_suite_report("RL raw", ablation_raw),
                "",
                "=== Mirror Agreement ===",
                f"canonical: states={mirror_canonical['states']}, agree={mirror_canonical['agreement']}, "
                f"agreement_rate={mirror_canonical['agreement_rate']:.2f}%",
                f"raw: states={mirror_raw['states']}, agree={mirror_raw['agreement']}, "
                f"agreement_rate={mirror_raw['agreement_rate']:.2f}%",
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

        report_text = "\n".join(report_lines).rstrip() + "\n"
        report_path = save_report(report_text, Path.home() / "RL_AI" / "log" / f"bias_check_{ts}.txt")
        zip_path = _zip_bias_text_logs(run_started_wall)

        print(f"[*] bias report saved: {report_path}")
        if zip_path is not None:
            print(f"[*] bias log archive: {zip_path}")
        print(report_text)
        print("[*] bias_check.py finished successfully")
        return 0
    finally:
        if temp_dir_mgr is not None:
            temp_dir_mgr.cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("[!] bias_check.py failed")
        print(f"[!] error: {exc}")
        print(traceback.format_exc())
        raise
