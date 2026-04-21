from __future__ import annotations

# legal action 목록이 불법 액션을 섞지 않고, 중복 없이, 빠진 합법 액션 없이 생성되는지 한 번에 검증하는 테스트 파일
# get_legal_actions 결과를 테스트 전용 전수 생성 오라클과 직접 비교해 soundness, uniqueness, completeness를 함께 확인한다.

import json
import random
from itertools import permutations

from RL_AI.agents.greedy_agent import GreedyAgent
from RL_AI.agents.random_agent import RandomAgent
from RL_AI.game_engine.engine import apply_action, initialize_main_phase
from RL_AI.game_engine.rules import describe_action, get_legal_actions, is_legal_action
from RL_AI.game_engine.state import Action, ActionType, PlayerID, Position, create_initial_game_state


def _action_key(action: Action) -> str:
    return json.dumps(action.to_dict(), sort_keys=True, ensure_ascii=False)


def _all_positions():
    return [Position(row, col) for row in range(6) for col in range(6)]


def _ordered_unit_target_tuples(unit_ids: list[str]) -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = [()]
    out.extend((unit_id,) for unit_id in unit_ids)
    out.extend(permutations(unit_ids, 2))
    return out


def _enumerate_legal_actions_by_oracle(state, card_db) -> dict[str, Action]:
    owner = state.active_player
    player = state.get_player(owner)
    board_unit_ids = [unit.unit_id for unit in state.get_board_units()]
    oracle: dict[str, Action] = {}

    def add_if_legal(action: Action) -> None:
        if is_legal_action(state, owner, action, card_db=card_db):
            oracle[_action_key(action)] = action

    add_if_legal(Action(ActionType.END_TURN))

    for unit in state.units.values():
        for pos in _all_positions():
            add_if_legal(Action(ActionType.MOVE_UNIT, source_unit_id=unit.unit_id, target_positions=(pos,)))

    for attacker in state.units.values():
        for defender in state.units.values():
            add_if_legal(Action(ActionType.UNIT_ATTACK, source_unit_id=attacker.unit_id, target_unit_ids=(defender.unit_id,)))

    ordered_unit_targets = _ordered_unit_target_tuples(board_unit_ids)
    ordered_position_targets = [()] + [(pos,) for pos in _all_positions()]

    for card in player.hand:
        for target_units in ordered_unit_targets:
            for target_positions in ordered_position_targets:
                add_if_legal(
                    Action(
                        ActionType.USE_CARD,
                        card_instance_id=card.instance_id,
                        target_unit_ids=target_units,
                        target_positions=target_positions,
                    )
                )

    return oracle


def _assert_legal_action_generation_is_correct(state, card_db) -> None:
    actual_actions = get_legal_actions(state, card_db=card_db)
    assert actual_actions, "An ongoing main phase should provide at least one legal action."

    actual_keys = [_action_key(action) for action in actual_actions]
    assert len(actual_keys) == len(set(actual_keys)), "get_legal_actions returned duplicate actions."

    for action in actual_actions:
        assert is_legal_action(state, state.active_player, action, card_db=card_db), (
            f"Illegal action returned by get_legal_actions: {describe_action(state, action)}"
        )
        next_state = apply_action(state, action, card_db, rng=random.Random(0))
        assert next_state.last_action == action

    oracle_actions = _enumerate_legal_actions_by_oracle(state, card_db)
    actual_action_map = {key: action for key, action in zip(actual_keys, actual_actions)}

    missing_keys = sorted(set(oracle_actions) - set(actual_action_map))
    unexpected_keys = sorted(set(actual_action_map) - set(oracle_actions))

    missing_text = [describe_action(state, oracle_actions[key]) for key in missing_keys[:10]]
    unexpected_text = [describe_action(state, actual_action_map[key]) for key in unexpected_keys[:10]]

    assert not missing_keys and not unexpected_keys, (
        "Legal action set mismatch. "
        f"missing={missing_text} unexpected={unexpected_text}"
    )


def test_legal_action_generation_matches_oracle_on_initial_state(initialized_state, card_db):
    _assert_legal_action_generation_is_correct(initialized_state, card_db)


def test_legal_action_generation_matches_oracle_after_basic_summon(initialized_state, card_db):
    state = initialized_state
    summon_action = next(
        action
        for action in get_legal_actions(state, card_db=card_db)
        if action.action_type == ActionType.USE_CARD and action.target_positions and not action.target_unit_ids
    )
    state = apply_action(state, summon_action, card_db, rng=random.Random(1))
    _assert_legal_action_generation_is_correct(state, card_db)


def test_legal_action_generation_matches_oracle_on_sampled_match_states(card_db):
    p1_agent = RandomAgent(seed=1)
    p2_agent = GreedyAgent(seed=2)
    state = create_initial_game_state(p1_world=2, p2_world=6, first_player=PlayerID.P1, seed=7)
    state = initialize_main_phase(state, card_db, rng=random.Random(7))

    agent_by_player = {
        PlayerID.P1: p1_agent,
        PlayerID.P2: p2_agent,
    }

    checked_states = 0
    while not state.is_terminal() and checked_states < 8:
        _assert_legal_action_generation_is_correct(state, card_db)
        legal_actions = get_legal_actions(state, card_db=card_db)
        _, chosen_action = agent_by_player[state.active_player].select_action(state, legal_actions, card_db=card_db)
        state = apply_action(state, chosen_action, card_db, rng=random.Random(checked_states + 10))
        checked_states += 1

    assert checked_states == 8

