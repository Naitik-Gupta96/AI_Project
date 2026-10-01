"""
Counterfactual branching, replay and comparison.

Flow:

    original board --snapshot()--> isolated copy
        -> new branch Blackboard: same task, events before the branch point
           re-published in order, then the intervention (the altered event)
        -> Scheduler replays the future on the branch board
        -> compare original vs counterfactual results

The original board is only ever read through ``snapshot()``; it is never
mutated. Each branch gets its own Blackboard, so branches are isolated from
the original and from each other.

Branch boards are rebuilt by re-publishing history through
``publish_message`` (rather than editing a snapshot and loading it) so the
Blackboard itself recomputes iteration, current prediction and latest message.
Limitation: ``HistoryEvent`` does not store message metadata, so inherited
events are re-published with empty metadata.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard import Blackboard, BlackboardSnapshot, HistoryEvent
from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.scheduler.policies import SchedulingPolicy
from ai_project.scheduler.registry import AgentsInput
from ai_project.scheduler.scheduler import Scheduler, SchedulerConfig, SchedulerResult
from ai_project.scheduler.trace import KIND_INHERITED, KIND_INTERVENTION, TraceEntry, diff_fields


class CounterfactualError(Exception):
    """Raised for invalid branch points, interventions or replay misuse."""


@dataclass(frozen=True)
class Intervention:
    """
    Replacement for one historical event: "what if this message had been different?"

    Attributes:
        iteration: Iteration of the event to replace (the branch point)
        tag: Replacement PXP tag
        prediction: Replacement prediction
        explanation: Replacement explanation
        agent_id: Author of the replacement (defaults to the original event's agent)
        confidence: Replacement confidence (optional)
        metadata: Replacement message metadata
        description: Human-readable summary of the change
    """

    iteration: int
    tag: PXPTag
    prediction: str
    explanation: str
    agent_id: str | None = None
    confidence: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.tag, str):
            object.__setattr__(self, "tag", PXPTag.from_string(self.tag))
        if self.iteration < 1:
            raise CounterfactualError("Intervention iteration must be >= 1")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "iteration": self.iteration,
            "tag": self.tag.value,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "agent_id": self.agent_id,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
            "description": self.description,
        }


@dataclass
class CounterfactualBranch:
    """
    An isolated alternative timeline.

    Attributes:
        branch_id: Identifier (unique within its engine)
        branch_point: First iteration that differs from (or is re-run relative to) the source
        intervention: The altered event, or None for a pure replay
        board: The branch's own Blackboard
        source_snapshot: Isolated snapshot of the source the branch was created from
        replaced_event: The source event the intervention replaced
        setup_trace: Trace entries for inherited events and the intervention
        initial_state: Branch state right after setup (before replay)
        initial_history: Branch history right after setup (before replay)
        result: Replay result, set by ``CounterfactualEngine.replay``
    """

    branch_id: str
    branch_point: int
    intervention: Intervention | None
    board: Blackboard
    source_snapshot: BlackboardSnapshot
    replaced_event: HistoryEvent | None
    setup_trace: list[TraceEntry]
    initial_state: dict[str, Any]
    initial_history: list[dict[str, Any]]
    result: SchedulerResult | None = None

    @property
    def replayed(self) -> bool:
        return self.result is not None

    def get_trace_entries(self) -> list[TraceEntry]:
        """Setup entries followed by the replay's scheduler entries."""
        replay = self.result.trace if self.result is not None else []
        return list(self.setup_trace) + list(replay)

    def get_trace(self) -> list[dict[str, Any]]:
        """Full branch trace as JSON-serializable dicts."""
        return [entry.to_dict() for entry in self.get_trace_entries()]

    def to_dict(self) -> dict[str, Any]:
        """
        Replay record: configuration, initial state, event sequence and outcome.
        """
        return {
            "branch_id": self.branch_id,
            "branch_point": self.branch_point,
            "intervention": self.intervention.to_dict() if self.intervention else None,
            "replaced_event": (
                _event_signature(self.replaced_event) if self.replaced_event else None
            ),
            "source": {
                "task": self.source_snapshot.state.task,
                "status": self.source_snapshot.state.status.value,
                "iteration": self.source_snapshot.state.iteration,
            },
            "initial_state": self.initial_state,
            "initial_history": self.initial_history,
            "replayed": self.replayed,
            "config": self.result.config if self.result else None,
            "policy": self.result.policy if self.result else None,
            "trace": self.get_trace(),
            "result": self.result.to_dict() if self.result else None,
        }


@dataclass(frozen=True)
class BranchComparison:
    """
    Structured original-vs-counterfactual comparison.

    ``shared_prefix`` counts leading history events that are identical in both
    runs (same agent, tag, prediction, explanation, confidence);
    ``divergence_iteration`` is the first iteration where they differ.
    """

    branch_id: str
    branch_point: int
    intervention: dict[str, Any] | None
    original_status: str
    counterfactual_status: str
    original_prediction: str | None
    counterfactual_prediction: str | None
    original_iterations: int
    counterfactual_iterations: int
    original_deadlocked: bool
    counterfactual_deadlocked: bool
    original_consensus: bool
    counterfactual_consensus: bool
    status_changed: bool
    prediction_changed: bool
    shared_prefix: int
    divergence_iteration: int | None
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "branch_id": self.branch_id,
            "branch_point": self.branch_point,
            "intervention": self.intervention,
            "original_status": self.original_status,
            "counterfactual_status": self.counterfactual_status,
            "original_prediction": self.original_prediction,
            "counterfactual_prediction": self.counterfactual_prediction,
            "original_iterations": self.original_iterations,
            "counterfactual_iterations": self.counterfactual_iterations,
            "original_deadlocked": self.original_deadlocked,
            "counterfactual_deadlocked": self.counterfactual_deadlocked,
            "original_consensus": self.original_consensus,
            "counterfactual_consensus": self.counterfactual_consensus,
            "status_changed": self.status_changed,
            "prediction_changed": self.prediction_changed,
            "shared_prefix": self.shared_prefix,
            "divergence_iteration": self.divergence_iteration,
            "summary": self.summary,
        }


