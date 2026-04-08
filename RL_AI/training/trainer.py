from __future__ import annotations

# PPO 학습 루프를 담당하는 파일
# rollout 수집, terminal reward 부여, return/advantage 계산, PPO 업데이트를 한 곳에서 연결한다.

from dataclasses import dataclass
from typing import Dict, Optional

import torch

from RL_AI.agents.base_agent import BaseAgent
from RL_AI.agents.random_agent import RandomAgent
from RL_AI.agents.rl_agent import RLAgent
from RL_AI.analysis.reports import build_win_rate_report
from RL_AI.game_engine.engine import initialize_main_phase
from RL_AI.game_engine.rules import get_legal_actions
from RL_AI.game_engine.state import GameResult, PlayerID, create_initial_game_state, load_supported_card_db
from RL_AI.training.evaluator import evaluate_agents
from RL_AI.training.reward import terminal_reward_for_player
from RL_AI.training.storage import RolloutBuffer, RolloutStep


@dataclass
class PPOConfig:
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_loss_coef: float = 0.5
    entropy_coef: float = 0.01
    update_epochs: int = 4
    max_grad_norm: float = 0.5


class PPOTrainer:
    def __init__(self, agent: RLAgent, config: Optional[PPOConfig] = None) -> None:
        self.agent = agent
        self.config = PPOConfig() if config is None else config

    def collect_episode(
        self,
        *,
        episode_id: int = 0,
        opponent_agent: Optional[BaseAgent] = None,
        p1_world: int = 2,
        p2_world: int = 6,
        card_data_path: str = "Cards.csv",
        seed: Optional[int] = None,
        first_player: Optional[PlayerID] = None,
        max_steps: int = 500,
    ) -> Dict[str, object]:
        card_db = load_supported_card_db(card_data_path=card_data_path)
        state = create_initial_game_state(
            p1_world=p1_world,
            p2_world=p2_world,
            card_data_path=card_data_path,
            seed=seed,
            first_player=first_player,
        )
        state = initialize_main_phase(state, card_db)

        buffer = RolloutBuffer()
        opponent = RandomAgent(seed=seed) if opponent_agent is None else opponent_agent

        steps = 0
        while not state.is_terminal() and steps < max_steps:
            legal_actions = get_legal_actions(state, card_db=card_db)
            if not legal_actions:
                break

            acting_player = state.active_player
            acting_agent: BaseAgent = self.agent if acting_player == PlayerID.P1 else opponent

            if acting_agent is self.agent:
                output = self.agent.compute_policy_output(state, legal_actions, card_db=card_db)
                buffer.add_step(
                    RolloutStep(
                        episode_id=episode_id,
                        player_id=int(acting_player),
                        state_vector=output.state_vector,
                        action_feature_vectors=output.action_feature_vectors,
                        chosen_action_index=output.action_index,
                        reward=0.0,
                        done=False,
                        old_log_prob=output.log_prob,
                        old_value=output.value,
                    )
                )
                action = output.action
            else:
                _, action = acting_agent.select_action(state, legal_actions, card_db=card_db)

            from RL_AI.game_engine.engine import apply_action  # local import to avoid widening module coupling
            state = apply_action(state, action, card_db)
            steps += 1

        self._assign_terminal_rewards(buffer, state.result)
        buffer.compute_returns_and_advantages(self.config.gamma, self.config.gae_lambda)

        return {
            "buffer": buffer,
            "result": state.result,
            "steps": steps,
        }

    def update_from_buffer(self, buffer: RolloutBuffer) -> Dict[str, float]:
        if len(buffer) == 0:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        if self.agent.optimizer is None:
            self.agent.ensure_model(state_dim=len(buffer.steps[0].state_vector))
        assert self.agent.optimizer is not None

        normalized_advantages = buffer.normalized_advantages()
        policy_loss_total = 0.0
        value_loss_total = 0.0
        entropy_total = 0.0
        update_count = 0

        for _ in range(self.config.update_epochs):
            for step, norm_advantage in zip(buffer.steps, normalized_advantages):
                old_log_prob = torch.tensor(step.old_log_prob, dtype=torch.float32, device=self.agent.device)
                advantage = torch.tensor(norm_advantage, dtype=torch.float32, device=self.agent.device)
                return_value = torch.tensor(step.return_value, dtype=torch.float32, device=self.agent.device)

                log_prob, entropy, value = self.agent.evaluate_action_set(
                    step.state_vector,
                    step.action_feature_vectors,
                    step.chosen_action_index,
                )

                ratio = torch.exp(log_prob - old_log_prob)
                clipped_ratio = torch.clamp(
                    ratio,
                    1.0 - self.config.clip_epsilon,
                    1.0 + self.config.clip_epsilon,
                )
                policy_loss = -torch.min(ratio * advantage, clipped_ratio * advantage)
                value_loss = (value - return_value).pow(2)
                loss = (
                    policy_loss
                    + self.config.value_loss_coef * value_loss
                    - self.config.entropy_coef * entropy
                )

                self.agent.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.agent.model.parameters(), self.config.max_grad_norm)  # type: ignore[arg-type]
                self.agent.optimizer.step()

                policy_loss_total += float(policy_loss.item())
                value_loss_total += float(value_loss.item())
                entropy_total += float(entropy.item())
                update_count += 1

        return {
            "policy_loss": policy_loss_total / max(1, update_count),
            "value_loss": value_loss_total / max(1, update_count),
            "entropy": entropy_total / max(1, update_count),
        }

    def train(
        self,
        *,
        num_episodes: int,
        opponent_agent: Optional[BaseAgent] = None,
        p1_world: int = 2,
        p2_world: int = 6,
        card_data_path: str = "Cards.csv",
        seed: Optional[int] = None,
        max_steps: int = 500,
    ) -> Dict[str, object]:
        results = {
            "episodes": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "last_update": None,
        }

        for episode_id in range(num_episodes):
            rollout = self.collect_episode(
                episode_id=episode_id,
                opponent_agent=opponent_agent,
                p1_world=p1_world,
                p2_world=p2_world,
                card_data_path=card_data_path,
                seed=None if seed is None else seed + episode_id,
                max_steps=max_steps,
            )

            result = rollout["result"]
            buffer = rollout["buffer"]
            update_info = self.update_from_buffer(buffer)

            results["episodes"] += 1
            results["last_update"] = update_info
            if result == GameResult.P1_WIN:
                results["wins"] += 1
            elif result == GameResult.P2_WIN:
                results["losses"] += 1
            else:
                results["draws"] += 1

        return results

    def evaluate(
        self,
        *,
        opponent_agent: Optional[BaseAgent] = None,
        num_matches: int = 20,
        p1_world: int = 2,
        p2_world: int = 6,
        card_data_path: str = "Cards.csv",
        seed: Optional[int] = None,
        max_steps: int = 500,
        enable_logging: bool = False,
        print_steps: bool = False,
    ) -> Dict[str, object]:
        opponent = RandomAgent(seed=seed) if opponent_agent is None else opponent_agent
        return evaluate_agents(
            self.agent,
            opponent,
            num_matches=num_matches,
            p1_world=p1_world,
            p2_world=p2_world,
            card_data_path=card_data_path,
            seed=seed,
            max_steps=max_steps,
        )

    def evaluate_report(
        self,
        *,
        opponent_agent: Optional[BaseAgent] = None,
        num_matches: int = 20,
        p1_world: int = 2,
        p2_world: int = 6,
        card_data_path: str = "Cards.csv",
        seed: Optional[int] = None,
        max_steps: int = 500,
        enable_logging: bool = False,
        print_steps: bool = False,
    ) -> str:
        summary = self.evaluate(
            opponent_agent=opponent_agent,
            num_matches=num_matches,
            p1_world=p1_world,
            p2_world=p2_world,
            card_data_path=card_data_path,
            seed=seed,
            max_steps=max_steps,
            enable_logging=enable_logging,
            print_steps=print_steps,
        )
        return build_win_rate_report(summary)

    def _assign_terminal_rewards(self, buffer: RolloutBuffer, result: GameResult) -> None:
        grouped = buffer.trajectory_groups()
        for (_, player_id), indices in grouped.items():
            if not indices:
                continue
            terminal_reward = terminal_reward_for_player(result, PlayerID(player_id))
            last_index = indices[-1]
            for index in indices:
                buffer.steps[index].reward = 0.0
                buffer.steps[index].done = False
            buffer.steps[last_index].reward = terminal_reward
            buffer.steps[last_index].done = True



