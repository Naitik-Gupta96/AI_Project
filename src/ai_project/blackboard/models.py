from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import copy


class BlackboardStatus(Enum):
    """Blackboard task status."""

    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    CONSENSUS = "CONSENSUS"
    DEADLOCK = "DEADLOCK"
    FAILED = "FAILED"

    def __str__(self) -> str:
        return self.value


@dataclass
class BlackboardState:
    """
    Current state of the Blackboard.

    Attributes:
        task: The task description
        status: Current task status
        iteration: Current iteration number
        current_prediction: Latest prediction from accepted messages
        current_explanation: Latest explanation from accepted messages
        latest_message: The most recently accepted PXP message (serialized)
        metadata: Additional task metadata
    """

    task: str
    status: BlackboardStatus = BlackboardStatus.INITIALIZED
    iteration: int = 0
    current_prediction: str = ""
    current_explanation: str = ""
    latest_message: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "task": self.task,
            "status": self.status.value,
            "iteration": self.iteration,
            "current_prediction": self.current_prediction,
            "current_explanation": self.current_explanation,
            "latest_message": self.latest_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlackboardState":
        """Create BlackboardState from dictionary."""
        return cls(
            task=data["task"],
            status=BlackboardStatus(data["status"]),
            iteration=data.get("iteration", 0),
            current_prediction=data.get("current_prediction", ""),
            current_explanation=data.get("current_explanation", ""),
            latest_message=data.get("latest_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class HistoryEvent:
    """
    Immutable event record for the Blackboard history.

    Attributes:
        iteration: Iteration number when this event occurred
        agent_id: ID of the agent that caused this event
        tag: PXP tag of the message
        timestamp: ISO format timestamp
        prediction: Prediction from the message
        explanation: Explanation from the message
        confidence: Confidence from the message (optional)
        message_id: ID of the message that caused this event
    """

    iteration: int
    agent_id: str
    tag: str
    timestamp: str
    prediction: str
    explanation: str
    confidence: Optional[float] = None
    message_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "iteration": self.iteration,
            "agent_id": self.agent_id,
            "tag": self.tag,
            "timestamp": self.timestamp,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "message_id": self.message_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEvent":
        """Create HistoryEvent from dictionary."""
        return cls(
            iteration=data["iteration"],
            agent_id=data["agent_id"],
            tag=data["tag"],
            timestamp=data["timestamp"],
            prediction=data["prediction"],
            explanation=data["explanation"],
            confidence=data.get("confidence"),
            message_id=data.get("message_id", ""),
        )

    @classmethod
    def from_message(cls, message, iteration: int) -> "HistoryEvent":
        """Create HistoryEvent from a PXPMessage and iteration number."""
        from ai_project.protocol.pxp import PXPMessage
        if not isinstance(message, PXPMessage):
            raise TypeError("message must be a PXPMessage")
        return cls(
            iteration=iteration,
            agent_id=message.agent_id,
            tag=message.tag.value,
            timestamp=message.timestamp,
            prediction=message.prediction,
            explanation=message.explanation,
            confidence=message.confidence,
            message_id=message.message_id,
        )


@dataclass
class BlackboardSnapshot:
    """
    Independent snapshot of Blackboard state at a point in time.

    This is a deep copy - modifying the snapshot does not affect the live Blackboard.
    """

    state: BlackboardState
    history: List[HistoryEvent]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def __post_init__(self) -> None:
        """Ensure deep copies are used."""
        self.state = copy.deepcopy(self.state)
        self.history = copy.deepcopy(self.history)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "state": self.state.to_dict(),
            "history": [e.to_dict() for e in self.history],
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlackboardSnapshot":
        """Create BlackboardSnapshot from dictionary."""
        return cls(
            state=BlackboardState.from_dict(data["state"]),
            history=[HistoryEvent.from_dict(e) for e in data["history"]],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
        )