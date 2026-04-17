"""Vectorized environment manager for running multiple SeaEngine instances."""

from __future__ import annotations

import multiprocessing as mp
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

# Use 'spawn' to ensure each process starts fresh, which is safer for CLR/PythonNet.
try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    pass


def _worker_loop(conn, card_data_path):
    import contextlib
    import os
    import sys

    try:
        from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession
    except ImportError:
        curr_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if curr_dir not in sys.path:
            sys.path.insert(0, curr_dir)
        from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession

    quiet_worker = os.getenv("SEAENGINE_QUIET_WORKER_LOG", "1") == "1"
    if quiet_worker:
        devnull = open(os.devnull, "w", encoding="utf-8")
        with contextlib.suppress(Exception):
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)

    session = PythonNetSession(card_data_path=card_data_path)
    try:
        session.start()
        while True:
            cmd, args = conn.recv()
            if cmd == "init_game":
                snapshot = session.init_game(**args)
                conn.send(snapshot)
            elif cmd == "apply_action":
                snapshot = session.apply_action(args["action_uid"])
                conn.send(snapshot)
            elif cmd == "close":
                break
    except Exception:
        error_msg = traceback.format_exc()
        try:
            conn.send({"error": error_msg})
        except Exception:
            pass
    finally:
        try:
            session.close()
        except Exception:
            pass
        conn.close()


