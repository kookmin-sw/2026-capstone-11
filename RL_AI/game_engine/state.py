#유닛의 상태, 위치, 게임의 기본적 세팅 등을 정의하는 파일

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Tuple
import random
import uuid

from RL_AI.cards.card_db import (
    CardDefinition,
    Role,
    TextCondition,
    load_card_db,
    build_default_deck,
)

# ============================================================
# Fixed assumptions for current prototype
# ============================================================

BOARD_ROWS = 6
BOARD_COLS = 6
HAND_LIMIT_AT_END = 3
MAX_UNITS_PER_PLAYER = 7
MAX_TOTAL_UNITS = 14

SUPPORTED_CARD_IDS = {
    "0x01000000","0x01000100","0x01000200","0x01000300","0x01000400",
    "0x02000000","0x02000100","0x02000200","0x02000300","0x02000400",
}

SUPPORTED_WORLDS = {1, 2}


# ============================================================
# Enums
# ============================================================

class PlayerID(IntEnum):
    P1 = 0
    P2 = 1

    def opponent(self) -> "PlayerID":
        return PlayerID.P2 if self == PlayerID.P1 else PlayerID.P1


class Phase(str, Enum):
    START = "START"
    MAIN = "MAIN"
    END = "END"


class ActionType(str, Enum):
    USE_CARD = "USE_CARD"
    MOVE_UNIT = "MOVE_UNIT"
    UNIT_ATTACK = "UNIT_ATTACK"
    END_TURN = "END_TURN"


class GameResult(str, Enum):
    ONGOING = "ONGOING"
    P1_WIN = "P1_WIN"
    P2_WIN = "P2_WIN"
    DRAW = "DRAW"


# ============================================================
# Value objects
# ============================================================

@dataclass(frozen=True, slots=True)
class Position:
    row: int
    col: int

    def is_in_bounds(self) -> bool:
        return 0 <= self.row < BOARD_ROWS and 0 <= self.col < BOARD_COLS

    def to_tuple(self) -> Tuple[int, int]:
        return (self.row, self.col)

    @classmethod
    def from_tuple(cls, rc: Tuple[int, int]) -> "Position":
        return cls(row=rc[0], col=rc[1])


@dataclass(frozen=True, slots=True)
class CardInstance:
    """
    Runtime card object in deck / hand / trash.

    - card_id: static definition ID
    - instance_id: runtime unique ID
    """
    instance_id: str
    card_id: str
    owner: PlayerID

    def short(self) -> str:
        return f"{self.card_id}:{self.instance_id[:8]}"


