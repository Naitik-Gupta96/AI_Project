"""
What an agent sees and what it produces.

    AgentContext     built from the Blackboard (or from a past point of it, for reflection)
    AgentOutput      one parsed provider answer: tag, prediction, explanation, judgment
    Candidate        one alternative message proposed during counterfactual reflection
    Reflection       all candidates for one past message, plus the lesson learned
    Draft            the result of one turn: a message to commit, and the attempts
                     the grammar rejected on the way
"""

from dataclasses import dataclass, field
from typing import Any

from ai_project.benchmarks.base import Evidence, Task
from ai_project.blackboard.models import MessageRecord
from ai_project.protocol.grammar import Position
from ai_project.protocol.pxp import Judgment, PXPMessage, PXPTag

ACT = "act"
REFLECT = "reflect"


@dataclass(frozen=True)
class AgentContext:
    """
    Attributes:
        agent_id, role: Who is deciding
        task: The task (its ``reference`` is never rendered)
        evidence: This agent's private evidence
        j: Number the next message will get
        peer: Latest message from another agent at that point
        own: The agent's previous position at that point
        messages: Messages committed before that point
        lessons: Lessons the agent learned from earlier interventions (its prompt delta)
        weight: The agent's current voting weight
        reject_after: k in Algorithm 1
        mode: ACT or REFLECT
        reflect_on: (REFLECT) the agent's own past message being reconsidered
        hindsight: (REFLECT) every message of the run, including those after ``reflect_on``
        feedback: Grammar or parse errors from the previous attempt in this turn
        tool_results: Tool calls made earlier in this turn and their results
    """

    agent_id: str
    role: str
    task: Task
    evidence: Evidence
    j: int
    peer: MessageRecord | None
    own: Position | None
    messages: tuple[MessageRecord, ...]
    lessons: tuple[str, ...] = ()
    weight: float = 1.0
    reject_after: int = 3
    mode: str = ACT
    reflect_on: MessageRecord | None = None
    hindsight: tuple[MessageRecord, ...] = ()
    feedback: tuple[str, ...] = ()
    tool_results: tuple[dict[str, Any], ...] = ()

    @property
    def options(self) -> tuple[str, ...]:
        return self.task.options

    @property
    def is_first_message(self) -> bool:
        return self.j == 1


@dataclass(frozen=True)
class AgentOutput:
    tag: PXPTag
    prediction: str
    explanation: str
    confidence: float | None = None
    judgment: Judgment | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_message(self, agent_id: str) -> PXPMessage:
        return PXPMessage(
            agent_id=agent_id,
            tag=self.tag,
            prediction=self.prediction,
            explanation=self.explanation,
            confidence=self.confidence,
            judgment=self.judgment,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag.value,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "judgment": self.judgment.to_dict() if self.judgment else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Candidate:
    output: AgentOutput
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**self.output.to_dict(), "rationale": self.rationale}


@dataclass(frozen=True)
class Reflection:
    target: MessageRecord
    candidates: tuple[Candidate, ...]
    lesson: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "lesson": self.lesson,
        }


@dataclass
class Draft:
    """
    Attributes:
        message: Grammatical message to commit, or None if every attempt failed
        rejected: Failed attempts: {"attempt", "output", "errors"}
        error: Why the turn produced no message
        tool_calls: Tool calls made during the turn: {"tool", "arguments", "result"}
    """

    message: PXPMessage | None
    rejected: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
