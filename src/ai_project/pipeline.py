"""
The end-to-end path shared by the Flash Talk demo, the CLI demo and the
experiments:

    DecisionTask -> Blackboard -> analyst/critic/specialist -> Scheduler
        -> CONSENSUS, or DEADLOCK -> counterfactual-capable agents reflect
        -> branch + replay -> outcome

``run_task`` is the only entry point; callers change the condition
(task, provider, which agents are counterfactual-capable), never the path.
"""

import time
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from ai_project.agents import BaseAgent, build_team
from ai_project.blackboard import Blackboard
from ai_project.counterfactual.resolver import CounterfactualResolver, Resolution
from ai_project.deadlock import DeadlockConfig
from ai_project.llm import LLMProvider, MockLLMProvider
from ai_project.scheduler import PriorityPolicy, Scheduler, SchedulerConfig, SchedulerResult
from ai_project.tasks import ROLES, DecisionTask


@dataclass(frozen=True)
class RunConfig:
    """
    Run configuration (recorded with every result).

    Attributes:
        cf_agents: Ids of counterfactual-capable agents (subset of ROLES)
        max_steps: Agent-action budget per run (original and each replay)
        max_disagreement_cycles: Deadlock rule 1 threshold
        max_stagnant_steps: Deadlock rule 2 threshold (None disables it)
    """

    cf_agents: tuple[str, ...] = ()
    max_steps: int = 12
    max_disagreement_cycles: int = 2
    max_stagnant_steps: int | None = 6

    def __post_init__(self) -> None:
        unknown = set(self.cf_agents) - set(ROLES)
        if unknown:
            raise ValueError(f"Unknown agents in cf_agents: {sorted(unknown)}")
        # Canonical order so equal configurations compare and serialize equally
        object.__setattr__(self, "cf_agents", tuple(r for r in ROLES if r in self.cf_agents))

    @property
    def cf_fraction(self) -> float:
        """Fraction of the team that is counterfactual-capable."""
        return len(self.cf_agents) / len(ROLES)

    def scheduler_config(self) -> SchedulerConfig:
        return SchedulerConfig(
            max_steps=self.max_steps,
            deadlock=DeadlockConfig(
                max_disagreement_cycles=self.max_disagreement_cycles,
                max_stagnant_steps=self.max_stagnant_steps,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cf_agents": list(self.cf_agents),
            "cf_fraction": round(self.cf_fraction, 4),
            "max_steps": self.max_steps,
            "max_disagreement_cycles": self.max_disagreement_cycles,
            "max_stagnant_steps": self.max_stagnant_steps,
        }


def default_policy() -> PriorityPolicy:
    """Analyst proposes, critic reviews new proposals, specialist answers objections."""
    return PriorityPolicy(proposer="analyst", critic="critic", resolver="specialist")


@dataclass
class PipelineRun:
    """One task run end to end, with its counterfactual resolution (if it deadlocked)."""

    task: DecisionTask
    config: RunConfig
    provider: dict[str, Any]
    agents: list[BaseAgent]
    board: Blackboard
    original: SchedulerResult
    resolution: Resolution | None
    runtime_ms: dict[str, float] = field(default_factory=dict)

    @property
    def recovered(self) -> bool:
        return self.resolution is not None and self.resolution.recovered

    @property
    def final(self) -> SchedulerResult:
        """The result the system ends with: the recovering branch, else the original."""
        if self.resolution is not None and self.resolution.success is not None:
            return self.resolution.success.outcome.result
        return self.original

    def token_usage(self) -> dict[str, int] | None:
        """Tokens reported by the provider across all agents, or None if none were reported."""
        totals = {"prompt_tokens": 0, "completion_tokens": 0}
        reported = False
        for agent in self.agents:
            for key in totals:
                if agent.usage.get(key) is not None:
                    totals[key] += agent.usage[key]
                    reported = True
        return totals if reported else None

    def provider_calls(self) -> int:
        return sum(agent.usage["calls"] for agent in self.agents)


def run_task(
    task: DecisionTask,
    cf_agents: Collection[str] = (),
    provider: LLMProvider | None = None,
    config: RunConfig | None = None,
) -> PipelineRun:
    """
    Run one task end to end.

    Args:
        task: The decision task
        cf_agents: Counterfactual-capable agents (overrides ``config.cf_agents``)
        provider: Decision provider for all agents (default: deterministic mock)
        config: Run configuration
    """
    config = config or RunConfig()
    if cf_agents:
        config = RunConfig(
            cf_agents=tuple(cf_agents),
            max_steps=config.max_steps,
            max_disagreement_cycles=config.max_disagreement_cycles,
            max_stagnant_steps=config.max_stagnant_steps,
        )
    provider = provider or MockLLMProvider()
    agents = build_team(task, provider)
    policy = default_policy()
    scheduler_config = config.scheduler_config()

    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata())

    start = time.perf_counter()
    original = Scheduler(board, agents, policy, scheduler_config).run()
    runtime = {"original": (time.perf_counter() - start) * 1000}

    resolution = None
    if original.deadlocked:
        start = time.perf_counter()
        resolution = CounterfactualResolver().resolve(
            board, original, agents, config.cf_agents, policy, scheduler_config
        )
        runtime["counterfactual"] = (time.perf_counter() - start) * 1000

    return PipelineRun(
        task=task,
        config=config,
        provider=provider.describe(),
        agents=agents,
        board=board,
        original=original,
        resolution=resolution,
        runtime_ms=runtime,
    )
