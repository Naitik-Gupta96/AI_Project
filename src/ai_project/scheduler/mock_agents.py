"""
Deterministic rule-based mock agents for scheduler demos and tests.

These are test doubles, not reasoning agents: no LLM, no randomness, no hidden
state. Each decision is a pure function of the Blackboard (read through its
public API), so the same board always yields the same message. That is what
makes deadlocks reproducible and counterfactual replays repeatable, while
still letting an agent behave differently when its context differs.
"""

from collections.abc import Mapping
from typing import Any

from ai_project.blackboard import Blackboard
from ai_project.deadlock.stances import OBJECTION_TAGS, current_proposal
from ai_project.protocol.pxp import PXPMessage, PXPTag

ALTERNATIVE_KEY = "alternative"


class RuleBasedMockAgent:
    """
    Mock agent with explicit, ordered decision rules.

    Rules (first match wins):

    1. ``open``: no proposal yet -> RATIFY ``preferred`` (REJECT if it has none)
    2. ``adopt_alternative``: if ``adopts_alternatives`` and the latest message is
       an objection whose metadata names an ``alternative`` this agent does not
       object to -> REVISE to that alternative
    3. ``object``: the standing proposal is in ``objections`` -> REFUTE it
       (offering ``suggests`` as an alternative, if set)
    4. ``endorse``: otherwise -> RATIFY the standing proposal
    """

    def __init__(
        self,
        agent_id: str,
        role: str = "",
        preferred: str | None = None,
        objections: Mapping[str, str] | None = None,
        suggests: str | None = None,
        adopts_alternatives: bool = False,
        confidence: float = 0.8,
    ) -> None:
        """
        Args:
            agent_id: Unique agent id
            role: Human-readable role
            preferred: Prediction to open with when nothing is proposed
            objections: {prediction: reason} this agent refutes
            suggests: Alternative attached to this agent's refutations
            adopts_alternatives: Whether it revises toward alternatives others offer
            confidence: Confidence attached to every message
        """
        self.agent_id = agent_id
        self.role = role or agent_id
        self.preferred = preferred
        self.objections: dict[str, str] = dict(objections or {})
        self.suggests = suggests
        self.adopts_alternatives = adopts_alternatives
        self.confidence = confidence

    def decide(self, board: Blackboard) -> tuple[PXPTag, str, str, dict[str, Any]]:
        """
        Apply the decision rules to the board.

        Returns:
            (tag, prediction, explanation, metadata) - metadata["rule"] names the rule used
        """
        proposal = current_proposal(board.get_history())

        if proposal is None:
            if self.preferred is None:
                return (
                    PXPTag.REJECT,
                    "No proposal",
                    "There is no proposal on the board to evaluate.",
                    {"rule": "open"},
                )
            return (
                PXPTag.RATIFY,
                self.preferred,
                f"Opening proposal: {self.preferred} matches my analysis of the task.",
                {"rule": "open"},
            )

        latest = board.get_latest_message()
        if self.adopts_alternatives and latest and latest["tag"] in OBJECTION_TAGS:
            alternative = (latest.get("metadata") or {}).get(ALTERNATIVE_KEY)
            if alternative and alternative != proposal and alternative not in self.objections:
                return (
                    PXPTag.REVISE,
                    alternative,
                    f"{latest['agent_id']} showed '{proposal}' is flawed and pointed to "
                    f"{alternative}; I revise the proposal to {alternative}.",
                    {"rule": "adopt_alternative", "adopted_from": latest["agent_id"]},
                )

        if proposal in self.objections:
            explanation = f"{proposal} is unacceptable: {self.objections[proposal]}."
            metadata: dict[str, Any] = {"rule": "object"}
            if self.suggests and self.suggests != proposal:
                explanation += f" {self.suggests} avoids this problem."
                metadata[ALTERNATIVE_KEY] = self.suggests
            return PXPTag.REFUTE, proposal, explanation, metadata

        if proposal == self.preferred:
            explanation = f"{proposal} matches my own analysis."
        else:
            explanation = f"I have no objection to {proposal}; it satisfies my constraints."
        return PXPTag.RATIFY, proposal, explanation, {"rule": "endorse"}

    def act(self, board: Blackboard) -> PXPMessage:
        """Decide and return a PXP message (the Scheduler publishes it)."""
        tag, prediction, explanation, metadata = self.decide(board)
        iteration = board.get_iteration() + 1
        return PXPMessage.create(
            agent_id=self.agent_id,
            tag=tag,
            prediction=prediction,
            explanation=explanation,
            confidence=self.confidence,
            iteration=iteration,
            metadata={"mock": True, "role": self.role, **metadata},
            message_id=f"{self.agent_id}-it{iteration:03d}",
        )

    def __repr__(self) -> str:
        return f"RuleBasedMockAgent({self.agent_id!r})"