@dataclass(slots=True)
class UnitState:
    """
    Runtime unit state.

    Important:
    - State source of truth is the unit list, not a 6x6 board array.
    - Not-yet-summoned units still exist as UnitState, but:
        is_on_board = False
        position = None
        current_life = 0
    """
    unit_id: str
    source_card_instance_id: str
    source_card_id: str

    owner: PlayerID
    leader_name: str
    name: str
    role: Role
    attack: int
    max_life: int

    current_life: int = 0
    position: Optional[Position] = None
    is_on_board: bool = False
    retired: bool = False

    moved_this_turn: bool = False
    attacked_this_turn: bool = False

    promoted: bool = False
    shield: int = 0
    disabled_move_turns: int = 0
    disabled_attack_turns: int = 0

    text_condition: TextCondition = TextCondition.ALWAYS
    text_name: str = ""
    text: str = ""

    def is_alive(self) -> bool:
        return self.is_on_board and not self.retired and self.current_life > 0

    def can_move(self) -> bool:
        return self.is_alive() and not self.moved_this_turn and self.disabled_move_turns <= 0

    def can_attack(self) -> bool:
        return self.is_alive() and not self.attacked_this_turn and self.disabled_attack_turns <= 0

    def summon_to(self, position: Position) -> None:
        if not position.is_in_bounds():
            raise ValueError(f"Position out of bounds: {position}")
        self.position = position
        self.is_on_board = True
        self.retired = False
        self.current_life = self.max_life
        self.moved_this_turn = False
        self.attacked_this_turn = False

    def retire(self) -> None:
        self.position = None
        self.is_on_board = False
        self.retired = True
        self.current_life = 0
        self.moved_this_turn = False
        self.attacked_this_turn = False
        self.shield = 0

    def take_damage(self, amount: int) -> None:
        if not self.is_alive():
            return

        amount = max(0, int(amount))
        if amount == 0:
            return

        if self.shield > 0:
            self.shield -= 1
            return

        self.current_life = max(0, self.current_life - amount)
        if self.current_life == 0:
            self.retire()

    def heal(self, amount: int) -> None:
        if not self.is_alive():
            return

        amount = max(0, int(amount))
        if amount == 0:
            return

        if self.current_life >= self.max_life:
            return

        self.current_life = min(self.max_life, self.current_life + amount)

    def full_heal(self) -> None:
        if self.is_alive():
            self.current_life = self.max_life

    def begin_new_turn(self) -> None:
        if not self.is_alive():
            return

        self.moved_this_turn = False
        self.attacked_this_turn = False

        if self.disabled_move_turns > 0:
            self.disabled_move_turns -= 1
        if self.disabled_attack_turns > 0:
            self.disabled_attack_turns -= 1

    def clone(self) -> "UnitState":
        return UnitState(
            unit_id=self.unit_id,
            source_card_instance_id=self.source_card_instance_id,
            source_card_id=self.source_card_id,
            owner=self.owner,
            leader_name=self.leader_name,
            name=self.name,
            role=self.role,
            attack=self.attack,
            max_life=self.max_life,
            current_life=self.current_life,
            position=None if self.position is None else Position(self.position.row, self.position.col),
            is_on_board=self.is_on_board,
            retired=self.retired,
            moved_this_turn=self.moved_this_turn,
            attacked_this_turn=self.attacked_this_turn,
            promoted=self.promoted,
            shield=self.shield,
            disabled_move_turns=self.disabled_move_turns,
            disabled_attack_turns=self.disabled_attack_turns,
            text_condition=self.text_condition,
            text_name=self.text_name,
            text=self.text,
        )


@dataclass(slots=True)
class PlayerState:
    player_id: PlayerID
    world: int

    deck: List[CardInstance] = field(default_factory=list)
    hand: List[CardInstance] = field(default_factory=list)
    trash: List[CardInstance] = field(default_factory=list)

    leader_card_id: Optional[str] = None

    def all_zone_cards(self) -> List[CardInstance]:
        return [*self.deck, *self.hand, *self.trash]

    def draw_one(self) -> Optional[CardInstance]:
        if not self.deck:
            return None
        card = self.deck.pop(0)
        self.hand.append(card)
        return card

    def remove_from_hand(self, card_instance_id: str) -> CardInstance:
        for i, card in enumerate(self.hand):
            if card.instance_id == card_instance_id:
                return self.hand.pop(i)
        raise ValueError(f"Card instance not found in hand: {card_instance_id}")

    def move_to_trash(self, card: CardInstance) -> None:
        self.trash.append(card)

    def rebuild_deck_from_trash(self, rng: random.Random) -> None:
        if not self.trash:
            return
        self.deck.extend(self.trash)
        self.trash.clear()
        rng.shuffle(self.deck)

    def draw(self, count: int, rng: random.Random) -> List[CardInstance]:
        drawn: List[CardInstance] = []
        for _ in range(max(0, count)):
            if not self.deck:
                self.rebuild_deck_from_trash(rng)
            if not self.deck:
                break
            card = self.draw_one()
            if card is not None:
                drawn.append(card)
        return drawn


