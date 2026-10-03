"""
Counterfactual deadlock resolution with counterfactual-capable agents.

After a deadlock, each *counterfactual-capable* agent reflects on its own
past messages (``BaseAgent.reflect``): knowing how the run unfolded, what
would it have said instead? Every proposed revision becomes an
``Intervention``; the engine branches the original board at that step and
replays the future with the same agents, policy and configuration.

Candidates are tried latest message first: a later branch point keeps more
of the original run and replays less, so it is the smallest change to
history. Resolution stops at the first branch that reaches CONSENSUS; every
attempted branch is kept for inspection.

The original board is only read through ``snapshot()`` and is never changed.
"""

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard import Blackboard
from ai_project.counterfactual.engine import (
    CounterfactualEngine,
    CounterfactualError,
    CounterfactualOutcome,
    Intervention,
    _event_signature,
)
from ai_project.scheduler.policies import SchedulingPolicy
from ai_project.scheduler.registry import AgentRegistry, AgentsInput
from ai_project.scheduler.scheduler import SchedulerConfig, SchedulerResult


@dataclass
class Reflection:
    """One agent's answer about one of its past messages."""

    agent_id: str
    iteration: int
    original: dict[str, Any]
    revised: dict[str, Any] | None  # None: the agent would not change the message
    outcome: CounterfactualOutcome | None = None  # set if the revision was replayed

    @property
    def recovered(self) -> bool:
        return self.outcome is not None and self.outcome.result.consensus_reached

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "iteration": self.iteration,
            "original": self.original,
            "revised": self.revised,
            "replayed": self.outcome is not None,
            "recovered": self.recovered,
            "comparison": self.outcome.comparison.to_dict() if self.outcome else None,
        }


@dataclass
class Resolution:
    """Everything the resolver did for one deadlocked run."""

    cf_agents: tuple[str, ...]
    reflections: list[Reflection] = field(default_factory=list)

    @property
    def attempts(self) -> list[Reflection]:
        """Reflections that produced a revision and were replayed, in order."""
        return [r for r in self.reflections if r.outcome is not None]

    @property
    def success(self) -> Reflection | None:
        """The replayed reflection that reached consensus, if any."""
        return next((r for r in self.reflections if r.recovered), None)

    @property
    def recovered(self) -> bool:
        return self.success is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cf_agents": list(self.cf_agents),
            "recovered": self.recovered,
            "branches_replayed": len(self.attempts),
            "reflections": [r.to_dict() for r in self.reflections],
        }


class CounterfactualResolver:
    """Turns counterfactual-capable agents' reflections into replayed branches."""

    def __init__(self, engine: CounterfactualEngine | None = None) -> None:
        self.engine = engine or CounterfactualEngine()

    def resolve(
        self,
        board: Blackboard,
        original: SchedulerResult,
        agents: AgentsInput,
        cf_agents: Collection[str],
        policy: SchedulingPolicy | None = None,
        config: SchedulerConfig | None = None,
    ) -> Resolution:
        """
        Try to resolve the deadlock on ``board``.

        Args:
            board: The deadlocked original board (read via snapshot only)
            original: The original run's result
            agents: The agents of the original run (replays use the same ones)
            cf_agents: Ids of the counterfactual-capable agents
            policy, config: The original run's policy and scheduler config

        Raises:
            CounterfactualError: If the run is not deadlocked, or a
                counterfactual-capable agent cannot reflect
        """
        if not original.deadlocked:
            raise CounterfactualError("Counterfactual resolution needs a deadlocked run")
        registry = AgentRegistry.from_input(agents)
        unknown = set(cf_agents) - set(registry.agent_ids)
        if unknown:
            raise CounterfactualError(f"Unknown counterfactual agents: {sorted(unknown)}")
        resolution = Resolution(
            cf_agents=tuple(a for a in registry.agent_ids if a in set(cf_agents))
        )

        snapshot = board.snapshot()
        history = snapshot.history
        options = snapshot.state.metadata.get("options") or []
        for event in reversed(history):
            if event.agent_id not in resolution.cf_agents:
                continue
            agent = registry.get(event.agent_id)
            if not hasattr(agent, "reflect"):
                raise CounterfactualError(f"Agent '{agent.agent_id}' cannot reflect")
            decision = agent.reflect(snapshot.state.task, options, history, event)
            reflection = Reflection(
                agent_id=event.agent_id,
                iteration=event.iteration,
                original=_event_signature(event),
                revised=decision.to_dict() if decision else None,
            )
            resolution.reflections.append(reflection)
            if decision is None:
                continue
            intervention = Intervention(
                iteration=event.iteration,
                tag=decision.tag,
                prediction=decision.prediction,
                explanation=decision.explanation,
                confidence=decision.confidence,
                metadata=decision.metadata,
                description=(
                    f"{event.agent_id} reconsiders its step-{event.iteration} message: "
                    f"{event.tag} {event.prediction} -> {decision.tag.value} "
                    f"{decision.prediction}"
                    + (f" (naming {decision.alternative})" if decision.alternative else "")
                ),
            )
            reflection.outcome = self.engine.run_counterfactual(
                snapshot, original, registry, intervention, policy=policy, config=config
            )
            if reflection.recovered:
                break
        return resolution
