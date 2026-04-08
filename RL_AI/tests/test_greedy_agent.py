from __future__ import annotations

# greedy_agent의 최소 동작을 검증하는 테스트 파일
# 공격 가능 상황에서 턴 종료보다 공격을 고르고, 리더 킬이 가능하면 그 공격을 우선하는지 확인한다.

from RL_AI.agents.greedy_agent import GreedyAgent
from RL_AI.game_engine.rules import get_legal_actions
from RL_AI.game_engine.state import ActionType, PlayerID, Position
from RL_AI.tests.helpers import clear_board_except, runtime_units_for_card_id, summon_unit


OR_ROOK = "Or_R"
CL_PAWN = "Cl_P"


def test_greedy_agent_prefers_attack_over_end_turn(initialized_state, card_db):
    state = initialized_state
    agent = GreedyAgent(seed=1)

    p1_rook = runtime_units_for_card_id(state, PlayerID.P1, OR_ROOK)[0]
    p2_pawn = runtime_units_for_card_id(state, PlayerID.P2, CL_PAWN)[0]
    p1_leader = state.get_leader_runtime_unit(PlayerID.P1)
    p2_leader = state.get_leader_runtime_unit(PlayerID.P2)
    assert p1_leader is not None and p2_leader is not None

    clear_board_except(state, {p1_rook.unit_id, p2_pawn.unit_id, p1_leader.unit_id, p2_leader.unit_id})
    summon_unit(p1_rook, Position(2, 1))
    summon_unit(p2_pawn, Position(2, 4))

    legal_actions = get_legal_actions(state, card_db=card_db)
    action_index, action = agent.select_action(state, legal_actions, card_db=card_db)

    assert legal_actions[action_index] == action
    assert action.action_type == ActionType.UNIT_ATTACK
    assert action.source_unit_id == p1_rook.unit_id
    assert action.target_unit_ids == (p2_pawn.unit_id,)


def test_greedy_agent_prefers_lethal_leader_attack(initialized_state, card_db):
    state = initialized_state
    agent = GreedyAgent(seed=1)

    p1_rook = runtime_units_for_card_id(state, PlayerID.P1, OR_ROOK)[0]
    p1_leader = state.get_leader_runtime_unit(PlayerID.P1)
    p2_leader = state.get_leader_runtime_unit(PlayerID.P2)
    assert p1_leader is not None and p2_leader is not None

    clear_board_except(state, {p1_rook.unit_id, p1_leader.unit_id, p2_leader.unit_id})
    summon_unit(p1_rook, Position(5, 0))
    p2_leader.position = Position(5, 2)
    p2_leader.current_life = 1
    p2_leader.retired = False
    p2_leader.is_on_board = True

    legal_actions = get_legal_actions(state, card_db=card_db)
    action_index, action = agent.select_action(state, legal_actions, card_db=card_db)

    assert legal_actions[action_index] == action
    assert action.action_type == ActionType.UNIT_ATTACK
    assert action.source_unit_id == p1_rook.unit_id
    assert action.target_unit_ids == (p2_leader.unit_id,)
