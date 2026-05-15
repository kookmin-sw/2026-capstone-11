"""Spawn-based isolated SeaEngine vector environment manager."""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from RL_AI.SeaEngine.bridge.process_env_worker import worker_loop


def _normalize_timeout(value: Any, fallback: float = 30.0) -> float:
    try:
        timeout = float(value)
    except Exception:
        timeout = float(fallback)
    return max(1.0, timeout)


class ProcessVectorSeaEngineEnv:
    """Spawned worker pool that owns PythonNetSession instances."""

    def __init__(self, num_envs: int = 8, card_data_path: Optional[str] = None, timeout_sec: float = 30.0):
        self.num_envs = max(1, int(num_envs))
        self.card_data_path = card_data_path
        self.timeout_sec = _normalize_timeout(os.getenv("SEAENGINE_WORKER_TIMEOUT_SEC", timeout_sec))
        self._ctx = mp.get_context("spawn")
        self._pipes: list[Any] = []
        self._processes: list[Any] = []
        self._waiting: list[Tuple[int, Any]] = []
        self._started = False

    def _spawn_worker(self, index: int) -> None:
        parent_conn, child_conn = self._ctx.Pipe()
        proc = self._ctx.Process(
            target=worker_loop,
            args=(child_conn, self.card_data_path),
            daemon=True,
        )
        proc.start()
        if index < len(self._pipes):
            self._pipes[index] = parent_conn
            self._processes[index] = proc
        else:
            self._pipes.append(parent_conn)
            self._processes.append(proc)
        try:
            child_conn.close()
        except Exception:
            pass

    def _ensure_started(self) -> None:
        if not self._started:
            self.start()

    def _send(self, index: int, payload: Dict[str, Any]) -> None:
        pipe = self._pipes[index]
        if not pipe.closed:
            pipe.send(payload)

    def _recv(self, index: int, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        pipe = self._pipes[index]
        timeout_sec = self.timeout_sec if timeout is None else _normalize_timeout(timeout, self.timeout_sec)
        deadline = time.monotonic() + timeout_sec
        while True:
            if pipe.poll(0.05):
                msg = pipe.recv()
                if isinstance(msg, dict) and not msg.get("ok", True):
                    raise RuntimeError(f"Worker {index} error: {msg.get('error', '<unknown>')}")
                if isinstance(msg, dict) and "snapshot" in msg:
                    return dict(msg["snapshot"])
                if isinstance(msg, dict):
                    return msg
                return {"value": msg}
            if time.monotonic() >= deadline:
                self.restart_worker(index)
                raise TimeoutError(f"Worker {index} timed out after {timeout_sec:.1f}s")

    def _close_worker(self, index: int, *, terminate_timeout: float = 2.0) -> None:
        if index >= len(self._pipes):
            return
        pipe = self._pipes[index]
        proc = self._processes[index]
        try:
            if not pipe.closed:
                pipe.send({"cmd": "close"})
        except Exception:
            pass
        try:
            if pipe.poll(self.timeout_sec):
                pipe.recv()
        except Exception:
            pass
        try:
            pipe.close()
        except Exception:
            pass
        try:
            proc.join(timeout=terminate_timeout)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=terminate_timeout)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

    def start(self) -> None:
        if self._started:
            return
        self._pipes = []
        self._processes = []
        for index in range(self.num_envs):
            self._spawn_worker(index)
        for index in range(self.num_envs):
            self._send(index, {"cmd": "ping"})
        for index in range(self.num_envs):
            self._recv(index)
        self._started = True

    def describe_parallelism(self) -> Dict[str, Any]:
        return {
            "backend": "isolated",
            "num_envs": self.num_envs,
            "workers": len(self._processes),
            "threaded": False,
            "worker_scope": "spawned_pythonnet_session_per_process",
            "timeout_sec": self.timeout_sec,
        }

    def init_games(self, configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self._ensure_started()
        limit = min(len(self._pipes), len(configs))
        for index in range(limit):
            self._send(index, {"cmd": "reset", "config": dict(configs[index])})
        return [self._recv(index) for index in range(limit)]

    def step_async(self, cmds: List[Optional[tuple]]):
        self._ensure_started()
        self._waiting = []
        limit = min(len(self._pipes), len(cmds))
        for index in range(limit):
            cmd = cmds[index]
            if cmd is None:
                continue
            name, args = cmd
            if name == "apply_action":
                self._send(index, {"cmd": "step", "action_uid": str(args.get("action_uid", ""))})
                self._waiting.append((index, self._pipes[index]))
            elif name == "init_game":
                self._send(index, {"cmd": "reset", "config": dict(args)})
                self._waiting.append((index, self._pipes[index]))

    def step_wait(self) -> Dict[int, Dict[str, Any]]:
        results: Dict[int, Dict[str, Any]] = {}
        if not self._waiting:
            return results
        for index, _pipe in self._waiting:
            results[index] = self._recv(index)
        self._waiting = []
        return results

    def restart_worker(self, index: int) -> None:
        if index < 0 or index >= len(self._pipes):
            return
        try:
            self._close_worker(index)
        finally:
            self._spawn_worker(index)
            try:
                self._send(index, {"cmd": "ping"})
                self._recv(index)
            except Exception:
                pass

    def close(self) -> None:
        for index in range(len(self._pipes)):
            self._close_worker(index)
        self._pipes = []
        self._processes = []
        self._waiting = []
        self._started = False
