"""Bridge for running the copied SeaEngine C# project as the actual game backend."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class SeaEngineSession:
    def __init__(
        self,
        *,
        card_data_path: Optional[str] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parent.parent)
        self.cli_project = self.project_root / "csharp" / "SeaEngineCli" / "SeaEngineCli.csproj"
        self.cli_build_dir = self.project_root / "csharp" / "SeaEngineCli" / "bin" / "Debug" / "net10.0"
        self.card_data_path = str(
            Path(card_data_path).resolve()
            if card_data_path is not None
            else (self.project_root.parent / "cards" / "Cards.csv").resolve()
        )
        self._proc: Optional[subprocess.Popen[str]] = None

    def start(self) -> None:
        if self._proc is not None:
            return
        dotnet_cmd = os.environ.get("DOTNET_CMD") or self._resolve_dotnet_cmd()
        dotnet_cli_home = os.environ.get("DOTNET_CLI_HOME") or str(
            (Path.home() / ".dotnet_cli_home").resolve()
        )
        launch_cmd = self._build_launch_command(dotnet_cmd)
        dotnet_root = Path(dotnet_cmd).resolve().parent if dotnet_cmd else None
        env = {
            **os.environ,
            "DOTNET_CLI_HOME": dotnet_cli_home,
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        }
        if dotnet_root is not None:
            env.setdefault("DOTNET_ROOT", str(dotnet_root))
            env.setdefault("DOTNET_ROOT_X64", str(dotnet_root))
        self._proc = subprocess.Popen(
            launch_cmd,
            cwd=str(self.project_root.parent),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            self.ping()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "dotnet executable was not found. Install .NET SDK or set DOTNET_CMD to the full dotnet path."
            ) from exc

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            try:
                self._request({"command": "close"})
            except (BrokenPipeError, json.JSONDecodeError, RuntimeError):
                # Shutdown is best-effort. Some environments close the bridge
                # before returning the final JSON response, which is fine here.
                pass
        finally:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
            self._proc = None

    def ping(self) -> Dict[str, Any]:
        return self._request({"command": "ping"})

    def init_game(
        self,
        *,
        player1_deck: str = "",
        player2_deck: str = "",
        player1_id: str = "P1",
        player2_id: str = "P2",
    ) -> Dict[str, Any]:
        return self._request(
            {
                "command": "init",
                "card_data_path": self.card_data_path,
                "player1_deck": player1_deck,
                "player2_deck": player2_deck,
                "player1_id": player1_id,
                "player2_id": player2_id,
            }
        )

    def snapshot(self) -> Dict[str, Any]:
        return self._request({"command": "snapshot"})

    def apply_action(self, action_uid: str) -> Dict[str, Any]:
        return self._request({"command": "apply", "action_uid": action_uid})

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("SeaEngine session is not started.")

        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

        response = self._read_response_line()
        if response.get("status") != "ok":
            raise RuntimeError(response.get("error", "unknown_seaengine_error"))
        return response["payload"]

    def _read_response_line(self) -> Dict[str, Any]:
        if self._proc is None or self._proc.stdout is None:
            raise RuntimeError("SeaEngine session is not started.")

        while True:
            line = self._proc.stdout.readline()
            if not line:
                stderr = ""
                if self._proc.stderr is not None:
                    stderr = self._proc.stderr.read()
                raise RuntimeError(f"SeaEngine bridge terminated unexpectedly. stderr={stderr}")

            stripped = line.strip()
            if not stripped:
                continue

            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                # Ignore any unexpected non-JSON line and keep reading the next
                # response line. The bridge protocol itself is still JSON-only.
                continue


    def _build_launch_command(self, dotnet_cmd: str) -> list[str]:
        dll_path = self.cli_build_dir / "SeaEngineCli.dll"
        linux_apphost = self.cli_build_dir / "SeaEngineCli"
        windows_apphost = self.cli_build_dir / "SeaEngineCli.exe"

        if os.name == "nt" and windows_apphost.exists():
            return [str(windows_apphost)]
        if dll_path.exists():
            return [dotnet_cmd, str(dll_path)]
        if linux_apphost.exists():
            return [str(linux_apphost)]
        return [dotnet_cmd, "run", "--project", str(self.cli_project), "-c", "Debug", "--no-build"]

    @staticmethod
    def _resolve_dotnet_cmd() -> str:
        bundled_dotnet = Path.home() / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
        if bundled_dotnet.exists():
            return str(bundled_dotnet)
        return "dotnet"
