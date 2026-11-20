"""
The Blackboard: the shared, thread-safe, event-sourced state of one session.

Writes go through four methods, all serialized by one lock:

    initialize_task   the task, its options, the team and their voting weights
    commit            a PXP message, checked by the grammar and, if
                      ``expected_version`` is given, against the board version
                      the agent read (optimistic concurrency: a stale write
                      raises VersionConflict instead of overwriting)
    set_status / set_weight / revise_context   state changes made by the
                      scheduler and the counterfactual layer
    record            events that change no state (activations, tool calls,
                      interventions, rejected messages)

Each write becomes one ``BoardEvent``: it is applied to the state, appended
to the store, and only then passed to subscribers (outside the lock).
"""

import copy
import itertools
import logging
import threading
from collections.abc import Callable, Iterable
from typing import Any

from ai_project.blackboard.exceptions import (
    BlackboardError,
    BlackboardNotInitializedError,
    InvalidMessageError,
    InvalidStatusTransitionError,
    VersionConflict,
)
from ai_project.blackboard.models import (
    CONTEXT_REVISION,
    MESSAGE,
    RECORD_KINDS,
    STATUS,
    STATUS_TRANSITIONS,
    TASK,
    WEIGHT,
    BlackboardSnapshot,
    BlackboardState,
    BlackboardStatus,
    BoardEvent,
    MessageRecord,
    apply_event,
)
from ai_project.blackboard.store import BoardStore, MemoryStore
from ai_project.protocol.grammar import GrammarContext, Position, PXPGrammar
from ai_project.protocol.pxp import PXPMessage

Subscriber = Callable[[BoardEvent], None]
logger = logging.getLogger(__name__)
_session_counter = itertools.count(1)


