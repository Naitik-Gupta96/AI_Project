"""
Consensus detection.

Criterion (``detect_consensus``):

    Let X = the Blackboard's current prediction.
    Consensus on X holds iff
      1. X is non-empty,
      2. every participant's latest message supports X (RATIFY X or REVISE X),
         so no participant has an unresolved REFUTE/REJECT or backs a
         different prediction, and
      3. at least ``min_supporters`` distinct agents support X.

    Participants are the registered agents when ``agent_ids`` is given (the
    Scheduler always passes its registry, so every registered agent must
    agree), otherwise every agent that appears in history.

Because the Blackboard sets its current prediction to the prediction of the
latest message, an objection as the latest message (REFUTE X sets the
prediction to X but the objector does not support X) can never be consensus.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ai_project.blackboard.models import BlackboardState, HistoryEvent
from ai_project.deadlock.stances import latest_stances, supports


@dataclass(frozen=True)
class ConsensusConfig:
    """
    Consensus thresholds.

    Attributes:
        min_supporters: Minimum number of distinct agents that must support
            the prediction
    """

    min_supporters: int = 2

    def __post_init__(self) -> None:
        if self.min_supporters < 1:
            raise ValueError("min_supporters must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {"min_supporters": self.min_supporters}


@dataclass(frozen=True)
class ConsensusResult:
    """
    Result of a consensus check.

    Attributes:
        reached: Whether consensus holds
        prediction: The candidate prediction that was checked
        supporters: Participants whose latest stance supports the candidate
        blockers: Participants that do not (silent agents included)
        reason: Human-readable explanation
    """

    reached: bool
    prediction: str | None
    supporters: tuple[str, ...]
    blockers: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "reached": self.reached,
            "prediction": self.prediction,
            "supporters": list(self.supporters),
            "blockers": list(self.blockers),
            "reason": self.reason,
        }


def detect_consensus(
    state: BlackboardState,
    history: Sequence[HistoryEvent],
    config: ConsensusConfig | None = None,
    agent_ids: Sequence[str] | None = None,
) -> ConsensusResult:
    """
    Check whether the Blackboard has reached consensus.

    Args:
        state: Current state, e.g. ``board.get_state()``
        history: Chronological history, e.g. ``board.get_history()``
        config: Thresholds (defaults to ``ConsensusConfig()``)
        agent_ids: Participants that must all agree; defaults to agents in history

    Returns:
        ConsensusResult (see module docstring for the exact criterion)
    """
    config = config or ConsensusConfig()
    candidate = state.current_prediction or None
    stances = latest_stances(history)
    participants = tuple(agent_ids) if agent_ids is not None else tuple(stances)

    if candidate is None:
        return ConsensusResult(False, None, (), participants, "No prediction on the board yet")

    supporters = tuple(a for a in participants if a in stances and supports(stances[a], candidate))
    blockers = tuple(a for a in participants if a not in supporters)

    if blockers:
        details = ", ".join(
            f"{a} ({stances[a].tag} {stances[a].prediction})" if a in stances else f"{a} (silent)"
            for a in blockers
        )
        return ConsensusResult(
            False,
            candidate,
            supporters,
            blockers,
            f"Not all agents support '{candidate}': {details}",
        )

    if len(supporters) < config.min_supporters:
        return ConsensusResult(
            False,
            candidate,
            supporters,
            blockers,
            f"Only {len(supporters)} supporter(s) for '{candidate}' "
            f"(need {config.min_supporters})",
        )

    return ConsensusResult(
        True,
        candidate,
        supporters,
        blockers,
        f"All {len(supporters)} agents support '{candidate}': {', '.join(supporters)}",
    )
