from __future__ import annotations

# 게임 엔진 핵심 규칙을 고정하는 테스트 파일
# 오프닝 세팅, 이동, 공격, 카드 효과, 카드 인스턴스 구분, 종료 판정을 우선 검증한다.

from RL_AI.game_engine.engine import apply_action
from RL_AI.game_engine.rules import can_move_unit, can_use_card, get_legal_actions
from RL_AI.game_engine.state import Action, ActionType, GameResult, Phase, PlayerID, Position

from RL_AI.tests.helpers import (
    cards_in_zones,
    clear_board_except,
    move_card_to_hand,
    runtime_unit_for_card_instance,
    runtime_units_for_card_id,
    summon_unit,
)


OR_LEADER = "Or_L"
OR_ROOK = "Or_R"
OR_PAWN = "Or_P"
CL_PAWN = "Cl_P"


def test_opening_setup_places_leaders_and_draws_extra_two_cards_on_turn1(initialized_state):
    state = initialized_state

    p1_leader = state.get_leader_runtime_unit(PlayerID.P1)
    p2_leader = state.get_leader_runtime_unit(PlayerID.P2)

    assert state.turn == 1
    assert state.phase == Phase.MAIN
    assert p1_leader is not None and p1_leader.position == Position(0, 2)
    assert p2_leader is not None and p2_leader.position == Position(5, 3)
    assert len(state.get_player(PlayerID.P1).hand) == 5
    assert len(state.get_player(PlayerID.P2).hand) == 3


def test_pawn_card_instances_remain_distinct_after_one_pawn_is_summoned(initialized_state, card_db):
    state = initialized_state
    p1 = state.get_player(PlayerID.P1)

    pawn_cards = cards_in_zones(state, PlayerID.P1, OR_PAWN)
    p1.hand = list(pawn_cards)
    p1.deck = [card for card in p1.deck if card.card_id != OR_PAWN]
    p1.trash = [card for card in p1.trash if card.card_id != OR_PAWN]

    first_pawn = p1.hand[0]
    second_pawn = p1.hand[1]

    state = apply_action(
        state,
        Action(ActionType.USE_CARD, card_instance_id=first_pawn.instance_id, target_positions=(Position(0, 0),)),
        card_db,
    )

    summoned_unit = runtime_unit_for_card_instance(state, PlayerID.P1, first_pawn.instance_id)
    assert summoned_unit.is_alive()
    assert summoned_unit.position == Position(0, 0)

    illegal_effect_target = state.get_leader_runtime_unit(PlayerID.P2)
    assert illegal_effect_target is not None
    assert not can_use_card(
        state,
        PlayerID.P1,
        second_pawn.instance_id,
        card_db,
        target_unit_ids=(summoned_unit.unit_id, illegal_effect_target.unit_id),
    )
    assert can_use_card(
        state,
        PlayerID.P1,
        second_pawn.instance_id,
        card_db,
        target_positions=(Position(0, 1),),
    )

    second_card_actions = [
        action
        for action in get_legal_actions(state, card_db=card_db)
        if action.card_instance_id == second_pawn.instance_id
    ]
    assert second_card_actions
    assert all(action.target_unit_ids == () for action in second_card_actions)
    assert all(action.target_positions for action in second_card_actions)


def test_pawn_moves_forward_only_once_per_turn(initialized_state, card_db):
    state = initialized_state
    pawn_card = cards_in_zones(state, PlayerID.P1, OR_PAWN)[0]

    state = apply_action(
        state,
        Action(ActionType.USE_CARD, card_instance_id=pawn_card.instance_id, target_positions=(Position(0, 0),)),
        card_db,
    )
    pawn_unit = runtime_unit_for_card_instance(state, PlayerID.P1, pawn_card.instance_id)

    assert can_move_unit(state, PlayerID.P1, pawn_unit.unit_id, Position(1, 0))
    assert not can_move_unit(state, PlayerID.P1, pawn_unit.unit_id, Position(0, 1))
    assert not can_move_unit(state, PlayerID.P1, pawn_unit.unit_id, Position(0, 0))

    state = apply_action(
        state,
        Action(ActionType.MOVE_UNIT, source_unit_id=pawn_unit.unit_id, target_positions=(Position(1, 0),)),
        card_db,
    )

    moved_pawn = state.get_unit(pawn_unit.unit_id)
    assert moved_pawn.position == Position(1, 0)
    assert moved_pawn.moved_this_turn is True
    assert not can_move_unit(state, PlayerID.P1, moved_pawn.unit_id, Position(2, 0))