@dataclass
class CounterfactualOutcome:
    """Everything produced by ``CounterfactualEngine.run_counterfactual``."""

    branch: CounterfactualBranch
    result: SchedulerResult
    comparison: BranchComparison

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {"branch": self.branch.to_dict(), "comparison": self.comparison.to_dict()}


def _event_signature(event: HistoryEvent | dict[str, Any]) -> dict[str, Any]:
    """Content of an event without timestamp/message id, for comparisons and traces."""
    data = event.to_dict() if isinstance(event, HistoryEvent) else event
    return {
        "iteration": data["iteration"],
        "agent_id": data["agent_id"],
        "tag": data["tag"],
        "prediction": data["prediction"],
        "explanation": data["explanation"],
        "confidence": data.get("confidence"),
    }


def _content(event: dict[str, Any]) -> tuple:
    sig = _event_signature(event)
    return (sig["agent_id"], sig["tag"], sig["prediction"], sig["explanation"], sig["confidence"])


def _message_from_event(event: HistoryEvent) -> PXPMessage:
    """Rebuild a publishable PXP message from a history event (metadata is not in history)."""
    return PXPMessage(
        message_id=event.message_id or f"inherited-it{event.iteration:03d}",
        agent_id=event.agent_id,
        tag=PXPTag.from_string(event.tag),
        prediction=event.prediction,
        explanation=event.explanation,
        confidence=event.confidence,
        iteration=event.iteration,
        timestamp=event.timestamp,
    )