class Blackboard:
    """
    Args:
        store: Where events are persisted (default: a private MemoryStore)
        session_id: Session key in the store (default: generated)
        grammar: PXP grammar used by ``commit`` (default: k = 3)
    """

    def __init__(
        self,
        store: BoardStore | None = None,
        session_id: str | None = None,
        grammar: PXPGrammar | None = None,
    ) -> None:
        self.store = store if store is not None else MemoryStore()
        self.session_id = session_id or f"session-{next(_session_counter):05d}"
        self.grammar = grammar or PXPGrammar()
        self._state = BlackboardState()
        self._events: list[BoardEvent] = []
        self._messages: list[MessageRecord] = []
        self._lock = threading.RLock()
        self._subscribers: list[Subscriber] = []

    # ------------------------------------------------------------------ construction

    @classmethod
    def from_events(
        cls,
        events: Iterable[BoardEvent],
        store: BoardStore | None = None,
        session_id: str | None = None,
        grammar: PXPGrammar | None = None,
        persist: bool = False,
    ) -> "Blackboard":
        """
        Rebuild a board by applying ``events`` in order.

        With ``persist=True`` the events are also written to ``store`` (used
        to seed a sandbox); otherwise the store is assumed to hold them already.
        """
        board = cls(store=store, session_id=session_id, grammar=grammar)
        for event in events:
            board._append(event, persist=persist)
        return board

    @classmethod
    def load(cls, store: BoardStore, session_id: str,
             grammar: PXPGrammar | None = None) -> "Blackboard":
        """Reopen a stored session."""
        return cls.from_events(store.load(session_id), store=store, session_id=session_id,
                               grammar=grammar)

    # ------------------------------------------------------------------ writes

    def initialize_task(
        self,
        task: str,
        metadata: dict[str, Any] | None = None,
        agents: Iterable[str] = (),
        weights: dict[str, float] | None = None,
    ) -> None:
        with self._lock:
            if self._events:
                raise BlackboardError("Task already initialized; use a new Blackboard per session")
            event = self._write(TASK, {
                "task": task,
                "metadata": copy.deepcopy(metadata or {}),
                "agents": list(agents),
                "weights": dict(weights or {}),
            })
        self._notify(event)

    def commit(self, message: PXPMessage, expected_version: int | None = None) -> MessageRecord:
        """
        Commit a PXP message.

        Raises:
            VersionConflict: ``expected_version`` is given and the board moved on
            InvalidMessageError: The grammar rejects the message (nothing changes)
            BlackboardError: The session is not accepting messages
        """
        with self._lock:
            self._require_task()
            if expected_version is not None and expected_version != self._state.version:
                raise VersionConflict(expected_version, self._state.version)
            if self._state.status not in (BlackboardStatus.INITIALIZED, BlackboardStatus.RUNNING):
                raise BlackboardError(
                    f"Session is {self._state.status.value}; it does not accept messages"
                )
            ctx = self._grammar_context(message.agent_id)
            violations = self.grammar.check(message, ctx)
            if violations:
                raise InvalidMessageError(
                    "PXP grammar violation: " + "; ".join(str(v) for v in violations),
                    violations,
                )
            peer = self._peer_message(message.agent_id)
            record = MessageRecord.from_dict({
                **message.to_dict(),
                "iteration": ctx.j,
                "in_reply_to": peer.message_id if peer else None,
            })
            event = self._write(MESSAGE, {"message": record.to_dict()})
        self._notify(event)
        return MessageRecord.from_dict(event.data["message"])

    def set_status(self, status: BlackboardStatus, reason: str = "",
                   details: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._require_task()
            current = self._state.status
            if status not in STATUS_TRANSITIONS[current]:
                raise InvalidStatusTransitionError(
                    f"Invalid status transition: {current.value} -> {status.value}"
                )
            event = self._write(STATUS, {
                "status": status.value,
                "previous": current.value,
                "reason": reason,
                "details": copy.deepcopy(details or {}),
            })
        self._notify(event)

    def set_weight(self, agent_id: str, weight: float, reason: str = "") -> None:
        if weight < 0:
            raise ValueError("weight must be >= 0")
        with self._lock:
            self._require_task()
            previous = self._state.weights.get(agent_id, 1.0)
            event = self._write(WEIGHT, {
                "agent_id": agent_id, "weight": float(weight), "previous": previous,
                "reason": reason,
            })
        self._notify(event)

    def revise_context(self, agent_id: str, prediction: str, explanation: str,
                       reason: str = "") -> None:
        """Replace an agent's position without a message (counterfactual intervention)."""
        with self._lock:
            self._require_task()
            previous = self._state.positions.get(agent_id)
            event = self._write(CONTEXT_REVISION, {
                "agent_id": agent_id,
                "prediction": prediction,
                "explanation": explanation,
                "previous": copy.deepcopy(previous),
                "reason": reason,
            })
        self._notify(event)

    def record(self, kind: str, data: dict[str, Any]) -> BoardEvent:
        """Append an event that changes no state."""
        if kind not in RECORD_KINDS:
            raise ValueError(f"record() takes one of {RECORD_KINDS}, not '{kind}'")
        with self._lock:
            self._require_task()
            event = self._write(kind, copy.deepcopy(data))
        self._notify(event)
        return event

    # ------------------------------------------------------------------ reads

    def get_state(self) -> BlackboardState:
        with self._lock:
            self._require_task()
            return copy.deepcopy(self._state)

    @property
    def version(self) -> int:
        with self._lock:
            return self._state.version

    @property
    def iteration(self) -> int:
        with self._lock:
            return self._state.iteration

    @property
    def status(self) -> BlackboardStatus:
        with self._lock:
            return self._state.status

    def get_messages(self) -> list[MessageRecord]:
        with self._lock:
            return list(self._messages)

    def get_events(self, since: int = 0) -> list[BoardEvent]:
        """Events with seq > ``since``."""
        with self._lock:
            return list(self._events[since:])

    def grammar_context(self, agent_id: str) -> GrammarContext:
        """What the grammar will check ``agent_id``'s next message against."""
        with self._lock:
            self._require_task()
            return self._grammar_context(agent_id)

    def peer_message(self, agent_id: str) -> MessageRecord | None:
        """Latest message from an agent other than ``agent_id``."""
        with self._lock:
            return self._peer_message(agent_id)

    def position(self, agent_id: str) -> Position | None:
        with self._lock:
            return self._state.position(agent_id)

    def state_at(self, version: int) -> BlackboardState:
        """State after the first ``version`` events (for stepping through a session)."""
        with self._lock:
            if not 0 <= version <= len(self._events):
                raise ValueError(f"version must be between 0 and {len(self._events)}")
            state = BlackboardState()
            for event in self._events[:version]:
                apply_event(state, event)
            return state

    def snapshot(self) -> BlackboardSnapshot:
        with self._lock:
            self._require_task()
            return BlackboardSnapshot(state=self._state, events=self._events)

    # ------------------------------------------------------------------ subscription

    def subscribe(self, callback: Subscriber) -> Callable[[], None]:
        """Call ``callback(event)`` after every write. Returns an unsubscribe function."""
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    # ------------------------------------------------------------------ internals

    def _require_task(self) -> None:
        if not self._events:
            raise BlackboardNotInitializedError("No task: call initialize_task() first")

    def _peer_message(self, agent_id: str) -> MessageRecord | None:
        for record in reversed(self._messages):
            if record.agent_id != agent_id:
                return record
        return None

    def _grammar_context(self, agent_id: str) -> GrammarContext:
        peer = self._peer_message(agent_id)
        return GrammarContext(
            j=self._state.iteration + 1,
            peer=peer.position if peer else None,
            own=self._state.position(agent_id),
            options=self._state.options,
        )

    def _write(self, kind: str, data: dict[str, Any]) -> BoardEvent:
        event = BoardEvent(seq=self._state.version + 1, kind=kind, data=data)
        self._append(event, persist=True)
        return event

    def _append(self, event: BoardEvent, persist: bool) -> None:
        with self._lock:
            if event.seq != self._state.version + 1:
                raise BlackboardError(
                    f"Event seq {event.seq} does not follow version {self._state.version}"
                )
            if persist:
                self.store.append(self.session_id, event)
            apply_event(self._state, event)
            self._events.append(event)
            if event.kind == MESSAGE:
                self._messages.append(MessageRecord.from_dict(event.data["message"]))

    def _notify(self, event: BoardEvent) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:  # a broken listener (e.g. a closed socket) must not stop the session
                logger.exception("Blackboard subscriber failed on event %s", event.seq)
