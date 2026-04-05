from __future__ import annotations

# 학습 전후 에이전트 성능을 비교하기 위한 evaluation 루프 파일
# 여러 판의 agent vs agent 매치를 직접 실행하면서 승/패/무, 평균 스텝 수,
# 행동 타입 분포, 카드 사용 빈도를 함께 집계한다.

from collections import Counter
from typing import Dict, Optional

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.game_engine.engine import apply_action, initialize_main_phase
from RL_AI.game_engine.rules import get_legal_actions
from RL_AI.game_engine.state import ActionType, GameResult, PlayerID, create_initial_game_state, load_supported_card_db


def evaluate_agents(
    p1_agent: BaseAgent,
    p2_agent: BaseAgent,
    *,
    num_matches: int,
    p1_world: int = 1,
    p2_world: int = 2,
    tsv_path: str = "Cards.tsv",
    seed: Optional[int] = None,
    max_steps: int = 500,
) -> Dict[str, object]:
    card_db = load_supported_card_db(tsv_path=tsv_path)

    p1_wins = 0
    p2_wins = 0
    draws = 0
    total_steps = 0
    action_type_counts: Counter[str] = Counter()
    card_use_counts: Counter[str] = Counter()

    for match_index in range(num_matches):
        match_seed = None if seed is None else seed + match_index
        state = create_initial_game_state(
            p1_world=p1_world,
            p2_world=p2_world,
            tsv_path=tsv_path,
            seed=match_seed,
        )
        state = initialize_main_phase(state, card_db)

        steps = 0
        agent_by_player = {
            PlayerID.P1: p1_agent,
            PlayerID.P2: p2_agent,
        }

        while not state.is_terminal() and steps < max_steps:
            legal_actions = get_legal_actions(state, card_db=card_db)
            if not legal_actions:
                break

            acting_agent = agent_by_player[state.active_player]
            _, action = acting_agent.select_action(state, legal_actions, card_db=card_db)

            action_type_counts[action.action_type.value] += 1
            if action.action_type == ActionType.USE_CARD and action.card_instance_id is not None:
                player = state.get_player(state.active_player)
                card = next((c for c in player.hand if c.instance_id == action.card_instance_id), None)
                if card is not None:
                    card_name = card_db.get(card.card_id).name if card.card_id in card_db else card.card_id
                    card_use_counts[card_name] += 1

            state = apply_action(state, action, card_db)
            steps += 1

        total_steps += steps
        if state.result == GameResult.P1_WIN:
            p1_wins += 1
        elif state.result == GameResult.P2_WIN:
            p2_wins += 1
        else:
            draws += 1

    return {
        "episodes": num_matches,
        "p1_agent": p1_agent.name,
        "p2_agent": p2_agent.name,
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "draws": draws,
        "avg_steps": 0.0 if num_matches == 0 else total_steps / num_matches,
        "action_type_counts": dict(sorted(action_type_counts.items())),
        "card_use_counts": dict(card_use_counts.most_common()),
    }
