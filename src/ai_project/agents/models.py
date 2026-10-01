from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ai_project.protocol.pxp import PXPTag


@dataclass
class AgentDecision:
    """
    Internal structured representation of an agent's reasoning output.

    This is the contract between agent reasoning and PXP message creation.
    """

    tag: PXPTag
    prediction: str
    explanation: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.tag, str):
            self.tag = PXPTag.from_string(self.tag)
        self.confidence = float(self.confidence)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")
        if not self.prediction or not self.prediction.strip():
            raise ValueError("prediction must be non-empty")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("explanation must be non-empty")

    def to_pxp_message(self, agent_id: str, iteration: int) -> "PXPMessage":
        """Convert to a PXPMessage for Blackboard publication."""
        from ai_project.protocol.pxp import PXPMessage
        return PXPMessage.create(
            agent_id=agent_id,
            tag=self.tag,
            prediction=self.prediction,
            explanation=self.explanation,
            confidence=self.confidence,
            iteration=iteration,
            metadata=self.metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "tag": self.tag.value,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class AgentContext:
    """
    Structured context passed to agents for reasoning.

    Contains all information an agent needs to make a decision.
    """

    task: str
    current_prediction: str
    current_explanation: str
    status: str
    iteration: int
    recent_history: List["HistoryEvent"]
    agent_id: str
    agent_role: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_context(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for prompt templating."""
        return {
            "task": self.task,
            "current_prediction": self.current_prediction or "(none)",
            "current_explanation": self.current_explanation or "(none)",
            "status": self.status,
            "iteration": self.iteration,
            "recent_history": [
                {
                    "iteration": e.iteration,
                    "agent_id": e.agent_id,
                    "tag": e.tag,
                    "prediction": e.prediction,
                    "explanation": e.explanation,
                    "confidence": e.confidence,
                }
                for e in self.recent_history
            ],
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
        }


from ai_project.blackboard.models import HistoryEvent