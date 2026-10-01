"""
Execution trace records.

Every Scheduler (and counterfactual branch setup) appends ``TraceEntry``
objects. They deliberately contain no wall-clock timestamps, so the same
deterministic run always produces an identical trace.
"""

from dataclasses import dataclass, field
from typing import Any

# Entry kinds
KIND_ACTION = "agent_action"  # an agent was selected, acted and its message was published
KIND_CONSENSUS = "consensus"  # consensus detected, board status set to CONSENSUS
KIND_DEADLOCK = "deadlock"  # deadlock detected, board status set to DEADLOCK
KIND_MAX_STEPS = "max_steps"  # run() hit its step budget; board left RUNNING
KIND_ERROR = "error"  # agent or publish failure, board status set to FAILED
KIND_INHERITED = "inherited"  # counterfactual branch: event copied from the original run
KIND_INTERVENTION = "intervention"  # counterfactual branch: the altered event


@dataclass(frozen=True)
class TraceEntry:
    """
    One step of execution.

    Attributes:
        step: Board iteration this entry refers to (the iteration produced by an
            action, or the iteration at which a status was detected)
        kind: One of the KIND_* constants
        event: PXP tag for messages; CONSENSUS / DEADLOCK / MAX_STEPS / ERROR otherwise
        agent: Acting agent id (None for status entries)
        prediction: Message prediction, or the prediction a status refers to
        explanation: Message explanation (None for status entries)
        confidence: Message confidence
        message_id: Published message id
        reason: Why the agent was selected, or why the status was set
        policy: Scheduling policy that made the selection
        status: Board status after this entry
        changes: State fields changed by this entry, as {field: {"before", "after"}}
        details: Extra structured data (e.g. consensus/deadlock report)
    """

    step: int
    kind: str
    event: str
    agent: str | None = None
    prediction: str | None = None
    explanation: str | None = None
    confidence: float | None = None
    message_id: str | None = None
    reason: str = ""
    policy: str | None = None
    status: str = ""
    changes: dict[str, dict[str, Any]] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "step": self.step,
            "kind": self.kind,
            "event": self.event,
            "agent": self.agent,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "message_id": self.message_id,
            "reason": self.reason,
            "policy": self.policy,
            "status": self.status,
            "changes": {k: dict(v) for k, v in self.changes.items()},
            "details": dict(self.details),
        }


def diff_fields(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return {field: {"before", "after"}} for every field whose value changed."""
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in after
        if before.get(key) != after.get(key)
    }