@dataclass(frozen=True, slots=True)
class Action:
    """
    Runtime action descriptor.

    Notes:
    - source side is still single for current prototype.
    - target side now supports multi-select.
    - for backward compatibility, singleton convenience properties
      target_unit_id / target_pos are provided.
    """
    action_type: ActionType

    card_instance_id: Optional[str] = None
    source_unit_id: Optional[str] = None
    target_unit_ids: Tuple[str, ...] = ()
    target_positions: Tuple[Position, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_unit_ids", tuple(self.target_unit_ids or ()))
        object.__setattr__(self, "target_positions", tuple(self.target_positions or ()))

        if any(unit_id is None or unit_id == "" for unit_id in self.target_unit_ids):
            raise ValueError("target_unit_ids cannot contain empty values.")

        for pos in self.target_positions:
            if not isinstance(pos, Position):
                raise TypeError("target_positions must contain Position objects.")

    @property
    def target_unit_id(self) -> Optional[str]:
        return self.target_unit_ids[0] if len(self.target_unit_ids) == 1 else None

    @property
    def target_pos(self) -> Optional[Position]:
        return self.target_positions[0] if len(self.target_positions) == 1 else None

    def to_dict(self) -> Dict[str, object]:
        return {
            "action_type": self.action_type.value,
            "card_instance_id": self.card_instance_id,
            "source_unit_id": self.source_unit_id,
            "target_unit_ids": list(self.target_unit_ids),
            "target_positions": [pos.to_tuple() for pos in self.target_positions],
            "target_unit_id": self.target_unit_id,
            "target_pos": None if self.target_pos is None else self.target_pos.to_tuple(),
        }


# ============================================================
# Game state: unit-list as source of truth
# ============================================================

@dataclass(slots=True)
class GameState:
    turn: int
    active_player: PlayerID
    phase: Phase
    result: GameResult = GameResult.ONGOING

    players: Dict[PlayerID, PlayerState] = field(default_factory=dict)

    # Source of truth: all runtime units, including not-yet-summoned units.
    units: Dict[str, UnitState] = field(default_factory=dict)

    winner: Optional[PlayerID] = None
    last_action: Optional[Action] = None

    def is_terminal(self) -> bool:
        return self.result != GameResult.ONGOING

    def get_player(self, player_id: PlayerID) -> PlayerState:
        return self.players[player_id]

    def get_unit(self, unit_id: str) -> UnitState:
        return self.units[unit_id]

    def all_units(self) -> List[UnitState]:
        return list(self.units.values())

    def get_units_by_owner(self, owner: PlayerID) -> List[UnitState]:
        return [u for u in self.units.values() if u.owner == owner]

    def get_board_units(self) -> List[UnitState]:
        return [u for u in self.units.values() if u.is_on_board and not u.retired]

    def get_board_units_by_owner(self, owner: PlayerID) -> List[UnitState]:
        return [u for u in self.units.values() if u.owner == owner and u.is_on_board and not u.retired]

    def get_unit_at(self, pos: Position) -> Optional[UnitState]:
        if not pos.is_in_bounds():
            return None
        for unit in self.units.values():
            if unit.is_on_board and not unit.retired and unit.position == pos:
                return unit
        return None

    def is_empty(self, pos: Position) -> bool:
        return pos.is_in_bounds() and self.get_unit_at(pos) is None

    def move_unit(self, unit_id: str, new_pos: Position) -> None:
        unit = self.units[unit_id]
        if not unit.is_alive():
            raise ValueError(f"Unit is not on board: {unit_id}")
        if not new_pos.is_in_bounds():
            raise ValueError(f"Position out of bounds: {new_pos}")
        if not self.is_empty(new_pos):
            raise ValueError(f"Target cell is occupied: {new_pos}")
        unit.position = new_pos

    def unit_exists_for_card(self, owner: PlayerID, card_id: str) -> bool:
        return any(
            u.owner == owner and u.source_card_id == card_id and u.is_on_board and not u.retired
            for u in self.units.values()
        )

    def get_leader_unit(self, owner: PlayerID) -> Optional[UnitState]:
        for unit in self.units.values():
            if unit.owner == owner and unit.role == Role.LEADER and unit.is_on_board and not unit.retired:
                return unit
        return None

    def get_empty_home_cells(self, owner: PlayerID) -> List[Position]:
        target_row = 0 if owner == PlayerID.P1 else BOARD_ROWS - 1
        result: List[Position] = []
        for col in range(BOARD_COLS):
            pos = Position(target_row, col)
            if self.is_empty(pos):
                result.append(pos)
        return result

    def check_leader_death(self) -> GameResult:
        p1_alive = self.get_leader_unit(PlayerID.P1) is not None
        p2_alive = self.get_leader_unit(PlayerID.P2) is not None

        if not p1_alive and not p2_alive:
            self.result = GameResult.DRAW
            self.winner = None
        elif not p1_alive:
            self.result = GameResult.P2_WIN
            self.winner = PlayerID.P2
        elif not p2_alive:
            self.result = GameResult.P1_WIN
            self.winner = PlayerID.P1
        else:
            self.result = GameResult.ONGOING
            self.winner = None

        return self.result

    def begin_turn_for_active_player(self) -> None:
        for unit in self.get_board_units_by_owner(self.active_player):
            unit.begin_new_turn()
        self.phase = Phase.START

    def advance_phase(self) -> None:
        if self.phase == Phase.START:
            self.phase = Phase.MAIN
        elif self.phase == Phase.MAIN:
            self.phase = Phase.END
        else:
            self.phase = Phase.START
            self.active_player = self.active_player.opponent()
            self.turn += 1

    def clone_shallow(self) -> "GameState":
        return GameState(
            turn=self.turn,
            active_player=self.active_player,
            phase=self.phase,
            result=self.result,
            players={
                pid: PlayerState(
                    player_id=ps.player_id,
                    world=ps.world,
                    deck=list(ps.deck),
                    hand=list(ps.hand),
                    trash=list(ps.trash),
                    leader_card_id=ps.leader_card_id,
                )
                for pid, ps in self.players.items()
            },
            units={uid: unit.clone() for uid, unit in self.units.items()},
            winner=self.winner,
            last_action=self.last_action,
        )


# ============================================================
# Factory helpers
# ============================================================

def _new_instance_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def validate_supported_card_db(card_db: Dict[str, CardDefinition]) -> Dict[str, CardDefinition]:
    filtered = {cid: c for cid, c in card_db.items() if cid in SUPPORTED_CARD_IDS}
    missing = SUPPORTED_CARD_IDS - set(filtered.keys())
    extra_worlds = {c.world for c in filtered.values()} - SUPPORTED_WORLDS

    if missing:
        raise ValueError(f"Missing required prototype cards: {sorted(missing)}")
    if extra_worlds:
        raise ValueError(f"Unsupported worlds found: {sorted(extra_worlds)}")

    return filtered


def load_supported_card_db(xlsx_path: str = "Cards.xlsx") -> Dict[str, CardDefinition]:
    db = load_card_db(xlsx_path=xlsx_path)
    return validate_supported_card_db(db)


def create_card_instance(card_id: str, owner: PlayerID) -> CardInstance:
    if card_id not in SUPPORTED_CARD_IDS:
        raise ValueError(f"Unsupported card_id for current prototype: {card_id}")
    return CardInstance(
        instance_id=_new_instance_id("card"),
        card_id=card_id,
        owner=owner,
    )


def build_player_deck_instances(
    world: int,
    owner: PlayerID,
    card_db: Dict[str, CardDefinition],
    rng: Optional[random.Random] = None,
) -> List[CardInstance]:
    if world not in SUPPORTED_WORLDS:
        raise ValueError(f"Unsupported world: {world}")

    deck_card_ids = build_default_deck(card_db, world)
    deck = [create_card_instance(card_id=cid, owner=owner) for cid in deck_card_ids]

    if rng is not None:
        rng.shuffle(deck)

    return deck


def create_unit_from_card_instance(
    card_def: CardDefinition,
    card_instance: CardInstance,
    owner: PlayerID,
) -> UnitState:
    return UnitState(
        unit_id=_new_instance_id("unit"),
        source_card_instance_id=card_instance.instance_id,
        source_card_id=card_def.card_id,
        owner=owner,
        leader_name=card_def.name if card_def.role == Role.LEADER else f"World{card_def.world}",
        name=card_def.name,
        role=card_def.role,
        attack=card_def.attack,
        max_life=card_def.life,
        current_life=0,
        position=None,
        is_on_board=False,
        retired=False,
        text_condition=card_def.text_condition,
        text_name=card_def.text_name,
        text=card_def.text,
    )


def create_initial_player_state(
    player_id: PlayerID,
    world: int,
    card_db: Dict[str, CardDefinition],
    rng: Optional[random.Random] = None,
) -> PlayerState:
    deck = build_player_deck_instances(world=world, owner=player_id, card_db=card_db, rng=rng)
    leader_card_id = next(
        c.card_id for c in card_db.values()
        if c.world == world and c.role == Role.LEADER
    )
    return PlayerState(
        player_id=player_id,
        world=world,
        deck=deck,
        hand=[],
        trash=[],
        leader_card_id=leader_card_id,
    )


def create_initial_units_for_player(
    player_id: PlayerID,
    world: int,
    player_state: PlayerState,
    card_db: Dict[str, CardDefinition],
) -> List[UnitState]:
    """
    Build exactly 7 unit states from the player's starting deck definition.
    These units exist from game start as runtime objects, but are not on board yet.
    """
    units: List[UnitState] = []

    all_cards = [*player_state.deck, *player_state.hand, *player_state.trash]
    if len(all_cards) != MAX_UNITS_PER_PLAYER:
        raise ValueError(
            f"Expected {MAX_UNITS_PER_PLAYER} cards for player {player_id}, got {len(all_cards)}"
        )

    for card_instance in all_cards:
        card_def = card_db[card_instance.card_id]
        units.append(create_unit_from_card_instance(card_def, card_instance, player_id))

    return units


def create_initial_game_state(
    p1_world: int,
    p2_world: int,
    xlsx_path: str = "Cards.xlsx",
    seed: Optional[int] = None,
    first_player: Optional[PlayerID] = None,
) -> GameState:
    rng = random.Random(seed)
    card_db = load_supported_card_db(xlsx_path)

    p1 = create_initial_player_state(PlayerID.P1, p1_world, card_db, rng)
    p2 = create_initial_player_state(PlayerID.P2, p2_world, card_db, rng)

    if first_player is None:
        active_player = rng.choice([PlayerID.P1, PlayerID.P2])
    else:
        active_player = first_player

    p1_units = create_initial_units_for_player(PlayerID.P1, p1_world, p1, card_db)
    p2_units = create_initial_units_for_player(PlayerID.P2, p2_world, p2, card_db)

    all_units = p1_units + p2_units
    if len(all_units) != MAX_TOTAL_UNITS:
        raise ValueError(f"Expected {MAX_TOTAL_UNITS} total units, got {len(all_units)}")

    state = GameState(
        turn=1,
        active_player=active_player,
        phase=Phase.START,
        players={
            PlayerID.P1: p1,
            PlayerID.P2: p2,
        },
        units={u.unit_id: u for u in all_units},
    )
    return state


# ============================================================
# Debug helpers
# ============================================================

def get_sorted_units_for_observation(state: GameState) -> List[UnitState]:
    """
    Stable unit ordering for observation vectorization.
    Recommended order:
    - P1 units first, then P2 units
    - within player: Leader, Rook, Knight, Bishop, Pawn, Pawn, Pawn
    - tie-break with unit_id
    """
    role_order = {
        Role.LEADER: 0,
        Role.ROOK: 1,
        Role.KNIGHT: 2,
        Role.BISHOP: 3,
        Role.PAWN: 4,
    }

    return sorted(
        state.units.values(),
        key=lambda u: (
            int(u.owner),
            role_order.get(u.role, 99),
            u.name,
            u.unit_id,
        ),
    )


def occupied_positions(state: GameState) -> Dict[Tuple[int, int], str]:
    """
    Optional helper for rule checks.
    Returns {(row, col): unit_id}
    """
    out: Dict[Tuple[int, int], str] = {}
    for unit in state.get_board_units():
        assert unit.position is not None
        out[unit.position.to_tuple()] = unit.unit_id
    return out
