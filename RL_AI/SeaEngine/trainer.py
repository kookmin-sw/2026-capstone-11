"""PPO trainer for SeaEngine-backed RL agents with Self-Play support."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from collections import Counter
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import torch

from RL_AI.SeaEngine.action_adapter import choose_action_with_agent
from RL_AI.SeaEngine.agents import SeaEngineAgent, SeaEngineGreedyAgent, SeaEngineRLAgent, SeaEngineRandomAgent
from RL_AI.SeaEngine.bridge.seaengine_session import SeaEngineSession
from RL_AI.SeaEngine.bridge.vector_env import VectorSeaEngineEnv
from RL_AI.SeaEngine.evaluator import evaluate_agents
from RL_AI.SeaEngine.reward import dense_reward_from_transition, terminal_reward_for_player
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
    update_epochs: int = 2
    max_grad_norm: float = 0.5


class PastSelfAgent(SeaEngineAgent):
    """An agent that plays using a previously saved model state."""
    def __init__(self, model_path: str, device: str = "cpu", name: str = "past_self", hidden_dim: int = 128):
        super().__init__(name)
        self.device = torch.device(device)
        self.model = None
        self.model_path = model_path
        self.hidden_dim = hidden_dim

    def select_action(self, snapshot: Dict[str, Any], legal_actions: Sequence[Dict[str, Any]]) -> Tuple[int, Dict[str, Any]]:
        if self.model is None:
            # Lazy load model
            from RL_AI.SeaEngine.observation import build_fixed_state_vector, ACTION_FEATURE_DIM
            from RL_AI.SeaEngine.agents import PPOActorCritic
            state_dim = len(build_fixed_state_vector(snapshot))
            self.model = PPOActorCritic(state_dim, ACTION_FEATURE_DIM, hidden_dim=self.hidden_dim).to(self.device)
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

    def _describe_opponent_pool(self, opponent_pool: Sequence[SeaEngineAgent]) -> str:
        if not opponent_pool:
            return "[]"
        return "[" + ", ".join(agent.name for agent in opponent_pool) + "]"

    def _short_opponent_name(self, name: str) -> str:
        if name == "random":
            return "r"
        if name == "greedy":
            return "g"
        if name.startswith("self_ep_"):
            return "s"
        return name[:1].lower()

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
                    action_effect_id = str(action.get("effect_id", ""))
                else:
                    _, action = choose_action_with_agent(acting_agent, snapshot)
                    action_effect_id = str(action.get("effect_id", ""))
                prev_snapshot = snapshot
                snapshot = session.apply_action(action["uid"])
                if buffer.steps:
                    buffer.steps[-1].reward += dense_reward_from_transition(
                        prev_snapshot,
                        snapshot,
                        ai_id=ai_id,
                        action_effect_id=action_effect_id,
                    )
                steps += 1

            self._assign_terminal_rewards_by_id(buffer, str(snapshot["result"]), ai_id, snapshot.get("winner_id", ""))
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

    def _assign_terminal_rewards_by_id(self, buffer: RolloutBuffer, result: str, ai_id: str, winner_id: str) -> None:
        """Helper to assign reward based on AI's ID instead of fixed P1/P2."""
        if not buffer.steps: return
        
        reward = 0.0
        if winner_id == ai_id:
            reward = 1.0
        elif winner_id != "" and winner_id != "None":
            reward = -1.0
        # Draw or Ongoing (terminated by max_turns) is 0.0
        
        last_step = buffer.steps[-1]
        last_step.reward += reward
        last_step.done = True

    def update_from_buffer(self, buffer: RolloutBuffer) -> Dict[str, float]:
        if len(buffer) == 0:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        if self.agent.optimizer is None:
            self.agent.ensure_model(state_dim=len(buffer.steps[0].state_vector))
        assert self.agent.optimizer is not None and self.agent.model is not None

        state_vectors = [s.state_vector for s in buffer.steps]
        action_feature_vectors_list = [s.action_feature_vectors for s in buffer.steps]
        chosen_action_indices = [s.chosen_action_index for s in buffer.steps]

        normalized_advantages = torch.tensor(buffer.normalized_advantages(), dtype=torch.float32, device=self.agent.device)
        returns = torch.tensor([s.return_value for s in buffer.steps], dtype=torch.float32, device=self.agent.device)
        old_log_probs = torch.tensor([s.old_log_prob for s in buffer.steps], dtype=torch.float32, device=self.agent.device)

        policy_loss_total = 0.0
        value_loss_total = 0.0
        entropy_total = 0.0
        batch_size = len(buffer)
        
        for _ in range(self.config.update_epochs):
            log_prob, entropy, value = self.agent.evaluate_action_batch(
                state_vectors,
                action_feature_vectors_list,
                chosen_action_indices,
            )

            ratio = torch.exp(log_prob - old_log_probs)
            clipped_ratio = torch.clamp(ratio, 1.0 - self.config.clip_epsilon, 1.0 + self.config.clip_epsilon)
            policy_loss = -torch.min(ratio * normalized_advantages, clipped_ratio * normalized_advantages).mean()
            value_loss = (value - returns).pow(2).mean()
            entropy_loss = entropy.mean()

            loss = policy_loss + self.config.value_loss_coef * value_loss - self.config.entropy_coef * entropy_loss

            self.agent.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.agent.model.parameters(), self.config.max_grad_norm)

            self.agent.optimizer.step()

            policy_loss_total += float(policy_loss.item())
            value_loss_total += float(value_loss.item())
            entropy_total += float(entropy_loss.item())

        return {
            "policy_loss": policy_loss_total / self.config.update_epochs,
            "value_loss": value_loss_total / self.config.update_epochs,
            "entropy": entropy_total / self.config.update_epochs,
        }

    def collect_vector_episodes(
        self,
        *,
        env: VectorSeaEngineEnv,
        episode_start_idx: int,
        opponent_pool: List[SeaEngineAgent],
        opponent_schedule: Optional[Sequence[str]] = None,
        card_data_path: Optional[str] = None,
        player1_deck: str = "",
        player2_deck: str = "",
        max_turns: int = 100,
    ) -> List[Dict[str, object]]:
        num_envs = env.num_envs
        configs = []
        opponents = []
        ai_ids = []
        buffers = [RolloutBuffer() for _ in range(num_envs)]
        step_counts = [0] * num_envs
        opponent_lookup = {agent.name: agent for agent in opponent_pool}

        for i in range(num_envs):
            player1_is_ai = random.choice([True, False])
            if opponent_schedule is not None and i < len(opponent_schedule):
                scheduled_name = opponent_schedule[i]
                opp = opponent_lookup.get(scheduled_name)
                if opp is None:
                    opp = self._resolve_opponent_for_episode(episode_start_idx + i, opponent_pool=opponent_pool)
            else:
                opp = self._resolve_opponent_for_episode(episode_start_idx + i, opponent_pool=opponent_pool)
            opponents.append(opp)

            if player1_deck and player2_deck:
                p1_d, p2_d = player1_deck, player2_deck
            else:
                deck_types = list(self.decks.keys())
                ai_deck_type = random.choice(deck_types)
                opp_deck_type = random.choice(deck_types)
                p1_d = self.decks[ai_deck_type] if player1_is_ai else self.decks[opp_deck_type]
                p2_d = self.decks[opp_deck_type] if player1_is_ai else self.decks[ai_deck_type]

            configs.append({
                "player1_deck": p1_d,
                "player2_deck": p2_d,
                "player1_id": "AI" if player1_is_ai else "Opponent",
                "player2_id": "Opponent" if player1_is_ai else "AI",
            })
            ai_ids.append("AI")

        snapshots = env.init_games(configs)
        active_envs = set(range(num_envs))
        results = [None] * num_envs

        while active_envs:
            ai_turn_indices = []
            ai_state_vectors = []
            ai_action_feature_vectors = []
            ai_legal_actions = []
            cmds = [None] * num_envs
            transition_effects: Dict[int, str] = {}
            prev_snapshots: Dict[int, Dict[str, object]] = {}

            for i in list(active_envs):
                snap = snapshots[i]
                if snap["result"] != "Ongoing" or snap["turn"] > max_turns:
                    self._assign_terminal_rewards_by_id(
                        buffers[i],
                        str(snap["result"]),
                        ai_ids[i],
                        snap.get("winner_id", ""),
                    )
                    buffers[i].compute_returns_and_advantages(self.config.gamma, self.config.gae_lambda)
                    results[i] = {
                        "buffer": buffers[i],
                        "result": snap["result"],
                        "steps": step_counts[i],
                        "final_turn": snap["turn"],
                        "ai_won": snap.get("winner_id") == ai_ids[i],
                        "opponent_name": opponents[i].name,
                    }
                    active_envs.remove(i)
                    continue

                legal_actions = snap.get("actions", [])
                if not legal_actions:
                    cmds[i] = ("apply_action", {"action_uid": ""})
                    transition_effects[i] = ""
                    prev_snapshots[i] = snap
                    continue

                is_ai_turn = snap["active_player"] == ai_ids[i]
                if is_ai_turn:
                    state_vector = snap.get("state_vector")
                    action_feature_vectors = snap.get("action_feature_vectors")
                    if state_vector is None or action_feature_vectors is None:
                        from RL_AI.SeaEngine.observation import build_observation
                        obs = build_observation({**snap, "actions": list(legal_actions)}, snap.get("active_player"))
                        state_vector = obs.state_vector
                        action_feature_vectors = obs.action_feature_vectors
                    ai_turn_indices.append(i)
                    ai_state_vectors.append(state_vector)
                    ai_action_feature_vectors.append(action_feature_vectors)
                    ai_legal_actions.append(legal_actions)
                else:
                    _, action = choose_action_with_agent(opponents[i], snap)
                    cmds[i] = ("apply_action", {"action_uid": action["uid"]})
                    transition_effects[i] = str(action.get("effect_id", ""))
                    prev_snapshots[i] = snap
                    step_counts[i] += 1

            if ai_turn_indices:
                outputs = self.agent.compute_policy_output_batch(
                    ai_state_vectors,
                    ai_action_feature_vectors,
                    ai_legal_actions,
                )
                for idx, out in zip(ai_turn_indices, outputs):
                    buffers[idx].add_step(
                        RolloutStep(
                            episode_id=episode_start_idx + idx,
                            player_id=0 if snapshots[idx]["active_player"] == "P1" else 1,
                            state_vector=out.state_vector,
                            action_feature_vectors=out.action_feature_vectors,
                            chosen_action_index=out.action_index,
                            reward=0.0,
                            done=False,
                            old_log_prob=out.log_prob,
                            old_value=out.value,
                        )
                    )
                    cmds[idx] = ("apply_action", {"action_uid": out.action["uid"]})
                    transition_effects[idx] = str(out.action.get("effect_id", ""))
                    prev_snapshots[idx] = snapshots[idx]
                    step_counts[idx] += 1

            if active_envs:
                env.step_async(cmds)
                new_snapshots = env.step_wait()
                for i in active_envs:
                    if i in new_snapshots:
                        if i in prev_snapshots and buffers[i].steps:
                            buffers[i].steps[-1].reward += dense_reward_from_transition(
                                prev_snapshots[i],
                                new_snapshots[i],
                                ai_id=ai_ids[i],
                                action_effect_id=transition_effects.get(i, ""),
                            )
                        snapshots[i] = new_snapshots[i]

        return results

    def train(
        self,
        *,
        num_episodes: int,
        opponent_pool: Optional[List[SeaEngineAgent]] = None,
        opponent_schedule: Optional[Sequence[str]] = None,
        card_data_path: Optional[str] = None,
        player1_deck: str = "",
        player2_deck: str = "",
        max_turns: int = 100,
        update_interval: int = 16,
        save_interval: int = 500,
        log_interval: int = 200, # 200판마다 요약 출력, 0 이하면 비활성화
        progress_callback: Optional[Callable[[int, int, str, Dict[str, object]], None]] = None,
        num_envs: int = 8,
        episode_offset: int = 0,
    ) -> Dict[str, object]:
        import time
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
        env = VectorSeaEngineEnv(num_envs=num_envs, card_data_path=card_data_path)
        env.start()
        
        start_time = time.time()
        interval_start_time = time.time()
        last_heartbeat_time = start_time
        interval_opponents: Counter[str] = Counter()
        try:
            parallel_desc = env.describe_parallelism()
            print(f"[*] Starting Training: {num_episodes} episodes | Device: {self.agent.device} | Envs: {num_envs} (PythonNet)")
            print(
                f"[*] Parallel: backend={parallel_desc.get('backend')} | "
                f"threaded={parallel_desc.get('threaded')} | workers={parallel_desc.get('workers')}"
            )
            print(f"[*] Opp pool: {self._describe_opponent_pool(opponent_pool)}")
            
            # num_episodes가 num_envs로 나누어 떨어지지 않으면 맞춰서 반복
            for episode_start_idx in range(0, num_episodes, num_envs):
                actual_num_envs = min(num_envs, num_episodes - episode_start_idx)
                env.num_envs = actual_num_envs # Adjust if last batch is smaller
                batch_schedule = None
                if opponent_schedule is not None:
                    batch_schedule = list(opponent_schedule[episode_start_idx:episode_start_idx + actual_num_envs])
                
                try:
                    rollouts = self.collect_vector_episodes(
                        env=env,
                        episode_start_idx=episode_offset + episode_start_idx,
                        opponent_pool=opponent_pool,
                        opponent_schedule=batch_schedule,
                        card_data_path=card_data_path,
                        player1_deck=player1_deck,
                        player2_deck=player2_deck,
                        max_turns=max_turns,
                    )
                except Exception as e:
                    print(f"  [!] Vector Engine crashed during batch {episode_start_idx}. Restarting envs... ({e})")
                    env.close()
                    env = VectorSeaEngineEnv(num_envs=num_envs, card_data_path=card_data_path)
                    env.start()
                    continue

                for rollout in rollouts:
                    self._extend_buffer(pending_buffer, rollout["buffer"])                
                    results["episodes"] += 1
                    interval_opponents[str(rollout["opponent_name"])] += 1
                    if rollout["ai_won"]: results["wins"] += 1
                    elif "Win" in str(rollout["result"]): results["losses"] += 1
                    else: results["draws"] += 1

                    if progress_callback:
                        progress_callback(results["episodes"], num_episodes, rollout["opponent_name"], {**rollout, **results})

                # 4. Update
                if len(pending_buffer) > 0 and (results["episodes"] % update_interval < actual_num_envs or results["episodes"] >= num_episodes):
                    results["last_update"] = self.update_from_buffer(pending_buffer)
                    results["updates"] += 1
                    pending_buffer.clear()

                now = time.time()
                if now - last_heartbeat_time >= 60:
                    elapsed = now - start_time
                    done = results["episodes"]
                    speed = done / elapsed if elapsed > 0 else 0.0
                    print(
                        f"[*] Training heartbeat | {done}/{num_episodes} episodes | "
                        f"updates={results['updates']} | speed={speed:.2f} eps/s"
                    )
                    last_heartbeat_time = now

                # 5. Periodic Output (200 episodes)
                if log_interval > 0 and results["episodes"] % log_interval < actual_num_envs:
                    elapsed = time.time() - interval_start_time
                    fps = log_interval / elapsed if elapsed > 0 else 0
                    win_rate = (results["wins"] / results["episodes"]) * 100
                    loss = results.get("last_update", {}).get("policy_loss", 0.0)
                    opp_summary = ", ".join(
                        f"{self._short_opponent_name(name)}={count}"
                        for name, count in sorted(interval_opponents.items())
                    )
                    if not opp_summary:
                        opp_summary = "-"
                    print(
                        f"[Ep {results['episodes']:>5}/{num_episodes}] "
                        f"Win: {win_rate:>4.1f}% | Loss: {loss:>7.4f} | Speed: {fps:>5.1f} eps/s | Opp: {opp_summary}"
                    )
                    interval_opponents.clear()
                    interval_start_time = time.time()

                # 6. Periodic Save
                global_episodes = episode_offset + results["episodes"]
                if global_episodes % save_interval < actual_num_envs:
                    model_path = self.model_dir / f"model_ep_{global_episodes}.pt"
                    torch.save(self.agent.model.state_dict(), model_path)
                    new_past_self = PastSelfAgent(
                        str(model_path),
                        device=str(self.agent.device),
                        name=f"self_ep_{global_episodes}",
                        hidden_dim=self.agent.hidden_dim,
                    )
                    opponent_pool.append(new_past_self)

            total_elapsed = time.time() - start_time
            print(f"[*] Training Finished! Total Time: {total_elapsed:.1f}s | Avg Speed: {num_episodes/total_elapsed:.1f} eps/s")

        finally:
            env.close()

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
        player1_deck: str = "",
        player2_deck: str = "",
        max_turns: int = 100,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Dict[str, object]:
        # Evaluation uses fixed decks or mirror matches for fairness
        opponent = SeaEngineRandomAgent() if opponent_agent is None else opponent_agent
        p1_d = player1_deck or self.decks["Orange"]
        p2_d = player2_deck or self.decks["Charlotte"]
        
        return evaluate_agents(
            self.agent,
            opponent,
            num_matches=num_matches,
            card_data_path=card_data_path,
            player1_deck=p1_d,
            player2_deck=p2_d,
            max_turns=max_turns,
            progress_callback=progress_callback,
        )
