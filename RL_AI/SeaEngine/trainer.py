"""PPO trainer for SeaEngine-backed RL agents with Self-Play support."""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

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


class PastSelfAgent(SeaEngineAgent):
    """An agent that plays using a previously saved model state."""
    def __init__(self, model_path: str, device: str = "cpu", name: str = "past_self"):
        super().__init__(name)
        self.device = torch.device(device)
        self.model = None
        self.model_path = model_path

    def select_action(self, snapshot: Dict[str, Any], legal_actions: Sequence[Dict[str, Any]]) -> Tuple[int, Dict[str, Any]]:
        if self.model is None:
            # Lazy load model
            from RL_AI.SeaEngine.observation import build_fixed_state_vector, ACTION_FEATURE_DIM
            from RL_AI.SeaEngine.agents import PPOActorCritic
            state_dim = len(build_fixed_state_vector(snapshot))
            self.model = PPOActorCritic(state_dim, ACTION_FEATURE_DIM, hidden_dim=256).to(self.device)
            self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
            self.model.eval()

        from RL_AI.SeaEngine.observation import build_observation
        obs = build_observation({**snapshot, "actions": list(legal_actions)}, snapshot.get("active_player"))
        state_tensor = torch.tensor(obs.state_vector, dtype=torch.float32, device=self.device)
        action_tensor = torch.tensor(obs.action_feature_vectors, dtype=torch.float32, device=self.device)

        with torch.no_grad():
            logits, _ = self.model(state_tensor, action_tensor)
            idx = int(torch.argmax(logits).item())
        return idx, legal_actions[idx]


