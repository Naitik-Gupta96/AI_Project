"""
Benchmark-independent task model.

Every benchmark loader turns its records into ``Task`` objects. What the
agents see is the question, the options (if the answer is a choice), the
public context and their own role's private evidence. ``reference`` is the
ground truth used for scoring and is never shown to agents.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Evidence:
    """
    One role's private knowledge about a task's options.

    Attributes:
        scores: Preference score per option (higher is better)
        objections: {option: reason} for options this role rules out
    """

    scores: Mapping[str, float] = field(default_factory=dict)
    objections: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"scores": dict(self.scores), "objections": dict(self.objections)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Evidence":
        return cls(scores=dict(data.get("scores", {})), objections=dict(data.get("objections", {})))

    @property
    def empty(self) -> bool:
        return not self.scores and not self.objections


@dataclass(frozen=True)
class Task:
    """
    Attributes:
        task_id: Unique id within its benchmark
        benchmark: "synthetic", "mscore", "kramabench" or "medagentbench"
        question: What the team must answer
        options: Allowed answers; empty for free-form answers
        domain: Selects the personas in the prompt matrix
        reference: Ground truth (scoring only)
        evidence: Private evidence per role
        context: Public material shown to every agent (e.g. a patient id, file list)
        metadata: Anything else the loader wants to keep (difficulty, task type, ...)
        answer_format: How a free-form answer must be written (shown to agents)
    """

    task_id: str
    benchmark: str
    question: str
    options: tuple[str, ...] = ()
    domain: str = "general"
    reference: Any = None
    evidence: Mapping[str, Evidence] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    answer_format: str = ""

    def evidence_for(self, role: str) -> Evidence:
        return self.evidence.get(role, Evidence())

    def board_metadata(self) -> dict[str, Any]:
        """Public task information published on the Blackboard."""
        return {
            "task_id": self.task_id,
            "benchmark": self.benchmark,
            "domain": self.domain,
            "options": list(self.options),
            "context": dict(self.context),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "benchmark": self.benchmark,
            "question": self.question,
            "options": list(self.options),
            "domain": self.domain,
            "reference": self.reference,
            "evidence": {r: e.to_dict() for r, e in self.evidence.items()},
            "context": dict(self.context),
            "metadata": dict(self.metadata),
            "answer_format": self.answer_format,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Task":
        return cls(
            task_id=data["task_id"],
            benchmark=data["benchmark"],
            question=data["question"],
            options=tuple(data.get("options") or ()),
            domain=data.get("domain", "general"),
            reference=data.get("reference"),
            evidence={r: Evidence.from_dict(e) for r, e in (data.get("evidence") or {}).items()},
            context=dict(data.get("context") or {}),
            metadata=dict(data.get("metadata") or {}),
            answer_format=data.get("answer_format", ""),
        )


@dataclass(frozen=True)
class Score:
    """
    Attributes:
        correct: Whether the answer counts as accurate
        value: Benchmark metric in [0, 1] (1/0 for exact tasks, ROUGE-L for MSCoRe, ...)
        detail: Scorer-specific information
    """

    correct: bool
    value: float
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"correct": self.correct, "value": round(self.value, 4), "detail": dict(self.detail)}


class Benchmark(Protocol):
    name: str

    def load(self, n: int | None = None, seed: int = 0) -> list[Task]:
        """Up to ``n`` tasks, sampled deterministically from ``seed``."""
        ...

    def score(self, task: Task, prediction: str | None) -> Score:
        """Score the team's final answer (None if the session ended without one)."""
        ...
