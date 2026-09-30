from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class PXPTag(Enum):
    """PXP interaction tags for agent communication."""

    RATIFY = "RATIFY"
    REVISE = "REVISE"
    REFUTE = "REFUTE"
    REJECT = "REJECT"

    @classmethod
    def from_string(cls, value: str) -> "PXPTag":
        """Create PXPTag from string, case-insensitive."""
        try:
            return cls[value.upper()]
        except KeyError:
            raise ValueError(f"Invalid PXP tag: {value}. Valid tags: {[t.value for t in cls]}")


@dataclass
class PXPMessage:
    """
    Structured PXP message for agent communication via Blackboard.

    Attributes:
        message_id: Unique identifier for this message
        agent_id: Identifier of the agent that created this message
        tag: PXP interaction tag (RATIFY, REVISE, REFUTE, REJECT)
        prediction: The agent's prediction/decision
        explanation: Reasoning supporting the prediction
        confidence: Confidence score between 0.0 and 1.0 (optional)
        iteration: Iteration number when this message was created
        timestamp: ISO format timestamp of message creation
        metadata: Additional arbitrary data
    """

    message_id: str
    agent_id: str
    tag: PXPTag
    prediction: str
    explanation: str
    confidence: Optional[float] = None
    iteration: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if isinstance(self.tag, str):
            self.tag = PXPTag.from_string(self.tag)
        if self.confidence is not None:
            self.confidence = float(self.confidence)
        self.iteration = int(self.iteration)
        if not self.message_id:
            self.message_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "message_id": self.message_id,
            "agent_id": self.agent_id,
            "tag": self.tag.value,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PXPMessage":
        """Create PXPMessage from dictionary."""
        return cls(
            message_id=data["message_id"],
            agent_id=data["agent_id"],
            tag=PXPTag.from_string(data["tag"]),
            prediction=data["prediction"],
            explanation=data["explanation"],
            confidence=data.get("confidence"),
            iteration=data.get("iteration", 0),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def create(
        cls,
        agent_id: str,
        tag: PXPTag,
        prediction: str,
        explanation: str,
        confidence: Optional[float] = None,
        iteration: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> "PXPMessage":
        """Factory method to create a new PXPMessage with auto-generated fields."""
        return cls(
            message_id=message_id or f"msg_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            tag=tag,
            prediction=prediction,
            explanation=explanation,
            confidence=confidence,
            iteration=iteration,
            metadata=metadata or {},
        )