from __future__ import annotations

# 테스트에서 반복되는 상태 조작을 모아 둔 헬퍼 파일
# 카드 인스턴스 찾기, 보드 정리, 강제 소환 같은 테스트용 보조 함수만 정의한다.

from typing import Iterable, List

from RL_AI.game_engine.state import GameState, PlayerID, Position


def cards_in_zones(state: GameState, owner: PlayerID, card_id: str) -> List[object]:
    player = state.get_player(owner)
    found = []
    for zone_name in ("hand", "deck", "trash"):
        for card in getattr(player, zone_name):
            if card.card_id == card_id:
                found.append(card)
    return found


def runtime_units_for_card_id(state: GameState, owner: PlayerID, card_id: str):
    return [
        unit
        for unit in state.units.values()
        if unit.owner == owner and unit.source_card_id == card_id
    ]


def runtime_unit_for_card_instance(state: GameState, owner: PlayerID, card_instance_id: str):
    for unit in state.units.values():
        if unit.owner == owner and unit.source_card_instance_id == card_instance_id:
            return unit
    raise AssertionError(f"Runtime unit not found for card instance {card_instance_id}")


def move_card_to_hand(state: GameState, owner: PlayerID, card_instance_id: str) -> None:
    player = state.get_player(owner)
    for zone_name in ("deck", "trash"):
        zone = getattr(player, zone_name)
        for index, card in enumerate(zone):
            if card.instance_id == card_instance_id:
                player.hand.append(zone.pop(index))
                return
    if any(card.instance_id == card_instance_id for card in player.hand):
        return
    raise AssertionError(f"Card instance not found in any movable zone: {card_instance_id}")


def summon_unit(unit, pos: Position) -> None:
    unit.summon_to(pos)
    unit.moved_this_turn = False
    unit.attacked_this_turn = False


def clear_board_except(state: GameState, keep_unit_ids: Iterable[str]) -> None:
    keep = set(keep_unit_ids)
    for unit in state.units.values():
        if unit.unit_id not in keep and unit.is_alive():
            unit.retire()