def test_rook_attack_kills_target_and_marks_attack_used(initialized_state, card_db):
    state = initialized_state
    p1_rook = runtime_units_for_card_id(state, PlayerID.P1, OR_ROOK)[0]
    p2_pawn = runtime_units_for_card_id(state, PlayerID.P2, CL_PAWN)[0]
    p1_leader = state.get_leader_runtime_unit(PlayerID.P1)
    p2_leader = state.get_leader_runtime_unit(PlayerID.P2)
    assert p1_leader is not None and p2_leader is not None

    clear_board_except(state, {p1_rook.unit_id, p2_pawn.unit_id, p1_leader.unit_id, p2_leader.unit_id})
    summon_unit(p1_rook, Position(2, 1))
    summon_unit(p2_pawn, Position(2, 4))

    state = apply_action(
        state,
        Action(ActionType.UNIT_ATTACK, source_unit_id=p1_rook.unit_id, target_unit_ids=(p2_pawn.unit_id,)),
        card_db,
    )

    attacker = state.get_unit(p1_rook.unit_id)
    defender = state.get_unit(p2_pawn.unit_id)
    assert attacker.attacked_this_turn is True
    assert defender.retired is True
    assert defender.is_on_board is False


def test_orange_leader_effect_draws_and_heals_ally(initialized_state, card_db):
    state = initialized_state
    leader = state.get_leader_runtime_unit(PlayerID.P1)
    assert leader is not None
    move_card_to_hand(state, PlayerID.P1, leader.source_card_instance_id)

    pawn_card = cards_in_zones(state, PlayerID.P1, OR_PAWN)[0]
    pawn_unit = runtime_unit_for_card_instance(state, PlayerID.P1, pawn_card.instance_id)
    summon_unit(pawn_unit, Position(0, 0))
    pawn_unit.current_life = 1

    hand_before = len(state.get_player(PlayerID.P1).hand)
    state = apply_action(
        state,
        Action(
            ActionType.USE_CARD,
            card_instance_id=leader.source_card_instance_id,
            target_unit_ids=(pawn_unit.unit_id,),
        ),
        card_db,
    )

    healed_pawn = state.get_unit(pawn_unit.unit_id)
    assert healed_pawn.position == Position(0, 0)
    assert healed_pawn.current_life == 1
    assert len(state.get_player(PlayerID.P1).hand) == hand_before
    assert any(card.instance_id == leader.source_card_instance_id for card in state.get_player(PlayerID.P1).trash)


def test_leader_death_from_attack_ends_game_immediately(initialized_state, card_db):
    state = initialized_state
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

    state = apply_action(
        state,
        Action(ActionType.UNIT_ATTACK, source_unit_id=p1_rook.unit_id, target_unit_ids=(p2_leader.unit_id,)),
        card_db,
    )

    assert state.result == GameResult.P1_WIN
    assert state.winner == PlayerID.P1
    assert state.get_unit(p2_leader.unit_id).retired is True


def test_double_leader_death_is_draw(initialized_state):
    state = initialized_state
    p1_leader = state.get_leader_runtime_unit(PlayerID.P1)
    p2_leader = state.get_leader_runtime_unit(PlayerID.P2)
    assert p1_leader is not None and p2_leader is not None

    p1_leader.retire()
    p2_leader.retire()

    assert state.check_leader_death() == GameResult.DRAW
    assert state.winner is None
