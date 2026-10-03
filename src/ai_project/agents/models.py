"""
The agent contract.

    AgentContext   what the agent sees   (built from the Blackboard + its private evidence)
    AgentDecision  what the agent decides (parsed from the provider's structured output)
    PXPMessage     what is published     (AgentDecision + agent id + iteration)
"""

from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard.models import HistoryEvent
from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.tasks import Evidence

# Metadata key for the option an objection points to instead (see PXPTag)
ALTERNATIVE_KEY = "alternative"


@dataclass(frozen=True)
class AgentContext:
    """
    Everything an agent reasons over for one decision.

    Attributes:
        agent_id: The deciding agent
        role: "analyst", "critic" or "specialist"
        task: Task question (public, from the Blackboard)
        options: Option names (public, from the Blackboard)
        evidence: This agent's private evidence
        status: Blackboard status
        iteration: Blackboard iteration
        proposal: Standing proposal (None if nothing proposed yet)
        history: Blackboard history up to now
        reflect_on: Set only for counterfactual reflection: the agent's own past
            event it is asked to reconsider, with ``history`` being the full
            history of the run that followed
    """

    agent_id: str
    role: str
    task: str
    options: tuple[str, ...]
    evidence: Evidence
    status: str
    iteration: int
    proposal: str | None
    history: tuple[HistoryEvent, ...]
    reflect_on: HistoryEvent | None = None

    @property
    def latest(self) -> HistoryEvent | None:
        return self.history[-1] if self.history else None

    @property
    def is_reflection(self) -> bool:
        return self.reflect_on is not None


@dataclass
class AgentDecision:
    """A validated decision: PXP tag, prediction, explanation, confidence, metadata."""

    tag: PXPTag
    prediction: str
    explanation: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

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

    @property
    def alternative(self) -> str | None:
        return self.metadata.get(ALTERNATIVE_KEY)

    def to_pxp_message(self, agent_id: str, iteration: int) -> PXPMessage:
        """Convert to a PXPMessage for Blackboard publication."""
        return PXPMessage.create(
            agent_id=agent_id,
            tag=self.tag,
            prediction=self.prediction,
            explanation=self.explanation,
            confidence=self.confidence,
            iteration=iteration,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary (the provider output schema)."""
        return {
            "tag": self.tag.value,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }
