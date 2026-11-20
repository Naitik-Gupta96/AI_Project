"""
Blackboard data model.

The Blackboard is event-sourced: every change is a ``BoardEvent`` appended to
the log, and ``BlackboardState`` is what you get by applying the log in order.
The same ``apply_event`` function is used for live writes and for rebuilding a
board from a store, so a replayed board is identical to the live one.

Event kinds and the state they change:

    task              task, metadata, agents, weights        (first event only)
    message           iteration, latest message, sender's position;
                      INITIALIZED -> RUNNING on the first message
    status            status
    weight            one agent's voting weight
    context_revision  one agent's position (after a counterfactual intervention)
    intervention      nothing (record of a counterfactual simulation)
    activation        nothing (scheduler's ranked queue for one round)
    collision         nothing (a draft discarded because the board moved on)
    tool              nothing (an agent's tool call and its result)
    format_error      nothing (a message the grammar rejected)
"""

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ai_project.protocol.grammar import Position
from ai_project.protocol.pxp import Judgment, PXPMessage, utc_timestamp

TASK = "task"
MESSAGE = "message"
STATUS = "status"
WEIGHT = "weight"
CONTEXT_REVISION = "context_revision"
INTERVENTION = "intervention"
ACTIVATION = "activation"
COLLISION = "collision"
TOOL = "tool"
FORMAT_ERROR = "format_error"

EVENT_KINDS = (
    TASK, MESSAGE, STATUS, WEIGHT, CONTEXT_REVISION,
    INTERVENTION, ACTIVATION, COLLISION, TOOL, FORMAT_ERROR,
)
#: Kinds that only record something; they never change state
RECORD_KINDS = (INTERVENTION, ACTIVATION, COLLISION, TOOL, FORMAT_ERROR)


class BlackboardStatus(Enum):
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    CONSENSUS = "CONSENSUS"
    DEADLOCK = "DEADLOCK"
    FAILED = "FAILED"

    def __str__(self) -> str:
        return self.value


#: Allowed status changes. DEADLOCK -> RUNNING happens only when a
#: counterfactual intervention resumes the session.
STATUS_TRANSITIONS: dict[BlackboardStatus, tuple[BlackboardStatus, ...]] = {
    BlackboardStatus.INITIALIZED: (BlackboardStatus.RUNNING, BlackboardStatus.FAILED),
    BlackboardStatus.RUNNING: (
        BlackboardStatus.CONSENSUS, BlackboardStatus.DEADLOCK, BlackboardStatus.FAILED,
    ),
    BlackboardStatus.DEADLOCK: (BlackboardStatus.RUNNING, BlackboardStatus.FAILED),
    BlackboardStatus.CONSENSUS: (),
    BlackboardStatus.FAILED: (),
}