class VectorSeaEngineEnv:
    """
    Vector environment for SeaEngine.

    Backends:
    - local (default): keep sessions in current process, optional thread pool
    - process: legacy multiprocessing workers with Pipe IPC
    """

    def __init__(self, num_envs: int = 8, card_data_path: Optional[str] = None):
        self.num_envs = num_envs
        self.card_data_path = card_data_path

        self.backend = os.getenv("SEAENGINE_VECTOR_BACKEND", "local").strip().lower()
        if self.backend not in {"local", "process"}:
            self.backend = "local"

        # SEAENGINE_LOCAL_THREADS supports:
        # - "0"/"false"/"off": disable local thread pool
        # - "1"/"true"/"auto": enable local thread pool with auto worker count
        # - integer style: "8" (explicit max_workers=8)
        local_threads_raw = os.getenv("SEAENGINE_LOCAL_THREADS", "1").strip().lower()
        self.use_threads = True
        self.max_workers = 0
        if local_threads_raw in {"0", "false", "no", "off"}:
            self.use_threads = False
            self.max_workers = 0
        elif local_threads_raw in {"1", "true", "yes", "on", "auto", ""}:
            self.use_threads = True
            self.max_workers = 0
        else:
            parsed_local_threads: Optional[int] = None
            try:
                parsed_local_threads = int(local_threads_raw)
            except Exception:
                parsed_local_threads = None
            if parsed_local_threads is not None and parsed_local_threads > 0:
                self.use_threads = True
                self.max_workers = parsed_local_threads
            else:
                self.use_threads = True
                self.max_workers = 0

        env_workers = int(os.getenv("SEAENGINE_WORKERS", "0") or "0")
        if env_workers > 0:
            self.max_workers = env_workers
        env_max_workers = int(os.getenv("SEAENGINE_LOCAL_MAX_WORKERS", "0") or "0")
        if env_max_workers > 0:
            self.max_workers = env_max_workers

        self.pipes = []
        self.processes = []
        self._sessions = []
        self._executor: Optional[ThreadPoolExecutor] = None
        self._executor_workers = 0
        self._waiting_pipes = []
        self._waiting_cmds: List[Tuple[int, tuple]] = []

    def start(self):
        if self.backend == "process":
            for _ in range(self.num_envs):
                parent_conn, child_conn = mp.Pipe()
                p = mp.Process(target=_worker_loop, args=(child_conn, self.card_data_path), daemon=True)
                p.start()
                self.pipes.append(parent_conn)
                self.processes.append(p)
            return

        from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession

        self._sessions = []
        for _ in range(self.num_envs):
            session = PythonNetSession(card_data_path=self.card_data_path)
            session.start()
            self._sessions.append(session)

        if self.use_threads and self.num_envs > 1:
            cpu = os.cpu_count() or self.num_envs
            workers = self.max_workers if self.max_workers > 0 else min(self.num_envs, cpu)
            workers = max(1, workers)
            self._executor_workers = workers
            self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="seaenv")
        else:
            self._executor_workers = 0

    def describe_parallelism(self) -> Dict[str, Any]:
        if self.backend == "process":
            return {
                "backend": "process",
                "num_envs": self.num_envs,
                "workers": len(self.processes) if self.processes else self.num_envs,
                "threaded": False,
            }
        return {
            "backend": "local",
            "num_envs": self.num_envs,
            "threaded": self._executor is not None,
            "workers": self._executor_workers if self._executor is not None else 1,
            "worker_scope": "cpu_threadpool_for_pythonnet_calls",
        }

    def init_games(self, configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.backend == "process":
            limit = min(len(self.pipes), len(configs))
            for i in range(limit):
                self.pipes[i].send(("init_game", configs[i]))
            return self._recv_n(limit)

        limit = min(len(self._sessions), len(configs))
        if limit == 0:
            return []

        if self._executor is None or limit <= 1:
            results = [self._sessions[i].init_game(**configs[i]) for i in range(limit)]
            return results

        futures = [self._executor.submit(self._sessions[i].init_game, **configs[i]) for i in range(limit)]
        return [f.result() for f in futures]

    def step_async(self, cmds: List[Optional[tuple]]):
        if self.backend == "process":
            self._waiting_pipes = []
            limit = min(len(self.pipes), len(cmds))
            for i in range(limit):
                pipe = self.pipes[i]
                if cmds[i] is not None:
                    pipe.send(cmds[i])
                    self._waiting_pipes.append((i, pipe))
            return

        self._waiting_cmds = []
        limit = min(len(self._sessions), len(cmds))
        for i in range(limit):
            cmd = cmds[i]
            if cmd is not None:
                self._waiting_cmds.append((i, cmd))

    def step_wait(self) -> Dict[int, Dict[str, Any]]:
        if self.backend == "process":
            res = {}
            for i, pipe in self._waiting_pipes:
                msg = pipe.recv()
                if "error" in msg:
                    raise RuntimeError(f"Worker {i} failed: {msg['error']}")
                res[i] = msg
            self._waiting_pipes = []
            return res

        res: Dict[int, Dict[str, Any]] = {}
        if not self._waiting_cmds:
            return res

        if self._executor is None or len(self._waiting_cmds) <= 1:
            for i, cmd in self._waiting_cmds:
                name, args = cmd
                if name == "apply_action":
                    res[i] = self._sessions[i].apply_action(args["action_uid"])
                elif name == "init_game":
                    res[i] = self._sessions[i].init_game(**args)
            self._waiting_cmds = []
            return res

        futures = []
        for i, cmd in self._waiting_cmds:
            name, args = cmd
            if name == "apply_action":
                futures.append((i, self._executor.submit(self._sessions[i].apply_action, args["action_uid"])))
            elif name == "init_game":
                futures.append((i, self._executor.submit(self._sessions[i].init_game, **args)))

        for i, fut in futures:
            res[i] = fut.result()
        self._waiting_cmds = []
        return res

    def _recv_n(self, count: int) -> List[Dict[str, Any]]:
        res = []
        for pipe in self.pipes[:count]:
            msg = pipe.recv()
            if "error" in msg:
                raise RuntimeError(f"Worker failed: {msg['error']}")
            res.append(msg)
        return res

    def close(self):
        if self.backend == "process":
            for pipe in self.pipes:
                try:
                    pipe.send(("close", None))
                except Exception:
                    pass
            for p in self.processes:
                p.join(timeout=2)
                if p.is_alive():
                    p.terminate()
            self.pipes = []
            self.processes = []
            return

        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None
            self._executor_workers = 0
        for session in self._sessions:
            try:
                session.close()
            except Exception:
                pass
        self._sessions = []
