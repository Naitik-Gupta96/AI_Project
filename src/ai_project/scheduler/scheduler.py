"""
Scheduler: the event loop that turns agents + a Blackboard into a process.

Each ``step()``:

1. Stop if the board is already terminal (CONSENSUS / DEADLOCK / FAILED).
2. Move the board to RUNNING if it is still INITIALIZED.
3. Check consensus, then deadlock; if either holds, set the status and stop.
4. Ask the policy which agent acts next.
5. Invoke ``agent.act(board)`` and publish the returned PXP message
   (the Blackboard validates it).
6. Record a trace entry, then check consensus and deadlock again.

Only the Blackboard's public API is used.
"""

from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.deadlock import DeadlockConfig, DeadlockDetector, DeadlockReport, current_proposal
from ai_project.scheduler.consensus import ConsensusConfig, ConsensusResult, detect_consensus
from ai_project.scheduler.policies import RoundRobinPolicy, SchedulingContext, SchedulingPolicy
from ai_project.scheduler.registry import AgentRegistry, AgentsInput
from ai_project.scheduler.trace import (
    KIND_ACTION,
    KIND_CONSENSUS,
    KIND_DEADLOCK,
    KIND_ERROR,
    KIND_MAX_STEPS,
    TraceEntry,
    diff_fields,
)

STOP_CONSENSUS = "consensus"
STOP_DEADLOCK = "deadlock"
STOP_ERROR = "error"
STOP_MAX_STEPS = "max_steps"

TERMINAL_STATUSES = {
    BlackboardStatus.CONSENSUS: STOP_CONSENSUS,
    BlackboardStatus.DEADLOCK: STOP_DEADLOCK,
    BlackboardStatus.FAILED: STOP_ERROR,
}


class SchedulerError(Exception):
    """Raised for scheduler misconfiguration or contract violations."""


@dataclass(frozen=True)
class SchedulerConfig:
    """
    Scheduler configuration. Recorded with every result for reproducibility.

    Attributes:
        max_steps: Default agent-action budget for ``run()``
        consensus: Consensus thresholds
        deadlock: Deadlock thresholds
        seed: Recorded with results; the built-in policies and mock agents are
            deterministic and do not consume it
        raise_on_agent_error: If True, agent/publish exceptions propagate instead
            of setting the board to FAILED
    """

    max_steps: int = 20
    consensus: ConsensusConfig = field(default_factory=ConsensusConfig)
    deadlock: DeadlockConfig = field(default_factory=DeadlockConfig)
    seed: int | None = None
    raise_on_agent_error: bool = False

    def __post_init__(self) -> None:
        if self.max_steps < 0:
            raise ValueError("max_steps must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "max_steps": self.max_steps,
            "consensus": self.consensus.to_dict(),
            "deadlock": self.deadlock.to_dict(),
            "seed": self.seed,
            "raise_on_agent_error": self.raise_on_agent_error,
        }


@dataclass
class SchedulerResult:
    """
    Structured outcome of a scheduler run.

    Attributes:
        status: Final board status value
        stop_reason: consensus / deadlock / error / max_steps (None if still running)
        final_prediction: Standing proposal at the end (the agreed prediction on
            consensus, the contested one on deadlock)
        iterations: Board iteration at the end
        steps: Agent actions performed by this scheduler
        consensus: Last consensus check
        deadlock: Last deadlock check
        trace: Scheduler trace entries
        state: Final board state (serialized)
        history: Final board history (serialized)
        config: Scheduler configuration (serialized)
        policy: Policy description
        error: Error message if the run failed
    """

    status: str
    stop_reason: str | None
    final_prediction: str | None
    iterations: int
    steps: int
    consensus: ConsensusResult
    deadlock: DeadlockReport
    trace: list[TraceEntry]
    state: dict[str, Any]
    history: list[dict[str, Any]]
    config: dict[str, Any]
    policy: dict[str, Any]
    error: str | None = None

    @property
    def consensus_reached(self) -> bool:
        return self.status == BlackboardStatus.CONSENSUS.value

    @property
    def deadlocked(self) -> bool:
        return self.status == BlackboardStatus.DEADLOCK.value

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "status": self.status,
            "stop_reason": self.stop_reason,
            "final_prediction": self.final_prediction,
            "iterations": self.iterations,
            "steps": self.steps,
            "consensus_reached": self.consensus_reached,
            "deadlocked": self.deadlocked,
            "consensus": self.consensus.to_dict(),
            "deadlock": self.deadlock.to_dict(),
            "trace": [entry.to_dict() for entry in self.trace],
            "state": self.state,
            "history": self.history,
            "config": self.config,
            "policy": self.policy,
            "error": self.error,
        }


