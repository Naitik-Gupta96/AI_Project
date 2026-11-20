"""
Event-driven scheduler.

The scheduler subscribes to the Blackboard. Every state-changing event
(message, status, weight, context revision) wakes it; bursts of events are
coalesced into one *round*:

1. Stop if the session is terminal, or the message budget is spent.
2. Check consensus, then deadlock; if either holds, set the status and stop.
3. Rank all agents (``PriorityArbiter``) and record the ranking as an
   ``activation`` event.
4. Let the top ``max_concurrent_agents`` eligible agents draft in parallel,
   all reading board version v.
5. Commit the drafts in rank order with ``expected_version=v``. The first
   commit moves the board on, so later drafts raise ``VersionConflict``:
   they are discarded and recorded as ``collision`` events, and those agents
   are ranked again next round. With one agent per round (the default) there
   are no collisions and runs are deterministic.
6. Record tool calls and rejected attempts; an agent that fails
   ``max_failed_turns`` turns fails the session.

The commit in step 5 emits a message event, which wakes the next round.
``pause``, ``resume``, ``step`` and ``stop`` let a UI drive a live session.
"""

import queue
import threading
from collections.abc import Callable, Collection, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai_project.agents.models import Draft
from ai_project.blackboard import Blackboard, BlackboardStatus, VersionConflict
from ai_project.blackboard.models import (
    ACTIVATION,
    COLLISION,
    CONTEXT_REVISION,
    FORMAT_ERROR,
    INTERVENTION,
    MESSAGE,
    STATUS,
    TOOL,
    WEIGHT,
    BoardEvent,
)
from ai_project.deadlock import DeadlockConfig, DeadlockDetector, DeadlockReport
from ai_project.scheduler.arbiter import Activation, PriorityArbiter
from ai_project.scheduler.consensus import ConsensusConfig, ConsensusResult, evaluate_consensus

STOP_CONSENSUS = "consensus"
STOP_DEADLOCK = "deadlock"
STOP_FAILED = "failed"
STOP_MAX_MESSAGES = "max_messages"
STOP_STOPPED = "stopped"

TERMINAL = (BlackboardStatus.CONSENSUS, BlackboardStatus.DEADLOCK, BlackboardStatus.FAILED)
_WAKE_KINDS = {MESSAGE, STATUS, WEIGHT, CONTEXT_REVISION}
_WAKE, _STOP = "wake", "stop"


class SchedulableAgent(Protocol):
    agent_id: str
    role: str

    def act(self, board: Blackboard) -> Draft: ...


class SchedulerError(Exception):
    """Misconfiguration (no agents, duplicate ids)."""


@dataclass(frozen=True)
class SchedulerConfig:
    """
    Attributes:
        max_messages: Message budget for the session (n in the paper's interaction procedure)
        max_concurrent_agents: Agents drafting in parallel per round
        consensus: Consensus rule
        deadlock: Deadlock rules
        max_failed_turns: Turns without a grammatical message before an agent fails the session
        pace: Seconds to wait before each round (0 for experiments; >0 to watch a session live)
    """

    max_messages: int = 12
    max_concurrent_agents: int = 1
    consensus: ConsensusConfig = field(default_factory=ConsensusConfig)
    deadlock: DeadlockConfig = field(default_factory=DeadlockConfig)
    max_failed_turns: int = 3
    pace: float = 0.0

    def __post_init__(self) -> None:
        if self.max_messages < 1:
            raise ValueError("max_messages must be >= 1")
        if self.max_concurrent_agents < 1:
            raise ValueError("max_concurrent_agents must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_messages": self.max_messages,
            "max_concurrent_agents": self.max_concurrent_agents,
            "consensus": self.consensus.to_dict(),
            "deadlock": self.deadlock.to_dict(),
            "max_failed_turns": self.max_failed_turns,
            "pace": self.pace,
        }


@dataclass
class SchedulerResult:
    status: str
    stop_reason: str | None
    final_prediction: str | None
    messages: int
    rounds: int
    collisions: int
    failed_turns: dict[str, int]
    consensus: ConsensusResult
    deadlock: DeadlockReport
    error: str | None = None

    @property
    def consensus_reached(self) -> bool:
        return self.status == BlackboardStatus.CONSENSUS.value

    @property
    def deadlocked(self) -> bool:
        return self.status == BlackboardStatus.DEADLOCK.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stop_reason": self.stop_reason,
            "final_prediction": self.final_prediction,
            "messages": self.messages,
            "rounds": self.rounds,
            "collisions": self.collisions,
            "failed_turns": dict(self.failed_turns),
            "consensus": self.consensus.to_dict(),
            "deadlock": self.deadlock.to_dict(),
            "error": self.error,
        }


def epoch_start(events: Sequence[BoardEvent]) -> int:
    """Message number at the last applied counterfactual intervention (0 if none)."""
    iteration, start = 0, 0
    for event in events:
        if event.kind == MESSAGE:
            iteration = event.data["message"]["iteration"]
        elif event.kind == INTERVENTION and event.data.get("applied"):
            start = iteration
    return start


