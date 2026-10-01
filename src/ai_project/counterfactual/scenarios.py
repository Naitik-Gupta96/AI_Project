"""
Scenario C: the original run deadlocks; a counterfactual branch reaches consensus.

Original (``deadlock_scenario``):
    1. analyst    RATIFY Option A
    2. critic     REFUTE Option A   (no alternative offered)
    3. specialist REFUTE Option A   -> DEADLOCK

Counterfactual: replace iteration 2 with the critic's same refutation, but
naming Option B as an alternative. The specialist now sees different context
and revises to Option B; the critic and analyst ratify it -> CONSENSUS.

Only iteration 2 is scripted. Everything after it is produced by the same
agents, policy and configuration as the original run.
"""

from dataclasses import dataclass
from typing import Any

from ai_project.blackboard import Blackboard
from ai_project.counterfactual.engine import (
    CounterfactualEngine,
    CounterfactualOutcome,
    Intervention,
)
from ai_project.protocol.pxp import PXPTag
from ai_project.scheduler.mock_agents import ALTERNATIVE_KEY
from ai_project.scheduler.scenarios import (
    CRITIC_OBJECTION,
    OPTION_A,
    OPTION_B,
    Scenario,
    deadlock_scenario,
)
from ai_project.scheduler.scheduler import SchedulerResult

DEMO_BRANCH_POINT = 2


def demo_intervention() -> Intervention:
    """The critic's iteration-2 refutation, now also pointing to Option B."""
    return Intervention(
        iteration=DEMO_BRANCH_POINT,
        tag=PXPTag.REFUTE,
        prediction=OPTION_A,
        explanation=(
            f"{OPTION_A} is unacceptable: {CRITIC_OBJECTION}. {OPTION_B} avoids this problem."
        ),
        confidence=0.8,
        metadata={ALTERNATIVE_KEY: OPTION_B},
        description=f"Critic's refutation of {OPTION_A} also names {OPTION_B} as an alternative",
    )


@dataclass
class CounterfactualScenarioRun:
    """Original run plus its counterfactual outcome."""

    scenario: Scenario
    original_board: Blackboard
    original_result: SchedulerResult
    engine: CounterfactualEngine
    outcome: CounterfactualOutcome

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary (UI / experiment logging)."""
        return {
            "scenario": self.scenario.describe(),
            "original": self.original_result.to_dict(),
            "counterfactual": self.outcome.to_dict(),
        }


def run_deadlock_counterfactual() -> CounterfactualScenarioRun:
    """Run Scenario C end to end."""
    scenario = deadlock_scenario()
    board, _, original = scenario.run()
    engine = CounterfactualEngine()
    outcome = engine.run_counterfactual(
        board,
        original,
        scenario.agents,
        demo_intervention(),
        policy=scenario.policy,
        config=scenario.config,
    )
    return CounterfactualScenarioRun(scenario, board, original, engine, outcome)
