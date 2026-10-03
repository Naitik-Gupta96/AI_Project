"""
UI data contract. The frontend renders only these types; the adapter builds
them from real runs. Every type serializes with ``to_dict`` (dataclasses.asdict)
for the "raw data" views.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

# Execution-mode labels shown in the UI and docs
MODE_MOCK = "DETERMINISTIC MOCK"
MODE_LOCAL_MODEL = "LIVE / LOCAL MODEL"
MODE_PILOT = "END-TO-END PILOT"

# RunEvent kinds
EVENT_MESSAGE = "message"  # an agent's PXP message in this run
EVENT_INHERITED = "inherited"  # counterfactual branch: copied unchanged from the original
EVENT_INTERVENTION = "intervention"  # counterfactual branch: the revised message
EVENT_STATUS = "status"  # CONSENSUS / DEADLOCK / MAX_STEPS / ERROR


class _Serializable:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # type: ignore[call-overload]


@dataclass(frozen=True)
class AgentView(_Serializable):
    agent_id: str
    role: str
    description: str
    evidence: dict[str, Any]
    counterfactual_capable: bool


@dataclass(frozen=True)
class RunEvent(_Serializable):
    """One row of a timeline: a PXP message or a status change."""

    kind: str
    step: int
    tag: str  # PXP tag, or the status for EVENT_STATUS
    agent_id: str | None = None
    role: str | None = None
    prediction: str | None = None
    explanation: str | None = None
    confidence: float | None = None
    alternative: str | None = None
    rule: str | None = None  # decision rule reported by the agent (mock provider)
    reason: str = ""  # why the scheduler picked this agent / why the status was set
    status_after: str = ""
    timestamp: str | None = None
    message_id: str | None = None

    @property
    def is_message(self) -> bool:
        return self.kind != EVENT_STATUS


@dataclass(frozen=True)
class Outcome(_Serializable):
    status: str
    prediction: str | None
    iterations: int
    reason: str


@dataclass(frozen=True)
class RunView(_Serializable):
    """One execution (an original run or a counterfactual branch)."""

    title: str
    task: str
    options: list[str]
    mode: str
    provider: dict[str, Any]
    policy: dict[str, Any]
    config: dict[str, Any]
    events: list[RunEvent]
    outcome: Outcome

    @property
    def messages(self) -> list[RunEvent]:
        return [e for e in self.events if e.is_message]


@dataclass(frozen=True)
class ReflectionView(_Serializable):
    """A counterfactual-capable agent's answer about one of its past messages."""

    agent_id: str
    step: int
    original: str  # "TAG prediction"
    revised: str | None  # None: the agent would not change it
    replayed: bool
    outcome: str | None  # branch status if replayed


@dataclass(frozen=True)
class CounterfactualView(_Serializable):
    """A replayed branch and how it relates to the original run."""

    agent_id: str
    branch_point: int
    original_event: RunEvent
    revised_event: RunEvent
    branch: RunView
    divergence_step: int | None
    shared_prefix: int
    recovered: bool
    summary: str


@dataclass(frozen=True)
class DemoView(_Serializable):
    """An original run, the reflections after its deadlock, and the replayed branches."""

    original: RunView
    agents: list[AgentView]
    cf_agents: list[str]
    reflections: list[ReflectionView] = field(default_factory=list)
    branches: list[CounterfactualView] = field(default_factory=list)
    final: Outcome | None = None
    original_preserved: bool = True  # original board unchanged after branching/replay
    runtime_ms: dict[str, float] = field(default_factory=dict)

    @property
    def deadlocked(self) -> bool:
        return self.original.outcome.status == "DEADLOCK"

    @property
    def recovering_branch(self) -> CounterfactualView | None:
        return next((b for b in self.branches if b.recovered), None)

    @property
    def shown_branch(self) -> CounterfactualView | None:
        """The branch to feature: the recovering one, else the last one tried."""
        return self.recovering_branch or (self.branches[-1] if self.branches else None)


@dataclass(frozen=True)
class ExperimentView(_Serializable):
    """A loaded pilot results file and its descriptive summary."""

    path: str
    mode: str
    provider: dict[str, Any]
    generated_at: str
    git_commit: str | None
    parameters: dict[str, Any]
    definitions: dict[str, str]
    by_fraction: list[dict[str, Any]]
    by_condition: list[dict[str, Any]]
    n_trials: int