class Scheduler:
    """
    Drives registered agents against a Blackboard until consensus, deadlock,
    failure, or the step budget.

    Example:
        board = Blackboard()
        board.initialize_task("Choose an option")
        scheduler = Scheduler(board, {"analyst": analyst, "critic": critic})
        result = scheduler.run(max_steps=10)
        result.status        # "CONSENSUS" / "DEADLOCK" / ...
        scheduler.get_trace()  # list of dicts for the UI
    """

    def __init__(
        self,
        board: Blackboard,
        agents: AgentsInput,
        policy: SchedulingPolicy | None = None,
        config: SchedulerConfig | None = None,
    ) -> None:
        """
        Args:
            board: Initialized Blackboard (raises BlackboardNotInitializedError otherwise)
            agents: AgentRegistry, {agent_id: agent} mapping, or iterable of agents
            policy: Selection policy (defaults to RoundRobinPolicy)
            config: Scheduler configuration (defaults to SchedulerConfig())

        Raises:
            SchedulerError: If no agents are given
        """
        board.get_state()  # fail fast if the board is not initialized
        self._board = board
        self._registry = AgentRegistry.from_input(agents)
        if len(self._registry) == 0:
            raise SchedulerError("Scheduler needs at least one agent")
        self._policy = policy or RoundRobinPolicy()
        self._config = config or SchedulerConfig()
        self._detector = DeadlockDetector(self._config.deadlock)
        self._trace: list[TraceEntry] = []
        self._steps = 0
        self._budget_exhausted = False
        self._error: str | None = None

    # ------------------------------------------------------------------ properties

    @property
    def board(self) -> Blackboard:
        return self._board

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def policy(self) -> SchedulingPolicy:
        return self._policy

    @property
    def config(self) -> SchedulerConfig:
        return self._config

    @property
    def steps(self) -> int:
        """Agent actions performed by this scheduler."""
        return self._steps

    @property
    def finished(self) -> bool:
        """True once the board is CONSENSUS, DEADLOCK or FAILED."""
        return self._board.get_state().status in TERMINAL_STATUSES

    @property
    def stop_reason(self) -> str | None:
        """consensus / deadlock / error when finished, max_steps after a budget stop, else None."""
        status = self._board.get_state().status
        if status in TERMINAL_STATUSES:
            return TERMINAL_STATUSES[status]
        return STOP_MAX_STEPS if self._budget_exhausted else None

    # ------------------------------------------------------------------ checks

    def check_consensus(self) -> ConsensusResult:
        """Evaluate the consensus rule against the board without changing it."""
        return detect_consensus(
            self._board.get_state(),
            self._board.get_history(),
            self._config.consensus,
            self._registry.agent_ids,
        )

    def check_deadlock(self) -> DeadlockReport:
        """Evaluate the deadlock rules against the board without changing it."""
        return self._detector.detect(self._board.get_history())

    # ------------------------------------------------------------------ execution

    def step(self) -> TraceEntry | None:
        """
        Perform one scheduling step.

        Returns:
            The trace entry produced (agent action, or the consensus/deadlock/error
            entry that ended the run), or None if the board was already terminal.
        """
        if self.finished:
            return None
        self._budget_exhausted = False
        before = self._state_view()  # captured first so the trace includes INITIALIZED -> RUNNING
        self._ensure_running()

        terminal = self._evaluate_termination()
        if terminal is not None:
            return terminal

        state = self._board.get_state()
        context = SchedulingContext(
            state=state,
            history=tuple(self._board.get_history()),
            agent_ids=self._registry.agent_ids,
            step=self._steps,
        )
        selection = self._policy.select(context)
        if selection.agent_id not in self._registry:
            raise SchedulerError(
                f"Policy '{self._policy.name}' selected unknown agent '{selection.agent_id}'"
            )
        agent = self._registry.get(selection.agent_id)

        try:
            message = agent.act(self._board)
            if message.agent_id != agent.agent_id:
                raise SchedulerError(
                    f"Agent '{agent.agent_id}' returned a message signed by '{message.agent_id}'"
                )
            self._board.publish_message(message)
        except Exception as exc:
            if self._config.raise_on_agent_error:
                raise
            return self._fail(selection.agent_id, selection.reason, exc, before)

        self._steps += 1
        after = self._state_view()
        entry = TraceEntry(
            step=after["iteration"],
            kind=KIND_ACTION,
            event=message.tag.value,
            agent=agent.agent_id,
            prediction=message.prediction,
            explanation=message.explanation,
            confidence=message.confidence,
            message_id=message.message_id,
            reason=selection.reason,
            policy=self._policy.name,
            status=after["status"],
            changes=diff_fields(before, after),
            details={"rule": selection.rule},
        )
        self._trace.append(entry)
        self._evaluate_termination()
        return entry

    def run(self, max_steps: int | None = None) -> SchedulerResult:
        """
        Step until the board is terminal or the action budget is spent.

        Args:
            max_steps: Agent actions allowed in this call (defaults to config.max_steps)

        Returns:
            SchedulerResult. If the budget ran out the board stays RUNNING,
            ``stop_reason`` is "max_steps", and ``run()`` can be called again.
        """
        budget = self._config.max_steps if max_steps is None else max_steps
        actions = 0
        while not self.finished and actions < budget:
            entry = self.step()
            if entry is None:
                break
            if entry.kind == KIND_ACTION:
                actions += 1

        if not self.finished:
            self._budget_exhausted = True
            state = self._board.get_state()
            self._trace.append(
                TraceEntry(
                    step=state.iteration,
                    kind=KIND_MAX_STEPS,
                    event="MAX_STEPS",
                    prediction=current_proposal(self._board.get_history()),
                    reason=f"Step budget of {budget} agent action(s) reached without "
                    f"consensus or deadlock",
                    policy=self._policy.name,
                    status=state.status.value,
                )
            )
        return self.get_result()

    # ------------------------------------------------------------------ reporting

    def get_trace_entries(self) -> list[TraceEntry]:
        """Trace as TraceEntry objects."""
        return list(self._trace)

    def get_trace(self) -> list[dict[str, Any]]:
        """Trace as JSON-serializable dicts (for the UI)."""
        return [entry.to_dict() for entry in self._trace]

    def get_status(self) -> dict[str, Any]:
        """Current scheduler/board status as a JSON-serializable dict."""
        state = self._board.get_state()
        history = self._board.get_history()
        return {
            "status": state.status.value,
            "finished": self.finished,
            "stop_reason": self.stop_reason,
            "iteration": state.iteration,
            "steps": self._steps,
            "current_prediction": state.current_prediction,
            "current_proposal": current_proposal(history),
            "last_agent": history[-1].agent_id if history else None,
            "agents": list(self._registry.agent_ids),
            "policy": self._policy.describe(),
            "consensus": self.check_consensus().to_dict(),
            "deadlock": self.check_deadlock().to_dict(),
            "error": self._error,
        }

    def get_result(self) -> SchedulerResult:
        """Structured result reflecting the board right now."""
        state = self._board.get_state()
        history = self._board.get_history()
        return SchedulerResult(
            status=state.status.value,
            stop_reason=self.stop_reason,
            final_prediction=current_proposal(history),
            iterations=state.iteration,
            steps=self._steps,
            consensus=self.check_consensus(),
            deadlock=self.check_deadlock(),
            trace=list(self._trace),
            state=state.to_dict(),
            history=[event.to_dict() for event in history],
            config=self._config.to_dict(),
            policy=self._policy.describe(),
            error=self._error,
        )

    # ------------------------------------------------------------------ internals

    def _state_view(self) -> dict[str, Any]:
        state = self._board.get_state()
        return {
            "iteration": state.iteration,
            "status": state.status.value,
            "current_prediction": state.current_prediction,
            "proposal": current_proposal(self._board.get_history()),
        }

    def _ensure_running(self) -> None:
        if self._board.get_state().status == BlackboardStatus.INITIALIZED:
            self._board.set_status(BlackboardStatus.RUNNING)

    def _evaluate_termination(self) -> TraceEntry | None:
        """Set CONSENSUS or DEADLOCK if a rule holds; return the recorded entry."""
        if not self._board.get_history():
            return None

        consensus = self.check_consensus()
        if consensus.reached:
            return self._set_terminal(
                BlackboardStatus.CONSENSUS,
                KIND_CONSENSUS,
                consensus.prediction,
                consensus.reason,
                {"consensus": consensus.to_dict()},
            )

        deadlock = self.check_deadlock()
        if deadlock.deadlocked:
            return self._set_terminal(
                BlackboardStatus.DEADLOCK,
                KIND_DEADLOCK,
                deadlock.contested_prediction,
                deadlock.reason,
                {"deadlock": deadlock.to_dict()},
            )
        return None

    def _set_terminal(
        self,
        status: BlackboardStatus,
        kind: str,
        prediction: str | None,
        reason: str,
        details: dict[str, Any],
    ) -> TraceEntry:
        before = self._state_view()
        self._board.set_status(status)
        after = self._state_view()
        entry = TraceEntry(
            step=after["iteration"],
            kind=kind,
            event=status.value,
            prediction=prediction,
            reason=reason,
            policy=self._policy.name,
            status=after["status"],
            changes=diff_fields(before, after),
            details=details,
        )
        self._trace.append(entry)
        return entry

    def _fail(
        self, agent_id: str, selection_reason: str, exc: Exception, before: dict[str, Any]
    ) -> TraceEntry:
        self._error = f"{type(exc).__name__}: {exc}"
        self._board.set_status(BlackboardStatus.FAILED)
        after = self._state_view()
        entry = TraceEntry(
            step=after["iteration"],
            kind=KIND_ERROR,
            event="ERROR",
            agent=agent_id,
            reason=f"{agent_id} failed: {self._error}",
            policy=self._policy.name,
            status=after["status"],
            changes=diff_fields(before, after),
            details={"selection_reason": selection_reason},
        )
        self._trace.append(entry)
        return entry
