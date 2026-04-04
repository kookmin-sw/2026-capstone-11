#케임에 대한 간단한 CLI 매치 루프 프로토타입
#상태, 규칙, 엔진, debug)view를 연결해서 사람이 보드를 확인하고 행동을 선택
#self-play, 로깅, RL 학습 이전에 수동으로 실행함

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.game_engine.engine import apply_action, initialize_main_phase
from RL_AI.game_engine.rules import get_legal_actions
from RL_AI.game_engine.state import Action, GameState, PlayerID, create_initial_game_state, load_supported_card_db
from RL_AI.simulation.debug_view import describe_action_local, print_state
from RL_AI.simulation.logging import MatchLogger


def _default_log_base(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(__file__).resolve().parent.parent / "log"
    return str(log_dir / f"{prefix}_{ts}")


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


def choose_action_by_index(state: GameState, legal_actions: Sequence[Action]) -> tuple[int, Action]:
    while True:
        raw = input("Select action index (or 'q' to quit): ").strip()
        if raw.lower() in {"q", "quit", "exit"}:
            raise KeyboardInterrupt
        if not raw.isdigit():
            print("Please enter a valid action index.")
            continue

        idx = int(raw)
        if 0 <= idx < len(legal_actions):
            return idx, legal_actions[idx]
        print(f"Index out of range. Enter 0 ~ {len(legal_actions) - 1}.")


def choose_action_randomly(legal_actions: Sequence[Action], rng: random.Random) -> tuple[int, Action]:
    idx = rng.randrange(len(legal_actions))
    return idx, legal_actions[idx]


def choose_action_with_agent(
    agent: BaseAgent,
    state: GameState,
    legal_actions: Sequence[Action],
    *,
    card_db,
) -> tuple[int, Action]:
    return agent.select_action(state, legal_actions, card_db=card_db)


def _build_match_metadata(
    *,
    p1_world: int,
    p2_world: int,
    seed: Optional[int],
    first_player: Optional[PlayerID],
    mode: str,
    max_steps: Optional[int] = None,
) -> dict:
    meta = {
        "mode": mode,
        "p1_world": p1_world,
        "p2_world": p2_world,
        "seed": seed,
        "first_player": None if first_player is None else ("P1" if first_player == PlayerID.P1 else "P2"),
    }
    if max_steps is not None:
        meta["max_steps"] = max_steps
    return meta


def run_manual_match(
    p1_world: int = 1,
    p2_world: int = 2,
    *,
    seed: Optional[int] = None,
    tsv_path: str = "Cards.tsv",
    first_player: Optional[PlayerID] = None,
    enable_logging: bool = True,
    log_base_path: Optional[str] = None,
    include_action_options_in_log: bool = False,
) -> GameState:
    card_db = load_supported_card_db(tsv_path=tsv_path)
    initial_state = create_initial_game_state(
        p1_world=p1_world,
        p2_world=p2_world,
        tsv_path=tsv_path,
        seed=seed,
        first_player=first_player,
    )

    runner = MatchRunner(initial_state, card_db, seed=seed)
    runner.initialize()

    logger: Optional[MatchLogger] = None
    if enable_logging:
        logger = MatchLogger(
            log_base_path or _default_log_base("manual_match"),
            card_db=card_db,
            save_text_log=True,
            include_action_options=include_action_options_in_log,
        )
        logger.log_match_start(
            runner.state,
            metadata=_build_match_metadata(
                p1_world=p1_world,
                p2_world=p2_world,
                seed=seed,
                first_player=first_player,
                mode="manual",
            ),
        )

    while not runner.is_done():
        legal_actions = runner.get_legal_actions()
        print_state(runner.state, legal_actions, runner.card_db)

        if logger is not None:
            logger.log_action_options(runner.state, legal_actions)

        if not legal_actions:
            print("No legal actions available. Stopping match.")
            if logger is not None:
                logger.log_event(
                    "no_legal_actions",
                    turn=runner.state.turn,
                    active_player=("P1" if runner.state.active_player == PlayerID.P1 else "P2"),
                    phase=(runner.state.phase.value if hasattr(runner.state.phase, "value") else str(runner.state.phase)),
                )
                logger.log_state_checkpoint(runner.state, note="no_legal_actions")
            break

        try:
            action_index, action = choose_action_by_index(runner.state, legal_actions)
        except KeyboardInterrupt:
            print("\nMatch interrupted by user.")
            if logger is not None:
                logger.log_event(
                    "manual_interrupt",
                    turn=runner.state.turn,
                    active_player=("P1" if runner.state.active_player == PlayerID.P1 else "P2"),
                )
                logger.log_match_end(runner.state, metadata={"interrupted": True})
            raise

        print("Chosen:", describe_action_local(runner.state, action))

        if logger is not None:
            logger.log_action_chosen(runner.state, action, action_index=action_index)

        runner.step(action)

        if logger is not None:
            logger.log_state_checkpoint(runner.state)

        print("\n" + "=" * 100 + "\n")

    print_state(runner.state, card_db=runner.card_db)

    if logger is not None:
        logger.log_match_end(runner.state)
        print(f"Logs written to: {logger.jsonl_path} and {logger.text_path}")

    print("Match finished.")
    return runner.state


def run_random_match(
    p1_world: int = 1,
    p2_world: int = 2,
    *,
    seed: Optional[int] = None,
    tsv_path: str = "Cards.tsv",
    first_player: Optional[PlayerID] = None,
    max_steps: int = 500,
    enable_logging: bool = True,
    log_base_path: Optional[str] = None,
    print_steps: bool = True,
    include_action_options_in_log: bool = False,
) -> GameState:
    card_db = load_supported_card_db(tsv_path=tsv_path)
    initial_state = create_initial_game_state(
        p1_world=p1_world,
        p2_world=p2_world,
        tsv_path=tsv_path,
        seed=seed,
        first_player=first_player,
    )

    runner = MatchRunner(initial_state, card_db, seed=seed)
    runner.initialize()

    logger: Optional[MatchLogger] = None
    if enable_logging:
        logger = MatchLogger(
            log_base_path or _default_log_base("random_match"),
            card_db=card_db,
            save_text_log=True,
            include_action_options=include_action_options_in_log,
        )
        logger.log_match_start(
            runner.state,
            metadata=_build_match_metadata(
                p1_world=p1_world,
                p2_world=p2_world,
                seed=seed,
                first_player=first_player,
                mode="random",
                max_steps=max_steps,
            ),
        )

    steps = 0
    while not runner.is_done() and steps < max_steps:
        legal_actions = runner.get_legal_actions()

        if logger is not None:
            logger.log_action_options(runner.state, legal_actions)

        if not legal_actions:
            print("No legal actions available. Stopping match.")
            if logger is not None:
                logger.log_event(
                    "no_legal_actions",
                    turn=runner.state.turn,
                    active_player=("P1" if runner.state.active_player == PlayerID.P1 else "P2"),
                    phase=(runner.state.phase.value if hasattr(runner.state.phase, "value") else str(runner.state.phase)),
                )
                logger.log_state_checkpoint(runner.state, note="no_legal_actions")
            break

        action_index, action = choose_action_randomly(legal_actions, runner.rng)

        if print_steps:
            print(f"[step {steps}] {describe_action_local(runner.state, action)}")

        if logger is not None:
            logger.log_action_chosen(runner.state, action, action_index=action_index)

        runner.step(action)

        if logger is not None:
            logger.log_state_checkpoint(runner.state, note=f"random_step={steps}")

        steps += 1

    if steps >= max_steps and not runner.is_done():
        if logger is not None:
            logger.log_event("max_steps_reached", max_steps=max_steps)
            logger.log_state_checkpoint(runner.state, note="max_steps_reached")

    print_state(runner.state, card_db=runner.card_db)

    if logger is not None:
        logger.log_match_end(runner.state, metadata={"steps": steps})
        print(f"Logs written to: {logger.jsonl_path} and {logger.text_path}")

    print(f"Random match finished after {steps} steps.")
    return runner.state


def run_agent_match(
    p1_agent: BaseAgent,
    p2_agent: BaseAgent,
    *,
    p1_world: int = 1,
    p2_world: int = 2,
    seed: Optional[int] = None,
    tsv_path: str = "Cards.tsv",
    first_player: Optional[PlayerID] = None,
    max_steps: int = 500,
    enable_logging: bool = True,
    log_base_path: Optional[str] = None,
    print_steps: bool = True,
    include_action_options_in_log: bool = False,
) -> GameState:
    card_db = load_supported_card_db(tsv_path=tsv_path)
    initial_state = create_initial_game_state(
        p1_world=p1_world,
        p2_world=p2_world,
        tsv_path=tsv_path,
        seed=seed,
        first_player=first_player,
    )

    runner = MatchRunner(initial_state, card_db, seed=seed)
    runner.initialize()

    logger: Optional[MatchLogger] = None
    if enable_logging:
        logger = MatchLogger(
            log_base_path or _default_log_base("agent_match"),
            card_db=card_db,
            save_text_log=True,
            include_action_options=include_action_options_in_log,
        )
        logger.log_match_start(
            runner.state,
            metadata={
                **_build_match_metadata(
                    p1_world=p1_world,
                    p2_world=p2_world,
                    seed=seed,
                    first_player=first_player,
                    mode="agent_vs_agent",
                    max_steps=max_steps,
                ),
                "p1_agent": p1_agent.name,
                "p2_agent": p2_agent.name,
            },
        )

    agent_by_player = {
        PlayerID.P1: p1_agent,
        PlayerID.P2: p2_agent,
    }

    steps = 0
    while not runner.is_done() and steps < max_steps:
        legal_actions = runner.get_legal_actions()

        if logger is not None:
            logger.log_action_options(runner.state, legal_actions)

        if not legal_actions:
            print("No legal actions available. Stopping match.")
            if logger is not None:
                logger.log_event(
                    "no_legal_actions",
                    turn=runner.state.turn,
                    active_player=("P1" if runner.state.active_player == PlayerID.P1 else "P2"),
                    phase=(runner.state.phase.value if hasattr(runner.state.phase, "value") else str(runner.state.phase)),
                )
                logger.log_state_checkpoint(runner.state, note="no_legal_actions")
            break

        acting_agent = agent_by_player[runner.current_player()]
        action_index, action = choose_action_with_agent(
            acting_agent,
            runner.state,
            legal_actions,
            card_db=runner.card_db,
        )

        if print_steps:
            print(f"[step {steps}] {acting_agent.name}: {describe_action_local(runner.state, action)}")

        if logger is not None:
            logger.log_action_chosen(runner.state, action, action_index=action_index)

        runner.step(action)

        if logger is not None:
            logger.log_state_checkpoint(runner.state, note=f"agent_step={steps}")

        steps += 1

    if steps >= max_steps and not runner.is_done():
        if logger is not None:
            logger.log_event("max_steps_reached", max_steps=max_steps)
            logger.log_state_checkpoint(runner.state, note="max_steps_reached")

    if print_steps:
        print_state(runner.state, card_db=runner.card_db)

    if logger is not None:
        logger.log_match_end(
            runner.state,
            metadata={
                "steps": steps,
                "p1_agent": p1_agent.name,
                "p2_agent": p2_agent.name,
            },
        )
        print(f"Logs written to: {logger.jsonl_path} and {logger.text_path}")

    print(f"Agent match finished after {steps} steps.")
    return runner.state


if __name__ == "__main__":
    # Manual play:
    #   python -m RL_AI.simulation.match_runner
    #
    # Random rollout from Python:
    #   from RL_AI.simulation.match_runner import run_random_match
    #   run_random_match(seed=7)
    run_manual_match(p1_world=1, p2_world=2, seed=7)
