from __future__ import annotations

# pytest 공통 fixture를 모아 두는 파일
# 카드 DB 로드와 초기 GameState 생성처럼 여러 테스트가 공유하는 기본 셋업만 담당한다.

import pytest

from RL_AI.game_engine.engine import initialize_main_phase
from RL_AI.game_engine.state import GameState, PlayerID, create_initial_game_state, load_supported_card_db


@pytest.fixture(scope="session")
def card_db():
    return load_supported_card_db()


@pytest.fixture
def initialized_state(card_db) -> GameState:
    state = create_initial_game_state(
        p1_world=1,
        p2_world=2,
        first_player=PlayerID.P1,
        seed=7,
    )
    return initialize_main_phase(state, card_db)
