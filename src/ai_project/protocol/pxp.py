"""
PXP messages (Baskar et al., arXiv 2301.01819; Mestha et al., arXiv 2410.20600).

Every message carries the sender's own prediction and explanation, plus the
tag that says how the sender relates to the message it is answering. The tag
is not free: it follows from three judgments (Algorithm 1, "The AGENT
Procedure", in 2410.20600):

    peer  (y', e')   the latest message on the board from another agent
    own   (y'', e'') the sender's previous position (its last message, or a
                     context revision recorded after a counterfactual
                     intervention); on its first reply, its current output
    new   (y, e)     the sender's current output

    prediction_matches  = MATCH(y', y'')
    explanation_agrees  = AGREE(e', e'')
    changed             = not MATCH(y, y'') or not AGREE(e, e'')

    message 1                          -> INIT
    match and agree                    -> RATIFY
    exactly one of match / agree       -> REVISE if changed else REFUTE
    neither, message number j > k      -> REJECT
    neither, j <= k                    -> REVISE if changed else REFUTE

k (``reject_after``) is the message number after which REJECT may be sent.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_timestamp() -> str:
    """Current UTC time as an ISO-8601 string with a trailing 'Z'."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class PXPTag(Enum):
    INIT = "INIT"
    RATIFY = "RATIFY"
    REVISE = "REVISE"
    REFUTE = "REFUTE"
    REJECT = "REJECT"

    @classmethod
    def from_string(cls, value: str) -> "PXPTag":
        try:
            return cls[str(value).strip().upper()]
        except KeyError:
            raise ValueError(
                f"Invalid PXP tag: {value!r}. Valid tags: {[t.value for t in cls]}"
            ) from None

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Judgment:
    """The sender's three judgments behind a reply (see module docstring)."""

    prediction_matches: bool
    explanation_agrees: bool
    changed: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "prediction_matches": self.prediction_matches,
            "explanation_agrees": self.explanation_agrees,
            "changed": self.changed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Judgment":
        return cls(
            prediction_matches=bool(data["prediction_matches"]),
            explanation_agrees=bool(data["explanation_agrees"]),
            changed=bool(data["changed"]),
        )


def expected_tag(j: int, judgment: Judgment | None, reject_after: int) -> PXPTag:
    """The tag Algorithm 1 assigns to message number ``j`` (1-based)."""
    if j == 1:
        return PXPTag.INIT
    if judgment is None:
        raise ValueError("A reply (message number > 1) needs a judgment")
    match, agree, changed = (
        judgment.prediction_matches,
        judgment.explanation_agrees,
        judgment.changed,
    )
    if match and agree:
        return PXPTag.RATIFY
    if match or agree:
        return PXPTag.REVISE if changed else PXPTag.REFUTE
    if j > reject_after:
        return PXPTag.REJECT
    return PXPTag.REVISE if changed else PXPTag.REFUTE


@dataclass
class PXPMessage:
    """
    A message an agent asks the Blackboard to commit.

    ``iteration`` is assigned by the Blackboard on commit (the message number j);
    ``in_reply_to`` is set by the Blackboard to the id of the peer message.
    """

    agent_id: str
    tag: PXPTag
    prediction: str
    explanation: str
    confidence: float | None = None
    judgment: Judgment | None = None
    message_id: str = ""
    iteration: int = 0
    in_reply_to: str | None = None
    timestamp: str = field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.tag, str):
            self.tag = PXPTag.from_string(self.tag)
        if isinstance(self.judgment, dict):
            self.judgment = Judgment.from_dict(self.judgment)
        if self.confidence is not None:
            self.confidence = float(self.confidence)
        if not self.message_id:
            self.message_id = f"msg_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "agent_id": self.agent_id,
            "tag": self.tag.value,
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "judgment": self.judgment.to_dict() if self.judgment else None,
            "iteration": self.iteration,
            "in_reply_to": self.in_reply_to,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PXPMessage":
        judgment = data.get("judgment")
        return cls(
            agent_id=data["agent_id"],
            tag=PXPTag.from_string(data["tag"]),
            prediction=data["prediction"],
            explanation=data["explanation"],
            confidence=data.get("confidence"),
            judgment=Judgment.from_dict(judgment) if judgment else None,
            message_id=data.get("message_id", ""),
            iteration=data.get("iteration", 0),
            in_reply_to=data.get("in_reply_to"),
            timestamp=data.get("timestamp") or utc_timestamp(),
            metadata=dict(data.get("metadata") or {}),
        )