class SeaEnginePPOTrainer:
    def __init__(self, agent: SeaEngineRLAgent, config: Optional[PPOConfig] = None) -> None:
        self.agent = agent
        self.config = PPOConfig() if config is None else config
        self.model_dir = Path(__file__).resolve().parent.parent / "models"
        self.model_dir.mkdir(exist_ok=True)
        
        # Standard Decks
        self.decks = {
            "Orange": json.dumps(["Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P"]),
            "Charlotte": json.dumps(["Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P"])
        }

    def _resolve_opponent_for_episode(
        self,
        episode_id: int,
        *,
        opponent_agent: Optional[SeaEngineAgent] = None,
        opponent_pool: Optional[Sequence[SeaEngineAgent]] = None,
        seed: Optional[int] = None,
    ) -> SeaEngineAgent:
        if opponent_pool:
            return random.choice(opponent_pool)
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
        session: Optional[SeaEngineSession] = None,
        card_data_path: Optional[str] = None,
        player1_deck: str = "",
        player2_deck: str = "",
        player1_is_ai: bool = True,
        max_turns: int = 100,
    ) -> Dict[str, object]:
        owns_session = session is None
        if session is None:
            session = SeaEngineSession(card_data_path=card_data_path)
            session.start()
        try:
            snapshot = session.init_game(
                player1_deck=player1_deck, 
                player2_deck=player2_deck,
                player1_id="AI" if player1_is_ai else "Opponent",
                player2_id="Opponent" if player1_is_ai else "AI"
            )
            buffer = RolloutBuffer()
            opponent = opponent_agent if opponent_agent is not None else SeaEngineRandomAgent()
            steps = 0

            ai_id = "AI"
            while snapshot["result"] == "Ongoing" and snapshot["turn"] <= max_turns:
                legal_actions = snapshot.get("actions", [])
                if not legal_actions:
                    break

                active_player = snapshot["active_player"]
                is_ai_turn = active_player == ai_id
                acting_agent: SeaEngineAgent = self.agent if is_ai_turn else opponent

                if is_ai_turn:
                    output = self.agent.compute_policy_output(snapshot, legal_actions)
                    buffer.add_step(
                        RolloutStep(
                            episode_id=episode_id,
                            player_id=0 if active_player == "P1" else 1, # Canonical P1/P2 index for reward processing
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

            self._assign_terminal_rewards_by_id(buffer, str(snapshot["result"]), ai_id)
            buffer.compute_returns_and_advantages(self.config.gamma, self.config.gae_lambda)
            return {
                "buffer": buffer,
                "result": snapshot["result"],
                "steps": steps,
                "final_turn": snapshot["turn"],
                "ai_won": snapshot["winner_id"] == ai_id
            }
        finally:
            if owns_session:
                session.close()

    def _assign_terminal_rewards_by_id(self, buffer: RolloutBuffer, result: str, ai_id: str) -> None:
        """Helper to assign reward based on AI's ID instead of fixed P1/P2."""
        # RolloutStep uses player_id as 0/1. We need to know which one was AI.
        # But here we just simplified: AI's steps are the only ones in the buffer.
        # collect_episode only adds AI's steps to the buffer.
        if not buffer.steps: return
        
        # Calculate reward
        reward = 0.0
        if result == "Player1Win":
            reward = 1.0 if ai_id == "P1" else -1.0
        elif result == "Player2Win":
            reward = 1.0 if ai_id == "P2" else -1.0
        
        last_step = buffer.steps[-1]
        last_step.reward = reward
        last_step.done = True

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
        opponent_pool: Optional[List[SeaEngineAgent]] = None,
        card_data_path: Optional[str] = None,
        max_turns: int = 100,
        update_interval: int = 16,
        save_interval: int = 500,
        progress_callback: Optional[Callable[[int, int, str, Dict[str, object]], None]] = None,
    ) -> Dict[str, object]:
        results = {
            "episodes": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "updates": 0,
            "opponents": [],
        }
        
        if opponent_pool is None:
            opponent_pool = self.build_default_opponent_pool()
        
        pending_buffer = RolloutBuffer()
        session = SeaEngineSession(card_data_path=card_data_path)
        session.start()
        
        try:
            for episode_id in range(num_episodes):
                # 1. Choose Opponent
                selected_opponent = self._resolve_opponent_for_episode(episode_id, opponent_pool=opponent_pool)
                
                # 2. Choose Randomized Setup
                player1_is_ai = random.choice([True, False])
                deck_types = list(self.decks.keys())
                ai_deck_type = random.choice(deck_types)
                opp_deck_type = random.choice(deck_types)
                
                p1_deck = self.decks[ai_deck_type] if player1_is_ai else self.decks[opp_deck_type]
                p2_deck = self.decks[opp_deck_type] if player1_is_ai else self.decks[ai_deck_type]

                # 3. Collect Rollout
                rollout = self.collect_episode(
                    episode_id=episode_id,
                    opponent_agent=selected_opponent,
                    session=session,
                    card_data_path=card_data_path,
                    player1_deck=p1_deck,
                    player2_deck=p2_deck,
                    player1_is_ai=player1_is_ai,
                    max_turns=max_turns,
                )
                
                self._extend_buffer(pending_buffer, rollout["buffer"])
                
                # Stats
                results["episodes"] += 1
                if rollout["ai_won"]:
                    results["wins"] += 1
                elif "Win" in str(rollout["result"]):
                    results["losses"] += 1
                else:
                    results["draws"] += 1
                
                # 4. Periodic Update
                if len(pending_buffer) > 0 and (results["episodes"] % update_interval == 0 or episode_id == num_episodes - 1):
                    results["last_update"] = self.update_from_buffer(pending_buffer)
                    results["updates"] += 1
                    pending_buffer.clear()

                # 5. Periodic Save & Pool Update (Self-Play)
                if results["episodes"] % save_interval == 0:
                    model_path = self.model_dir / f"model_ep_{results['episodes']}.pt"
                    torch.save(self.agent.model.state_dict(), model_path)
                    # Add to opponent pool
                    new_past_self = PastSelfAgent(str(model_path), device=str(self.agent.device), name=f"self_ep_{results['episodes']}")
                    opponent_pool.append(new_past_self)
                    print(f"Checkpoint saved and added to Self-Play pool: {model_path}")

                if progress_callback:
                    progress_callback(results["episodes"], num_episodes, selected_opponent.name, rollout)

        finally:
            session.close()

        return results

    def build_default_opponent_pool(self, *, seed: Optional[int] = None) -> List[SeaEngineAgent]:
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
        max_turns: int = 100,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Dict[str, object]:
        # Evaluation uses fixed decks or mirror matches for fairness
        opponent = SeaEngineRandomAgent() if opponent_agent is None else opponent_agent
        return evaluate_agents(
            self.agent,
            opponent,
            num_matches=num_matches,
            card_data_path=card_data_path,
            player1_deck=self.decks["Orange"],
            player2_deck=self.decks["Charlotte"],
            max_turns=max_turns,
            progress_callback=progress_callback,
        )
