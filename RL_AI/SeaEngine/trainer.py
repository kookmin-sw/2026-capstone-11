"""PPO trainer for SeaEngine-backed RL agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import torch

from RL_AI.SeaEngine.action_adapter import choose_action_with_agent
from RL_AI.SeaEngine.agents import SeaEngineAgent, SeaEngineGreedyAgent, SeaEngineRLAgent, SeaEngineRandomAgent
from RL_AI.SeaEngine.bridge.seaengine_session import SeaEngineSession
from RL_AI.SeaEngine.evaluator import evaluate_agents
from RL_AI.SeaEngine.reward import terminal_reward_for_player
from RL_AI.analysis.reports import build_win_rate_report
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


class SeaEnginePPOTrainer:
    def __init__(self, agent: SeaEngineRLAgent, config: Optional[PPOConfig] = None) -> None:
        self.agent = agent
        self.config = PPOConfig() if config is None else config

    def _resolve_opponent_for_episode(
        self,
        episode_id: int,
        *,
        opponent_agent: Optional[SeaEngineAgent] = None,
        opponent_pool: Optional[Sequence[SeaEngineAgent]] = None,
        seed: Optional[int] = None,
    ) -> SeaEngineAgent:
        if opponent_pool:
            return opponent_pool[episode_id % len(opponent_pool)]
        if opponent_agent is not None:
            return opponent_agent
        return SeaEngineRandomAgent(seed=seed)

    def _extend_buffer(self, dst: RolloutBuffer, src: RolloutBuffer) -> None:
        for step in src.steps:
            dst.add_step(step)

    def _assign_terminal_rewards(self, buffer: RolloutBuffer, result: str) -> None:
        grouped = buffer.trajectory_groups()
        for (_, player_idx), indices in grouped.items():
            if not indices:
                continue
            player_id = "P1" if player_idx == 0 else "P2"
            terminal_reward = terminal_reward_for_player(result, player_id)
            last_index = indices[-1]
            for index in indices:
                buffer.steps[index].reward = 0.0
                buffer.steps[index].done = False
            buffer.steps[last_index].reward = terminal_reward
            buffer.steps[last_index].done = True

    def collect_episode(
        self,
        *,
        episode_id: int = 0,
        opponent_agent: Optional[SeaEngineAgent] = None,
        card_data_path: Optional[str] = None,
        player1_deck: str = "",
        player2_deck: str = "",
        max_turns: int = 100,
    ) -> Dict[str, object]:
        session = SeaEngineSession(card_data_path=card_data_path)
        session.start()
        try:
            snapshot = session.init_game(player1_deck=player1_deck, player2_deck=player2_deck)
            buffer = RolloutBuffer()
            opponent = opponent_agent if opponent_agent is not None else SeaEngineRandomAgent()
            steps = 0

            while snapshot["result"] == "Ongoing" and snapshot["turn"] <= max_turns:
                legal_actions = snapshot.get("actions", [])
                if not legal_actions:
                    break

                acting_player = snapshot["active_player"]
                acting_agent: SeaEngineAgent = self.agent if acting_player == "P1" else opponent

                if acting_agent is self.agent:
                    output = self.agent.compute_policy_output(snapshot, legal_actions)
                    buffer.add_step(
                        RolloutStep(
                            episode_id=episode_id,
                            player_id=0 if acting_player == "P1" else 1,
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
                    _, action = choose_action_with_agent(acting_agent, snapshot)

                snapshot = session.apply_action(action["uid"])
                steps += 1

            self._assign_terminal_rewards(buffer, str(snapshot["result"]))
            buffer.compute_returns_and_advantages(self.config.gamma, self.config.gae_lambda)
            return {
                "buffer": buffer,
                "result": snapshot["result"],
                "steps": steps,
                "final_turn": snapshot["turn"],
            }
        finally:
            session.close()

    def update_from_buffer(self, buffer: RolloutBuffer) -> Dict[str, float]:
        if len(buffer) == 0:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        if self.agent.optimizer is None:
            self.agent.ensure_model(state_dim=len(buffer.steps[0].state_vector))
        assert self.agent.optimizer is not None and self.agent.model is not None

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
                clipped_ratio = torch.clamp(ratio, 1.0 - self.config.clip_epsilon, 1.0 + self.config.clip_epsilon)
                policy_loss = -torch.min(ratio * advantage, clipped_ratio * advantage)
                value_loss = (value - return_value).pow(2)
                loss = policy_loss + self.config.value_loss_coef * value_loss - self.config.entropy_coef * entropy

                self.agent.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.agent.model.parameters(), self.config.max_grad_norm)
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
        opponent_agent: Optional[SeaEngineAgent] = None,
        opponent_pool: Optional[Sequence[SeaEngineAgent]] = None,
        card_data_path: Optional[str] = None,
        player1_deck: str = "",
        player2_deck: str = "",
        max_turns: int = 100,
        update_interval: int = 8,
    ) -> Dict[str, object]:
        results = {
            "episodes": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "last_update": None,
            "updates": 0,
            "update_interval": update_interval,
            "opponents": [],
        }
        pending_buffer = RolloutBuffer()

        for episode_id in range(num_episodes):
            selected_opponent = self._resolve_opponent_for_episode(
                episode_id,
                opponent_agent=opponent_agent,
                opponent_pool=opponent_pool,
            )
            rollout = self.collect_episode(
                episode_id=episode_id,
                opponent_agent=selected_opponent,
                card_data_path=card_data_path,
                player1_deck=player1_deck,
                player2_deck=player2_deck,
                max_turns=max_turns,
            )
            result = str(rollout["result"])
            self._extend_buffer(pending_buffer, rollout["buffer"])

            results["episodes"] += 1
            if selected_opponent.name not in results["opponents"]:
                results["opponents"].append(selected_opponent.name)
            if result == "Player1Win":
                results["wins"] += 1
            elif result == "Player2Win":
                results["losses"] += 1
            else:
                results["draws"] += 1

            should_update = len(pending_buffer) > 0 and (
                results["episodes"] % max(1, update_interval) == 0 or episode_id == num_episodes - 1
            )
            if should_update:
                results["last_update"] = self.update_from_buffer(pending_buffer)
                results["updates"] += 1
                pending_buffer.clear()

        return results

    def build_default_opponent_pool(self, *, seed: Optional[int] = None) -> list[SeaEngineAgent]:
        return [
            SeaEngineRandomAgent(seed=seed),
            SeaEngineGreedyAgent(seed=None if seed is None else seed + 1),
        ]

    def evaluate(
        self,
        *,
        opponent_agent: Optional[SeaEngineAgent] = None,
        num_matches: int = 20,
        card_data_path: Optional[str] = None,
        player1_deck: str = "",
        player2_deck: str = "",
        max_turns: int = 100,
    ) -> Dict[str, object]:
        opponent = SeaEngineRandomAgent() if opponent_agent is None else opponent_agent
        return evaluate_agents(
            self.agent,
            opponent,
            num_matches=num_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
        )

    def evaluate_report(
        self,
        *,
        opponent_agent: Optional[SeaEngineAgent] = None,
        num_matches: int = 20,
        card_data_path: Optional[str] = None,
        player1_deck: str = "",
        player2_deck: str = "",
        max_turns: int = 100,
    ) -> str:
        summary = self.evaluate(
            opponent_agent=opponent_agent,
            num_matches=num_matches,
            card_data_path=card_data_path,
            player1_deck=player1_deck,
            player2_deck=player2_deck,
            max_turns=max_turns,
        )
        return build_win_rate_report(summary)