class CounterfactualEngine:
    """
    Creates isolated branches, replays them with a Scheduler, and compares outcomes.

    Example:
        engine = CounterfactualEngine()
        branch = engine.create_branch(original_board, Intervention(iteration=2, ...))
        cf_result = engine.replay(branch, agents, policy, config)
        comparison = engine.compare(original_result, branch)
    """

    def __init__(self) -> None:
        self._branches: dict[str, CounterfactualBranch] = {}
        self._counter = 0

    @property
    def branches(self) -> list[CounterfactualBranch]:
        """Branches created by this engine, in creation order."""
        return list(self._branches.values())

    def get_branch(self, branch_id: str) -> CounterfactualBranch:
        """Return a branch by id; raises KeyError if unknown."""
        return self._branches[branch_id]

    def create_branch(
        self,
        source: Blackboard | BlackboardSnapshot,
        intervention: Intervention | None = None,
        *,
        branch_point: int | None = None,
        branch_id: str | None = None,
    ) -> CounterfactualBranch:
        """
        Create an isolated branch of ``source``.

        Args:
            source: Original Blackboard (read via ``snapshot()`` only) or a snapshot
            intervention: Event replacement; its iteration is the branch point
            branch_point: Required for a pure replay (no intervention): events
                before this iteration are inherited, the rest is re-run
            branch_id: Optional explicit id (default "cf-<n>")

        Returns:
            CounterfactualBranch ready for ``replay``

        Raises:
            CounterfactualError: Invalid branch point / intervention / duplicate id
        """
        if intervention is not None:
            if branch_point is not None and branch_point != intervention.iteration:
                raise CounterfactualError(
                    f"branch_point {branch_point} != intervention.iteration "
                    f"{intervention.iteration}"
                )
            branch_point = intervention.iteration
        if branch_point is None:
            raise CounterfactualError("Provide an intervention or a branch_point")

        if branch_id is None:
            self._counter += 1
            branch_id = f"cf-{self._counter}"
        if branch_id in self._branches:
            raise CounterfactualError(f"Branch '{branch_id}' already exists")

        # Isolated copy: the original is never touched again
        if isinstance(source, Blackboard):
            snapshot = source.snapshot()
        else:
            snapshot = BlackboardSnapshot(source.state, source.history, source.timestamp)
        history = snapshot.history

        last_iteration = max((e.iteration for e in history), default=0)
        replaced: HistoryEvent | None = None
        if intervention is not None:
            matches = [e for e in history if e.iteration == branch_point]
            if len(matches) != 1:
                raise CounterfactualError(
                    f"Expected exactly one event at iteration {branch_point}, found {len(matches)}"
                )
            replaced = matches[0]
        elif not 1 <= branch_point <= last_iteration + 1:
            raise CounterfactualError(
                f"branch_point must be between 1 and {last_iteration + 1}, got {branch_point}"
            )

        board = Blackboard()
        metadata = dict(snapshot.state.metadata)
        metadata["counterfactual"] = {
            "branch_id": branch_id,
            "branch_point": branch_point,
            "source_iteration": snapshot.state.iteration,
            "source_status": snapshot.state.status.value,
            "intervention": intervention.to_dict() if intervention else None,
        }
        board.initialize_task(snapshot.state.task, metadata)

        setup_trace: list[TraceEntry] = []
        for event in history:
            if event.iteration >= branch_point:
                continue
            board.publish_message(_message_from_event(event))
            setup_trace.append(
                TraceEntry(
                    step=board.get_iteration(),
                    kind=KIND_INHERITED,
                    event=event.tag,
                    agent=event.agent_id,
                    prediction=event.prediction,
                    explanation=event.explanation,
                    confidence=event.confidence,
                    message_id=event.message_id,
                    reason="Inherited unchanged from the original run",
                    status=board.get_state().status.value,
                )
            )

        if intervention is not None and replaced is not None:
            message = PXPMessage.create(
                agent_id=intervention.agent_id or replaced.agent_id,
                tag=intervention.tag,
                prediction=intervention.prediction,
                explanation=intervention.explanation,
                confidence=intervention.confidence,
                iteration=board.get_iteration() + 1,
                metadata={
                    **intervention.metadata,
                    "counterfactual": True,
                    "branch_id": branch_id,
                    "replaces_message_id": replaced.message_id,
                },
                message_id=f"{branch_id}-it{branch_point:03d}",
            )
            board.publish_message(message)
            original_sig = _event_signature(replaced)
            new_sig = _event_signature(board.get_history()[-1])
            setup_trace.append(
                TraceEntry(
                    step=board.get_iteration(),
                    kind=KIND_INTERVENTION,
                    event=message.tag.value,
                    agent=message.agent_id,
                    prediction=message.prediction,
                    explanation=message.explanation,
                    confidence=message.confidence,
                    message_id=message.message_id,
                    reason=intervention.description
                    or f"Counterfactual replacement of iteration {branch_point}",
                    status=board.get_state().status.value,
                    changes=diff_fields(original_sig, new_sig),
                    details={"replaced": original_sig},
                )
            )

        branch = CounterfactualBranch(
            branch_id=branch_id,
            branch_point=branch_point,
            intervention=intervention,
            board=board,
            source_snapshot=snapshot,
            replaced_event=replaced,
            setup_trace=setup_trace,
            initial_state=board.get_state().to_dict(),
            initial_history=[e.to_dict() for e in board.get_history()],
        )
        self._branches[branch_id] = branch
        return branch

    def replay(
        self,
        branch: CounterfactualBranch,
        agents: AgentsInput,
        policy: SchedulingPolicy | None = None,
        config: SchedulerConfig | None = None,
        max_steps: int | None = None,
    ) -> SchedulerResult:
        """
        Run the future of a branch with a Scheduler on the branch's own board.

        Use the same agents/policy/config as the original run to isolate the
        effect of the intervention. A branch can be replayed once; create a
        new branch to replay again.

        Raises:
            CounterfactualError: If the branch was already replayed
        """
        if branch.replayed:
            raise CounterfactualError(
                f"Branch '{branch.branch_id}' was already replayed; create a new branch"
            )
        scheduler = Scheduler(branch.board, agents, policy, config)
        branch.result = scheduler.run(max_steps)
        return branch.result

    def compare(self, original: SchedulerResult, branch: CounterfactualBranch) -> BranchComparison:
        """
        Compare an original run with a replayed branch.

        Args:
            original: Result of the original run (e.g. ``scheduler.get_result()``)
            branch: A replayed CounterfactualBranch

        Raises:
            CounterfactualError: If the branch has not been replayed
        """
        if branch.result is None:
            raise CounterfactualError(f"Branch '{branch.branch_id}' has not been replayed")
        cf = branch.result

        shared = 0
        for a, b in zip(original.history, cf.history, strict=False):
            if _content(a) != _content(b):
                break
            shared += 1
        identical = shared == len(original.history) == len(cf.history)
        divergence = None if identical else shared + 1

        if branch.replaced_event is not None:
            changed = (
                f"Changing iteration {branch.branch_point} "
                f"({branch.replaced_event.agent_id} {branch.replaced_event.tag} "
                f"'{branch.replaced_event.prediction}')"
            )
        else:
            changed = f"Replaying from iteration {branch.branch_point} without changes"
        summary = (
            f"{changed}: original {original.status} on '{original.final_prediction}' after "
            f"{original.iterations} iteration(s); counterfactual {cf.status} on "
            f"'{cf.final_prediction}' after {cf.iterations} iteration(s)."
        )

        return BranchComparison(
            branch_id=branch.branch_id,
            branch_point=branch.branch_point,
            intervention=branch.intervention.to_dict() if branch.intervention else None,
            original_status=original.status,
            counterfactual_status=cf.status,
            original_prediction=original.final_prediction,
            counterfactual_prediction=cf.final_prediction,
            original_iterations=original.iterations,
            counterfactual_iterations=cf.iterations,
            original_deadlocked=original.deadlocked,
            counterfactual_deadlocked=cf.deadlocked,
            original_consensus=original.consensus_reached,
            counterfactual_consensus=cf.consensus_reached,
            status_changed=original.status != cf.status,
            prediction_changed=original.final_prediction != cf.final_prediction,
            shared_prefix=shared,
            divergence_iteration=divergence,
            summary=summary,
        )

    def run_counterfactual(
        self,
        source: Blackboard | BlackboardSnapshot,
        original: SchedulerResult,
        agents: AgentsInput,
        intervention: Intervention | None = None,
        *,
        branch_point: int | None = None,
        policy: SchedulingPolicy | None = None,
        config: SchedulerConfig | None = None,
    ) -> CounterfactualOutcome:
        """Convenience: create_branch + replay + compare in one call."""
        branch = self.create_branch(source, intervention, branch_point=branch_point)
        result = self.replay(branch, agents, policy, config)
        return CounterfactualOutcome(branch, result, self.compare(original, branch))