class RunControl:
    """
    Pause / step / stop for a running session, shared by every scheduler the
    session creates (a session starts a new scheduler after each intervention).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resume = threading.Event()
        self._resume.set()
        self._stopped = threading.Event()
        self._step_budget: int | None = None
        self._listeners: list[Callable[[], None]] = []

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        with self._lock:
            self._step_budget = None
        self._resume.set()

    def step(self) -> None:
        """While paused, allow exactly one more round."""
        with self._lock:
            self._step_budget = 1
        self._resume.set()

    def stop(self) -> None:
        self._stopped.set()
        self._resume.set()
        with self._lock:
            listeners = list(self._listeners)
        for wake in listeners:
            wake()

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()

    def sleep(self, seconds: float) -> None:
        """Wait ``seconds``, returning early if the run is stopped."""
        if seconds > 0:
            self._stopped.wait(seconds)

    def wait_turn(self) -> bool:
        """Block until the next round may run. False if the run was stopped."""
        self._resume.wait()
        if self.stopped:
            return False
        with self._lock:
            if self._step_budget is not None:
                self._step_budget -= 1
                if self._step_budget <= 0:
                    self._resume.clear()
                    self._step_budget = None
        return True

    def on_stop(self, wake: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(wake)

        def remove() -> None:
            with self._lock:
                if wake in self._listeners:
                    self._listeners.remove(wake)

        return remove


class Scheduler:
    """
    Args:
        board: Blackboard with the task initialized
        agents: The team, in registration order
        arbiter: Priority arbiter (default: ``PriorityArbiter()``)
        config: Scheduler configuration
        pending: Agents with a pending counterfactual intervention (they post next)
        control: Pause / step / stop (default: a private one)
    """

    def __init__(
        self,
        board: Blackboard,
        agents: Sequence[SchedulableAgent],
        arbiter: PriorityArbiter | None = None,
        config: SchedulerConfig | None = None,
        pending: Collection[str] = (),
        control: RunControl | None = None,
    ) -> None:
        if not agents:
            raise SchedulerError("The scheduler needs at least one agent")
        ids = [a.agent_id for a in agents]
        if len(set(ids)) != len(ids):
            raise SchedulerError(f"Duplicate agent ids: {ids}")
        board.get_state()  # fails fast if no task
        self.board = board
        self.agents = {a.agent_id: a for a in agents}
        self.arbiter = arbiter or PriorityArbiter()
        self.config = config or SchedulerConfig()
        self.detector = DeadlockDetector(self.config.deadlock)
        self.pending = set(pending)
        self.control = control or RunControl()
        self.rounds = 0
        self.collisions = 0
        self.failed_turns: dict[str, int] = dict.fromkeys(ids, 0)
        self.queue: list[Activation] = []
        self._inbox: queue.Queue[str] = queue.Queue()
        self._stop_reason: str | None = None
        self._error: str | None = None

    # ------------------------------------------------------------------ control

    def pause(self) -> None:
        self.control.pause()

    def resume(self) -> None:
        self.control.resume()

    def step(self) -> None:
        """While paused, allow exactly one more round."""
        self.control.step()

    def stop(self) -> None:
        self.control.stop()

    @property
    def paused(self) -> bool:
        return self.control.paused

    # ------------------------------------------------------------------ checks

    def check_consensus(self) -> ConsensusResult:
        state = self.board.get_state()
        return evaluate_consensus(self.board.get_messages(), state.agents or list(self.agents),
                                  state.weights, self.config.consensus)

    def check_deadlock(self) -> DeadlockReport:
        return self.detector.detect(self.board.get_messages(),
                                    epoch_start(self.board.get_events()))

    @property
    def finished(self) -> bool:
        return self.board.status in TERMINAL

    # ------------------------------------------------------------------ run loop

    def run(self) -> SchedulerResult:
        """Run rounds until the session is terminal, the budget is spent, or ``stop()``."""
        unsubscribe = self.board.subscribe(self._on_event)
        remove_stop = self.control.on_stop(lambda: self._inbox.put(_STOP))
        self._inbox.put(_WAKE)
        # Hard stop even if every turn fails: each message may cost a few failed rounds
        attempts_per_message = (self.config.max_failed_turns + 1) * len(self.agents)
        max_rounds = self.config.max_messages * attempts_per_message
        try:
            while True:
                token = self._inbox.get()
                while not self._inbox.empty():  # coalesce bursts of events
                    if self._inbox.get_nowait() == _STOP:
                        token = _STOP
                if token == _STOP or not self.control.wait_turn():
                    self._stop_reason = self._stop_reason or STOP_STOPPED
                    break
                self.control.sleep(self.config.pace)
                if self.control.stopped:
                    self._stop_reason = STOP_STOPPED
                    break
                if not self._round() or self.rounds >= max_rounds:
                    break
        finally:
            unsubscribe()
            remove_stop()
        return self.result()

    def _on_event(self, event: BoardEvent) -> None:
        if event.kind in _WAKE_KINDS:
            self._inbox.put(_WAKE)

    def _round(self) -> bool:
        """One scheduling round. Returns False when the run is over."""
        if self.finished:
            self._stop_reason = self._terminal_reason()
            return False
        if self._evaluate_termination():
            return False
        if self.board.iteration >= self.config.max_messages:
            self._stop_reason = STOP_MAX_MESSAGES
            return False

        self.rounds += 1
        agents = [(a.agent_id, a.role) for a in self.agents.values()]
        self.queue = self.arbiter.rank(agents, self.board.get_messages(), self.pending)
        selected = [a for a in self.queue if a.eligible][: self.config.max_concurrent_agents]
        if not selected:
            self._stop_reason = "idle"
            return False
        self.board.record(ACTIVATION, {
            "round": self.rounds,
            "ranking": [a.to_dict() for a in self.queue],
            "selected": [a.agent_id for a in selected],
        })

        version = self.board.version
        drafts = self._draft([a.agent_id for a in selected])
        committed = False
        for agent_id, draft in drafts:
            if draft.message is None:
                self._record_failure(agent_id, draft)
                continue
            try:
                record = self.board.commit(draft.message, expected_version=version)
            except VersionConflict as exc:
                self.collisions += 1
                self.board.record(COLLISION, {
                    "agent_id": agent_id, "expected_version": exc.expected,
                    "actual_version": exc.actual, "draft": draft.message.to_dict(),
                })
                continue
            committed = True
            self.pending.discard(agent_id)
            self.failed_turns[agent_id] = 0
            for call in draft.tool_calls:
                self.board.record(TOOL, {"agent_id": agent_id, "message_id": record.message_id,
                                         **call})
            if draft.rejected:
                self.board.record(FORMAT_ERROR, {"agent_id": agent_id, "recovered": True,
                                                 "rejected": draft.rejected})
        if self.board.status == BlackboardStatus.FAILED:
            self._stop_reason = STOP_FAILED
            return False
        if not committed:
            self._inbox.put(_WAKE)  # nothing changed on the board, so wake ourselves
        return True

    def _draft(self, agent_ids: list[str]) -> list[tuple[str, Draft]]:
        if len(agent_ids) == 1:
            return [(agent_ids[0], self._safe_act(agent_ids[0]))]
        with ThreadPoolExecutor(max_workers=len(agent_ids)) as pool:
            futures = [(a, pool.submit(self._safe_act, a)) for a in agent_ids]
            return [(a, f.result()) for a, f in futures]

    def _safe_act(self, agent_id: str) -> Draft:
        try:
            return self.agents[agent_id].act(self.board)
        except Exception as exc:  # an agent crash is a failed turn, not a crashed session
            return Draft(None, error=f"{type(exc).__name__}: {exc}")

    def _record_failure(self, agent_id: str, draft: Draft) -> None:
        self.failed_turns[agent_id] += 1
        self.board.record(FORMAT_ERROR, {
            "agent_id": agent_id, "recovered": False, "error": draft.error,
            "rejected": draft.rejected,
        })
        if self.failed_turns[agent_id] >= self.config.max_failed_turns:
            self._error = (f"{agent_id} produced no grammatical message in "
                           f"{self.failed_turns[agent_id]} consecutive turns: {draft.error}")
            self.board.set_status(BlackboardStatus.FAILED, self._error)

    def _evaluate_termination(self) -> bool:
        if not self.board.get_messages():
            return False
        consensus = self.check_consensus()
        if consensus.reached:
            self.board.set_status(BlackboardStatus.CONSENSUS, consensus.reason,
                                  {"consensus": consensus.to_dict()})
            self._stop_reason = STOP_CONSENSUS
            return True
        deadlock = self.check_deadlock()
        if deadlock.deadlocked:
            self.board.set_status(BlackboardStatus.DEADLOCK, deadlock.reason,
                                  {"deadlock": deadlock.to_dict()})
            self._stop_reason = STOP_DEADLOCK
            return True
        return False

    def _terminal_reason(self) -> str:
        return {
            BlackboardStatus.CONSENSUS: STOP_CONSENSUS,
            BlackboardStatus.DEADLOCK: STOP_DEADLOCK,
            BlackboardStatus.FAILED: STOP_FAILED,
        }[self.board.status]

    # ------------------------------------------------------------------ reporting

    def result(self) -> SchedulerResult:
        consensus = self.check_consensus()
        state = self.board.get_state()
        return SchedulerResult(
            status=state.status.value,
            stop_reason=self._stop_reason,
            final_prediction=consensus.prediction if consensus.reached else None,
            messages=state.iteration,
            rounds=self.rounds,
            collisions=self.collisions,
            failed_turns=dict(self.failed_turns),
            consensus=consensus,
            deadlock=self.check_deadlock(),
            error=self._error,
        )
