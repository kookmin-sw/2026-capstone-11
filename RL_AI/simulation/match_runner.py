#케임에 대한 간단한 CLI 매치 루프 프로토타입
#상태, 규칙, 엔진, debug)view를 연결해서 사람이 보드를 확인하고 행동을 선택
#self-play, 로깅, RL 학습 이전에 수동으로 실행함

from __future__ import annotations

import random
from typing import List, Optional, Sequence

from RL_AI.game_engine.engine import apply_action, initialize_main_phase
from RL_AI.game_engine.rules import get_legal_actions
from RL_AI.game_engine.state import Action, GameState, PlayerID, create_initial_game_state, load_supported_card_db
from RL_AI.simulation.debug_view import describe_action_local, print_state


class MatchRunner:
    def __init__(self, state: GameState, card_db, seed: Optional[int] = None):
        self.state = state
        self.card_db = card_db
        self.rng = random.Random(seed)

    def initialize(self) -> None:
        self.state = initialize_main_phase(self.state, self.card_db, self.rng)

    def get_legal_actions(self) -> List[Action]:
        return get_legal_actions(self.state, card_db=self.card_db)

    def step(self, action: Action) -> GameState:
        self.state = apply_action(self.state, action, self.card_db, self.rng)
        return self.state

    def is_done(self) -> bool:
        return self.state.is_terminal()

    def current_player(self) -> PlayerID:
        return self.state.active_player


def choose_action_by_index(state: GameState, legal_actions: Sequence[Action]) -> Action:
    while True:
        raw = input("Select action index (or 'q' to quit): ").strip()
        if raw.lower() in {"q", "quit", "exit"}:
            raise KeyboardInterrupt
        if not raw.isdigit():
            print("Please enter a valid action index.")
            continue

        idx = int(raw)
        if 0 <= idx < len(legal_actions):
            return legal_actions[idx]
        print(f"Index out of range. Enter 0 ~ {len(legal_actions) - 1}.")


def choose_action_randomly(legal_actions: Sequence[Action], rng: random.Random) -> Action:
    return rng.choice(list(legal_actions))


def run_manual_match(
    p1_world: int = 1,
    p2_world: int = 2,
    *,
    seed: Optional[int] = None,
    xlsx_path: str = "Cards.xlsx",
    first_player: Optional[PlayerID] = None,
) -> GameState:
    card_db = load_supported_card_db(xlsx_path=xlsx_path)
    initial_state = create_initial_game_state(
        p1_world=p1_world,
        p2_world=p2_world,
        xlsx_path=xlsx_path,
        seed=seed,
        first_player=first_player,
    )

    runner = MatchRunner(initial_state, card_db, seed=seed)
    runner.initialize()

    while not runner.is_done():
        legal_actions = runner.get_legal_actions()
        print_state(runner.state, legal_actions, runner.card_db)

        if not legal_actions:
            print("No legal actions available. Stopping match.")
            break

        action = choose_action_by_index(runner.state, legal_actions)
        print("Chosen:", describe_action_local(runner.state, action, runner.card_db))
        runner.step(action)
        print("\n" + "=" * 100 + "\n")

    print_state(runner.state, card_db=runner.card_db)
    print("Match finished.")
    return runner.state


def run_random_match(
    p1_world: int = 1,
    p2_world: int = 2,
    *,
    seed: Optional[int] = None,
    xlsx_path: str = "Cards.xlsx",
    first_player: Optional[PlayerID] = None,
    max_steps: int = 500,
) -> GameState:
    card_db = load_supported_card_db(xlsx_path=xlsx_path)
    initial_state = create_initial_game_state(
        p1_world=p1_world,
        p2_world=p2_world,
        xlsx_path=xlsx_path,
        seed=seed,
        first_player=first_player,
    )

    runner = MatchRunner(initial_state, card_db, seed=seed)
    runner.initialize()

    steps = 0
    while not runner.is_done() and steps < max_steps:
        legal_actions = runner.get_legal_actions()
        if not legal_actions:
            print("No legal actions available. Stopping match.")
            break
        action = choose_action_randomly(legal_actions, runner.rng)
        print(f"[step {steps}] {describe_action_local(runner.state, action, runner.card_db)}")
        runner.step(action)
        steps += 1

    print_state(runner.state, card_db=runner.card_db)
    print(f"Random match finished after {steps} steps.")
    return runner.state


if __name__ == "__main__":
    run_manual_match(p1_world=1, p2_world=2, seed=7)
