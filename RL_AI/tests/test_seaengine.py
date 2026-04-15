import os
import sys
import shutil
from pathlib import Path
import pytest

# Add the project root to sys.path
sys.path.insert(0, os.getcwd())

from RL_AI.SeaEngine.bridge.seaengine_session import SeaEngineSession
from RL_AI.SeaEngine.agents import SeaEngineRandomAgent, SeaEngineRLAgent
from RL_AI.SeaEngine.trainer import SeaEnginePPOTrainer

@pytest.fixture(scope="session", autouse=True)
def setup_dotnet():
    dotnet_cmd = shutil.which("dotnet")
    if dotnet_cmd:
        os.environ["DOTNET_CMD"] = dotnet_cmd
        dotnet_root = str(Path(dotnet_cmd).resolve().parent)
        os.environ["DOTNET_ROOT"] = dotnet_root
        os.environ["DOTNET_ROOT_X64"] = dotnet_root

def test_session_start_stop():
    session = SeaEngineSession()
    session.start()
    try:
        res = session.ping()
        assert res["message"] == "pong"
    finally:
        session.close()

def test_game_init():
    session = SeaEngineSession()
    session.start()
    try:
        snapshot = session.init_game()
        assert "turn" in snapshot
        assert snapshot["turn"] == 1
        assert len(snapshot["players"]) == 2
        assert len(snapshot["actions"]) > 0
    finally:
        session.close()

def test_collect_episode():
    agent = SeaEngineRLAgent()
    trainer = SeaEnginePPOTrainer(agent)
    # Collect a very short episode
    result = trainer.collect_episode(max_turns=2)
    assert "buffer" in result
    assert "result" in result
    assert "steps" in result
    assert result["steps"] > 0

def test_update_from_buffer():
    agent = SeaEngineRLAgent()
    trainer = SeaEnginePPOTrainer(agent)
    result = trainer.collect_episode(max_turns=5)
    buffer = result["buffer"]
    assert len(buffer) > 0
    
    update_res = trainer.update_from_buffer(buffer)
    assert "policy_loss" in update_res
    assert "value_loss" in update_res
    assert "entropy" in update_res
