"""
Deterministic scheduler scenarios built from RuleBasedMockAgent.

- ``consensus_scenario``            -> Scenario A: agents reach CONSENSUS
- ``deadlock_scenario``             -> Scenario B: analyst proposes, critic and
                                       specialist both refute -> DEADLOCK
- ``alternating_deadlock_scenario`` -> RATIFY / REFUTE ping-pong between two
                                       agents until the cycle threshold

The counterfactual variant of ``deadlock_scenario`` (Scenario C) lives in
``ai_project.counterfactual.scenarios``.
"""

from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard import Blackboard
from ai_project.deadlock import DeadlockConfig
from ai_project.scheduler.mock_agents import RuleBasedMockAgent
from ai_project.scheduler.policies import PriorityPolicy, RoundRobinPolicy, SchedulingPolicy
from ai_project.scheduler.scheduler import Scheduler, SchedulerConfig, SchedulerResult

DEFAULT_TASK = "Choose the architecture for the reasoning service: Option A or Option B"
OPTION_A = "Option A"
OPTION_B = "Option B"

CRITIC_OBJECTION = "it violates constraint C3 (runs must be reproducible)"
SPECIALIST_OBJECTION = "it cannot meet the latency budget"


@dataclass
class Scenario:
    """
    A ready-to-run configuration: task, agents, policy and scheduler config.

    Agents and policies here are stateless, so one Scenario can be run any
    number of times (and reused for counterfactual replay).
    """

    name: str
    description: str
    task: str
    agents: dict[str, RuleBasedMockAgent]
    policy: SchedulingPolicy
    config: SchedulerConfig = field(default_factory=SchedulerConfig)

    def new_board(self) -> Blackboard:
        """Create and initialize a fresh Blackboard for this scenario."""
        board = Blackboard()
        board.initialize_task(self.task, {"scenario": self.name})
        return board

    def new_scheduler(self, board: Blackboard | None = None) -> Scheduler:
        """Create a Scheduler for this scenario (on a fresh board by default)."""
        return Scheduler(board or self.new_board(), self.agents, self.policy, self.config)

    def run(self) -> tuple[Blackboard, Scheduler, SchedulerResult]:
        """Run the scenario to completion on a fresh board."""
        scheduler = self.new_scheduler()
        result = scheduler.run()
        return scheduler.board, scheduler, result

    def describe(self) -> dict[str, Any]:
        """Serializable description of the scenario."""
        return {
            "name": self.name,
            "description": self.description,
            "task": self.task,
            "agents": list(self.agents),
            "policy": self.policy.describe(),
            "config": self.config.to_dict(),
        }


def _critic() -> RuleBasedMockAgent:
    return RuleBasedMockAgent(
        "critic",
        role="Critic",
        objections={OPTION_A: CRITIC_OBJECTION},
    )


def _specialist() -> RuleBasedMockAgent:
    return RuleBasedMockAgent(
        "specialist",
        role="Specialist",
        objections={OPTION_A: SPECIALIST_OBJECTION},
        adopts_alternatives=True,
    )


def _priority() -> PriorityPolicy:
    return PriorityPolicy(proposer="analyst", critic="critic", resolver="specialist")


def consensus_scenario() -> Scenario:
    """Scenario A: the analyst opens with Option B, which nobody objects to."""
    return Scenario(
        name="consensus",
        description="Analyst proposes Option B; critic and specialist ratify it -> CONSENSUS",
        task=DEFAULT_TASK,
        agents={
            "analyst": RuleBasedMockAgent("analyst", role="Analyst", preferred=OPTION_B),
            "critic": _critic(),
            "specialist": _specialist(),
        },
        policy=_priority(),
        config=SchedulerConfig(max_steps=10),
    )


def deadlock_scenario() -> Scenario:
    """
    Scenario B: the analyst opens with Option A; the critic refutes it without
    offering an alternative, the specialist refutes it too -> DEADLOCK after
    two disagreement cycles.
    """
    return Scenario(
        name="deadlock",
        description="Analyst proposes Option A; critic and specialist refute it -> DEADLOCK",
        task=DEFAULT_TASK,
        agents={
            "analyst": RuleBasedMockAgent("analyst", role="Analyst", preferred=OPTION_A),
            "critic": _critic(),
            "specialist": _specialist(),
        },
        policy=_priority(),
        config=SchedulerConfig(max_steps=10, deadlock=DeadlockConfig(max_disagreement_cycles=2)),
    )


def alternating_deadlock_scenario(max_disagreement_cycles: int = 2) -> Scenario:
    """
    Two agents alternate (round robin): analyst RATIFY Option A, critic
    REFUTE Option A, ... until ``max_disagreement_cycles`` refutations.
    Stagnation is disabled so only the cycle threshold applies.
    """
    return Scenario(
        name="alternating_deadlock",
        description="Analyst keeps ratifying Option A, critic keeps refuting it -> DEADLOCK",
        task=DEFAULT_TASK,
        agents={
            "analyst": RuleBasedMockAgent("analyst", role="Analyst", preferred=OPTION_A),
            "critic": _critic(),
        },
        policy=RoundRobinPolicy(),
        config=SchedulerConfig(
            max_steps=4 * max_disagreement_cycles,
            deadlock=DeadlockConfig(
                max_disagreement_cycles=max_disagreement_cycles, max_stagnant_steps=None
            ),
        ),
    )