@dataclass(frozen=True)
class BoardEvent:
    """One entry of the Blackboard log. ``seq`` starts at 1."""

    seq: int
    kind: str
    data: dict[str, Any]
    timestamp: str = field(default_factory=utc_timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "data": copy.deepcopy(self.data),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BoardEvent":
        return cls(
            seq=int(data["seq"]),
            kind=data["kind"],
            data=copy.deepcopy(data.get("data") or {}),
            timestamp=data.get("timestamp") or utc_timestamp(),
        )


@dataclass(frozen=True)
class MessageRecord:
    """A committed PXP message, as stored on the board."""

    iteration: int
    message_id: str
    agent_id: str
    tag: str
    prediction: str
    explanation: str
    confidence: float | None
    judgment: Judgment | None
    in_reply_to: str | None
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "message_id": self.message_id,
            "agent_id": self.agent_id,
            "tag": self.tag,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "judgment": self.judgment.to_dict() if self.judgment else None,
            "in_reply_to": self.in_reply_to,
            "timestamp": self.timestamp,
            "metadata": copy.deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageRecord":
        judgment = data.get("judgment")
        return cls(
            iteration=int(data["iteration"]),
            message_id=data["message_id"],
            agent_id=data["agent_id"],
            tag=data["tag"],
            prediction=data["prediction"],
            explanation=data["explanation"],
            confidence=data.get("confidence"),
            judgment=Judgment.from_dict(judgment) if judgment else None,
            in_reply_to=data.get("in_reply_to"),
            timestamp=data.get("timestamp") or utc_timestamp(),
            metadata=copy.deepcopy(data.get("metadata") or {}),
        )

    @classmethod
    def from_message(cls, message: PXPMessage) -> "MessageRecord":
        return cls.from_dict(message.to_dict())

    def to_message(self) -> PXPMessage:
        return PXPMessage.from_dict(self.to_dict())

    @property
    def position(self) -> Position:
        return Position(self.agent_id, self.prediction, self.explanation, self.message_id)


@dataclass
class BlackboardState:
    """
    State derived from the log.

    Attributes:
        task: Task text
        status: Session status
        version: Number of events applied (the log length)
        iteration: Number of committed PXP messages (the last message number j)
        agents: Registered agent ids, in order
        weights: Voting weight per agent
        positions: Each agent's current position (prediction, explanation, source)
        latest_message: The last committed message, serialized
        metadata: Task metadata (e.g. "options")
    """

    task: str = ""
    status: BlackboardStatus = BlackboardStatus.INITIALIZED
    version: int = 0
    iteration: int = 0
    agents: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    positions: dict[str, dict[str, str]] = field(default_factory=dict)
    latest_message: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def options(self) -> tuple[str, ...]:
        return tuple(self.metadata.get("options") or ())

    def position(self, agent_id: str) -> Position | None:
        p = self.positions.get(agent_id)
        if p is None:
            return None
        return Position(agent_id, p["prediction"], p["explanation"], p.get("source", ""))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "status": self.status.value,
            "version": self.version,
            "iteration": self.iteration,
            "agents": list(self.agents),
            "weights": dict(self.weights),
            "positions": copy.deepcopy(self.positions),
            "latest_message": copy.deepcopy(self.latest_message),
            "metadata": copy.deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlackboardState":
        return cls(
            task=data.get("task", ""),
            status=BlackboardStatus(data.get("status", "INITIALIZED")),
            version=int(data.get("version", 0)),
            iteration=int(data.get("iteration", 0)),
            agents=list(data.get("agents") or []),
            weights=dict(data.get("weights") or {}),
            positions=copy.deepcopy(data.get("positions") or {}),
            latest_message=copy.deepcopy(data.get("latest_message")),
            metadata=copy.deepcopy(data.get("metadata") or {}),
        )


def apply_event(state: BlackboardState, event: BoardEvent) -> None:
    """Apply one event to ``state`` in place (the single state-transition function)."""
    data = event.data
    if event.kind == TASK:
        state.task = data["task"]
        state.metadata = copy.deepcopy(data.get("metadata") or {})
        state.agents = list(data.get("agents") or [])
        state.weights = {a: float(w) for a, w in (data.get("weights") or {}).items()}
        for agent in state.agents:
            state.weights.setdefault(agent, 1.0)
    elif event.kind == MESSAGE:
        record = data["message"]
        state.iteration = int(record["iteration"])
        state.latest_message = copy.deepcopy(record)
        state.positions[record["agent_id"]] = {
            "prediction": record["prediction"],
            "explanation": record["explanation"],
            "source": record["message_id"],
        }
        if record["agent_id"] not in state.weights:
            state.weights[record["agent_id"]] = 1.0
        if state.status == BlackboardStatus.INITIALIZED:
            state.status = BlackboardStatus.RUNNING
    elif event.kind == STATUS:
        state.status = BlackboardStatus(data["status"])
    elif event.kind == WEIGHT:
        state.weights[data["agent_id"]] = float(data["weight"])
    elif event.kind == CONTEXT_REVISION:
        state.positions[data["agent_id"]] = {
            "prediction": data["prediction"],
            "explanation": data["explanation"],
            "source": f"revision@{event.seq}",
        }
    state.version = event.seq


@dataclass
class BlackboardSnapshot:
    """An isolated deep copy of a board's state and log."""

    state: BlackboardState
    events: list[BoardEvent]
    timestamp: str = field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        self.state = copy.deepcopy(self.state)
        self.events = copy.deepcopy(self.events)

    @property
    def messages(self) -> list[MessageRecord]:
        return [MessageRecord.from_dict(e.data["message"]) for e in self.events
                if e.kind == MESSAGE]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "events": [e.to_dict() for e in self.events],
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlackboardSnapshot":
        return cls(
            state=BlackboardState.from_dict(data["state"]),
            events=[BoardEvent.from_dict(e) for e in data["events"]],
            timestamp=data.get("timestamp") or utc_timestamp(),
        )
