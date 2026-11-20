"""
PXP grammar: decides whether a message may be committed to the Blackboard.

The Blackboard builds a ``GrammarContext`` (message number, peer message, the
sender's previous position, the task's options) and calls ``PXPGrammar.check``
before any state changes. Messages are rejected, never repaired.

Checks, in order:

1. Structure: non-empty agent id, prediction and explanation; confidence in
   [0, 1]; a known tag.
2. Position in the session: INIT exactly for message 1; a reply needs a peer
   message (from another agent) and a judgment.
3. Options: if the task lists options, the prediction must be one of them.
4. Verifiable judgments: with listed options, prediction matching is string
   equality, so ``prediction_matches`` and the prediction part of ``changed``
   are recomputed and must agree with what the agent reported. On an agent's
   first reply its previous position is its current output, so ``changed``
   must be false. Explanation agreement is the agent's own judgment and is
   not second-guessed.
5. Tag: must equal ``expected_tag(j, judgment, reject_after)``.
6. RATIFY content: the spec defines RATIFY as aligning with the board's
   prediction and explanation, so with listed options a RATIFY must carry the
   peer's prediction. (Algorithm 1 alone would allow "RATIFY A" in reply to B
   when the sender's previous position matched B but its new output is A.)
"""

from dataclasses import dataclass

from ai_project.protocol.pxp import PXPMessage, PXPTag, expected_tag


@dataclass(frozen=True)
class Position:
    """An agent's prediction and explanation at some point in the session."""

    agent_id: str
    prediction: str
    explanation: str
    source: str = ""  # message id or context-revision id


@dataclass(frozen=True)
class GrammarContext:
    """
    What the grammar needs to know about the board for one message.

    Attributes:
        j: The number the message will get if committed (1-based)
        peer: Latest message from another agent, as a position
        own: The sender's previous position (None before its first message)
        options: Allowed predictions; empty for free-form answers
    """

    j: int
    peer: Position | None
    own: Position | None
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Violation:
    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


class PXPGrammar:
    """
    Args:
        reject_after: k in Algorithm 1; REJECT is allowed only for message j > k
    """

    def __init__(self, reject_after: int = 3) -> None:
        if reject_after < 1:
            raise ValueError("reject_after must be >= 1")
        self.reject_after = reject_after

    def check(self, message: PXPMessage, ctx: GrammarContext) -> list[Violation]:
        """Return every violation (empty list if the message is grammatical)."""
        errors = self._structure(message)
        if errors:
            return errors

        if ctx.options and message.prediction not in ctx.options:
            errors.append(
                Violation("prediction", f"{message.prediction!r} is not one of {list(ctx.options)}")
            )

        if ctx.j == 1:
            if message.tag != PXPTag.INIT:
                errors.append(Violation("tag", "the first message of a session must be INIT"))
            return errors

        if message.tag == PXPTag.INIT:
            errors.append(Violation("tag", "INIT is only valid as the first message"))
            return errors
        if ctx.peer is None:
            errors.append(Violation("tag", "a reply needs a message from another agent"))
            return errors
        if message.judgment is None:
            errors.append(Violation("judgment", "a reply must carry a judgment"))
            return errors

        judgment = message.judgment
        reference = ctx.own or Position(message.agent_id, message.prediction, message.explanation)
        if ctx.own is None and judgment.changed:
            errors.append(
                Violation("judgment.changed", "must be false on an agent's first reply")
            )
        if ctx.options:
            matches = ctx.peer.prediction == reference.prediction
            if judgment.prediction_matches != matches:
                errors.append(
                    Violation(
                        "judgment.prediction_matches",
                        f"peer predicts {ctx.peer.prediction!r}, previous position is "
                        f"{reference.prediction!r}, so this must be {matches}",
                    )
                )
            if message.prediction != reference.prediction and not judgment.changed:
                errors.append(
                    Violation(
                        "judgment.changed",
                        f"prediction moved from {reference.prediction!r} to "
                        f"{message.prediction!r}, so this must be true",
                    )
                )

        expected = expected_tag(ctx.j, judgment, self.reject_after)
        if message.tag != expected:
            errors.append(
                Violation(
                    "tag",
                    f"judgment {judgment.to_dict()} at message {ctx.j} requires "
                    f"{expected.value}, not {message.tag.value}",
                )
            )
        if (message.tag == PXPTag.RATIFY and ctx.options
                and message.prediction != ctx.peer.prediction):
            errors.append(
                Violation(
                    "prediction",
                    f"a RATIFY aligns with the peer's prediction {ctx.peer.prediction!r}",
                )
            )
        return errors

    def expected(self, ctx: GrammarContext, message: PXPMessage) -> PXPTag:
        """Tag the grammar would require for ``message`` in ``ctx``."""
        return expected_tag(ctx.j, message.judgment, self.reject_after)

    @staticmethod
    def _structure(message: PXPMessage) -> list[Violation]:
        errors = []
        if not isinstance(message.tag, PXPTag):
            errors.append(Violation("tag", f"unknown tag {message.tag!r}"))
        if not str(message.agent_id or "").strip():
            errors.append(Violation("agent_id", "must be non-empty"))
        if not str(message.prediction or "").strip():
            errors.append(Violation("prediction", "must be non-empty"))
        if not str(message.explanation or "").strip():
            errors.append(Violation("explanation", "must be non-empty"))
        if message.confidence is not None and not 0.0 <= message.confidence <= 1.0:
            errors.append(Violation("confidence", f"{message.confidence} is outside [0, 1]"))
        return errors
