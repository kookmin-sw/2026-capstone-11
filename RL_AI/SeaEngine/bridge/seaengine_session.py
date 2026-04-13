"""Bridge for running the SeaEngine C# project as a gRPC backend."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

import grpc
from google.protobuf.json_format import MessageToDict

# gRPC generated files
from RL_AI.protos import seaengine_pb2, seaengine_pb2_grpc


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
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[seaengine_pb2_grpc.SeaEngineServiceStub] = None

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

        # 서버 프로세스 실행
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

        # 서버가 출력하는 포트 번호 대기
        port = None
        start_time = time.time()
        while time.time() - start_time < 30: # 30초 타임아웃
            line = self._proc.stdout.readline()
            if not line:
                break
            if line.startswith("PORT:"):
                port = line.strip().split(":")[1]
                break
        
        if not port:
            stderr = self._proc.stderr.read()
            self.close()
            raise RuntimeError(f"Failed to get gRPC port from SeaEngineCli. stderr={stderr}")

        # gRPC 채널 및 스텁 설정
        self._channel = grpc.insecure_channel(f"localhost:{port}")
        self._stub = seaengine_pb2_grpc.SeaEngineServiceStub(self._channel)
        
        try:
            self.ping()
        except Exception as exc:
            self.close()
            raise RuntimeError(f"Failed to connect to gRPC server on port {port}.") from exc

    def close(self) -> None:
        if self._channel:
            self._channel.close()
            self._channel = None
        
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
            self._proc = None
        
        self._stub = None

    def ping(self) -> Dict[str, Any]:
        if not self._stub: raise RuntimeError("Session not started")
        response = self._stub.Ping(seaengine_pb2.Empty())
        return {"message": response.message}

    def init_game(
        self,
        *,
        player1_deck: str = "",
        player2_deck: str = "",
        player1_id: str = "P1",
        player2_id: str = "P2",
    ) -> Dict[str, Any]:
        if not self._stub: raise RuntimeError("Session not started")
        request = seaengine_pb2.InitRequest(
            card_data_path=self.card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            player1_id=player1_id,
            player2_id=player2_id,
        )
        snapshot = self._stub.InitGame(request)
        return self._message_to_dict(snapshot)

    def snapshot(self) -> Dict[str, Any]:
        if not self._stub: raise RuntimeError("Session not started")
        snapshot = self._stub.GetSnapshot(seaengine_pb2.Empty())
        return self._message_to_dict(snapshot)

    def apply_action(self, action_uid: str) -> Dict[str, Any]:
        if not self._stub: raise RuntimeError("Session not started")
        request = seaengine_pb2.ActionRequest(action_uid=action_uid)
        snapshot = self._stub.ApplyAction(request)
        return self._message_to_dict(snapshot)

    def _message_to_dict(self, message) -> Dict[str, Any]:
        # 기존 코드 호환성을 위해 snake_case 유지 및 빈 리스트 처리
        return MessageToDict(
            message,
            preserving_proto_field_name=True,
            including_default_value_fields=True
        )

    def _build_launch_command(self, dotnet_cmd: str) -> list[str]:
        dll_path = self.cli_build_dir / "SeaEngineCli.dll"
        windows_apphost = self.cli_build_dir / "SeaEngineCli.exe"

        # gRPC 서버로 실행할 때는 build 결과물을 직접 실행하는 것이 유리함
        if os.name == "nt" and windows_apphost.exists():
            return [str(windows_apphost)]
        if dll_path.exists():
            return [dotnet_cmd, str(dll_path)]
        
        return [dotnet_cmd, "run", "--project", str(self.cli_project), "-c", "Debug", "--no-build"]

    @staticmethod
    def _resolve_dotnet_cmd() -> str:
        bundled_dotnet = Path.home() / ".dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
        if bundled_dotnet.exists():
            return str(bundled_dotnet)
        return "dotnet"
