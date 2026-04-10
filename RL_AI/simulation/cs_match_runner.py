"""Backward-compatible wrappers for SeaEngine match runners.

Use RL_AI.simulation.match_runner as the primary entrypoint.
"""

from RL_AI.simulation.match_runner import (
    print_cs_snapshot,
    run_cs_agent_match,
    run_cs_manual_match,
    run_cs_manual_vs_agent,
    run_cs_mixed_match,
    run_cs_random_match,
)

__all__ = [
    "print_cs_snapshot",
    "run_cs_agent_match",
    "run_cs_manual_match",
    "run_cs_manual_vs_agent",
    "run_cs_mixed_match",
    "run_cs_random_match",
]
