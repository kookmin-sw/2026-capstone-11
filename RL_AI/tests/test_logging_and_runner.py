from __future__ import annotations

# match_runner와 lightweight logging의 최소 계약을 확인하는 테스트 파일
# 랜덤 매치 실행 후 compact JSONL/TXT 기보 로그가 생성되는지만 우선 검증한다.

import json

from RL_AI.simulation.match_runner import run_random_match


def test_random_match_writes_compact_notation_logs(tmp_path):
    log_base = tmp_path / "random_match_smoke"

    run_random_match(
        seed=7,
        max_steps=5,
        enable_logging=True,
        log_base_path=str(log_base),
        print_steps=False,
        include_action_options_in_log=False,
    )

    jsonl_path = log_base.with_suffix(".jsonl")
    txt_path = log_base.with_suffix(".txt")

    assert jsonl_path.exists()
    assert txt_path.exists()

    records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [record["event_type"] for record in records]
    assert event_types[0] == "match_start"
    assert "action_chosen" in event_types
    assert "state_checkpoint" in event_types
    assert event_types[-1] == "match_end"
    assert "legal_actions" not in event_types

    text_log = txt_path.read_text(encoding="utf-8")
    assert "=== MATCH START ===" in text_log
    assert "=== MATCH END ===" in text_log
    assert "T1 " in text_log
