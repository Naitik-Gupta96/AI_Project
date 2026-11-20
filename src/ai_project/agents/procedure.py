"""
The AGENT procedure (Algorithm 1 of arXiv 2410.20600) on the agent side.

The provider (a model, or the mock) supplies what needs understanding: the
agent's current answer and explanation, whether it agrees with the peer's
explanation, and whether its own reasoning has changed. MATCH on listed
options is string equality, so the procedure computes it. The procedure then
assigns the tag exactly as Algorithm 1 does:

    prediction_matches = MATCH(peer prediction, previous prediction)
                         (string equality with listed options; the model's
                         judgment for free-form answers)
    explanation_agrees = AGREE(peer explanation, previous explanation)   (model)
    changed            = the prediction moved from the previous position, or
                         the model says its reasoning changed; always false on
                         the agent's first reply (the paper sets the previous
                         position to the current output there)
    tag                = expected_tag(j, judgment, k)

A RATIFY aligns with the board: with listed options, it carries the peer's
prediction. If the model's own answer differed, it is kept in
``metadata["unsent_prediction"]``.

The Blackboard's grammar checks the assembled message again on commit.
"""

from dataclasses import dataclass, field
from typing import Any

from ai_project.protocol.grammar import GrammarContext
from ai_project.protocol.pxp import Judgment, PXPMessage, PXPTag, expected_tag


class TurnError(ValueError):
    """The provider's turn lacks a judgment the procedure needs."""


@dataclass(frozen=True)
class Turn:
    """What the provider returns for one turn (see ``prompts/schemas``)."""

    prediction: str
    explanation: str
    confidence: float | None = None
    explanation_agrees: bool | None = None
    prediction_matches: bool | None = None
    changed: bool | None = None
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "prediction": self.prediction,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "explanation_agrees": self.explanation_agrees,
            "prediction_matches": self.prediction_matches,
            "changed": self.changed,
            "metadata": dict(self.metadata),
        }
        if self.rationale:
            data["rationale"] = self.rationale
        return data


def assemble(agent_id: str, turn: Turn, ctx: GrammarContext, reject_after: int) -> PXPMessage:
    """Turn + board context -> PXP message with judgment and tag."""
    metadata = dict(turn.metadata)
    if ctx.j == 1:
        return PXPMessage(agent_id=agent_id, tag=PXPTag.INIT, prediction=turn.prediction,
                          explanation=turn.explanation, confidence=turn.confidence,
                          metadata=metadata)
    if ctx.peer is None:
        raise TurnError("there is no message from another agent to answer")
    if turn.explanation_agrees is None:
        raise TurnError("explanation_agrees is required when answering a peer message")

    previous_prediction = ctx.own.prediction if ctx.own else turn.prediction
    if ctx.options:
        matches = ctx.peer.prediction == previous_prediction
    elif turn.prediction_matches is None:
        raise TurnError("prediction_matches is required for free-form answers")
    else:
        matches = turn.prediction_matches

    if ctx.own is None:
        changed = False
    else:
        moved = bool(ctx.options) and turn.prediction != ctx.own.prediction
        changed = moved or bool(turn.changed)

    judgment = Judgment(matches, turn.explanation_agrees, changed)
    tag = expected_tag(ctx.j, judgment, reject_after)
    prediction = turn.prediction
    if tag == PXPTag.RATIFY and ctx.options and prediction != ctx.peer.prediction:
        metadata["unsent_prediction"] = prediction
        prediction = ctx.peer.prediction
    return PXPMessage(agent_id=agent_id, tag=tag, prediction=prediction,
                      explanation=turn.explanation, confidence=turn.confidence,
                      judgment=judgment, metadata=metadata)
