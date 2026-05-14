"""Worker process entrypoint for isolated SeaEngine vector environments."""

from __future__ import annotations

import contextlib
import os
import traceback
from typing import Any, Dict


def _suppress_worker_output() -> None:
    quiet_worker = os.getenv("SEAENGINE_QUIET_WORKER_LOG", "1") == "1"
    if not quiet_worker:
        return
    devnull = open(os.devnull, "w", encoding="utf-8")
    with contextlib.suppress(Exception):
        os.dup2(devnull.fileno(), 1)
        os.dup2(devnull.fileno(), 2)


def worker_loop(conn, card_data_path: str | None) -> None:
    _suppress_worker_output()

    from RL_AI.SeaEngine.bridge.pythonnet_session import PythonNetSession

    session = PythonNetSession(card_data_path=card_data_path)
    try:
        session.start()
        while True:
            msg = conn.recv()
            cmd = str(msg.get("cmd", "")).strip().lower()

            if cmd == "ping":
                conn.send({"ok": True, "pong": True})
                continue

            if cmd == "reset":
                config = dict(msg.get("config", {}) or {})
                snapshot = session.init_game(**config)
                conn.send({"ok": True, "snapshot": snapshot})
                continue

            if cmd == "step":
                action_uid = str(msg.get("action_uid", ""))
                snapshot = session.apply_action(action_uid)
                conn.send({"ok": True, "snapshot": snapshot})
                continue

            if cmd == "close":
                conn.send({"ok": True})
                break

            conn.send({"ok": False, "error": f"unknown cmd: {cmd}"})
    except BaseException:
        error_msg = traceback.format_exc()
        try:
            conn.send({"ok": False, "error": error_msg})
        except Exception:
            pass
        raise
    finally:
        try:
            session.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
