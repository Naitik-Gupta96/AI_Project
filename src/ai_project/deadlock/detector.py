"""
Deadlock detection from Blackboard history.

Two explicit, configurable rules (checked in this order):

1. ``repeated_disagreement``: the standing proposal has been objected to
   (REFUTE of it, or REJECT) at least ``max_disagreement_cycles`` times since
   it was introduced, and at least one agent's latest stance still objects to
   it. Each such objection is one *disagreement cycle*: the proposal was on
   the table and was challenged without being changed.

2. ``stagnation``: no *novel* proposal (a prediction never proposed before)
   has appeared for ``max_stagnant_steps`` messages while some agent still
   does not support the standing proposal. Re-proposing an earlier prediction
   is not progress, so proposals oscillating A -> B -> A are caught here.
   Set ``max_stagnant_steps=None`` to disable this rule.

A new proposal (RATIFY/REVISE with a different prediction) starts a new epoch
and resets the disagreement-cycle count; only a novel one resets stagnation.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ai_project.blackboard.models import HistoryEvent
from ai_project.deadlock.stances import (
    last_novel_proposal_index,
    latest_stances,
    objections_in_epoch,
    objects_to,
    proposal_epoch,
    supports,
)

RULE_REPEATED_DISAGREEMENT = "repeated_disagreement"
RULE_STAGNATION = "stagnation"


@dataclass(frozen=True)
class DeadlockConfig:
    """
    Thresholds for deadlock detection.

    Attributes:
        max_disagreement_cycles: Objections against one standing proposal that
            trigger ``repeated_disagreement``
        max_stagnant_steps: Messages without a novel proposal (while dissent
            remains) that trigger ``stagnation``; None disables the rule
    """

    max_disagreement_cycles: int = 2
    max_stagnant_steps: int | None = 6

    def __post_init__(self) -> None:
        if self.max_disagreement_cycles < 1:
            raise ValueError("max_disagreement_cycles must be >= 1")
        if self.max_stagnant_steps is not None and self.max_stagnant_steps < 1:
            raise ValueError("max_stagnant_steps must be >= 1 or None")

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "max_disagreement_cycles": self.max_disagreement_cycles,
            "max_stagnant_steps": self.max_stagnant_steps,
        }


@dataclass(frozen=True)
class DeadlockReport:
    """
    Result of a deadlock check, including the measurements behind it.

    Attributes:
        deadlocked: Whether a deadlock rule fired
        rule: Name of the rule that fired, or None
        reason: Human-readable explanation
        contested_prediction: The standing proposal (None if none yet)
        disagreement_cycles: Objections against the standing proposal in its epoch
        stagnant_steps: Messages since the last novel proposal
        objecting_agents: Agents whose latest stance objects to the proposal
        dissenting_agents: Agents whose latest stance does not support the proposal
    """

    deadlocked: bool
    rule: str | None
    reason: str
    contested_prediction: str | None
    disagreement_cycles: int
    stagnant_steps: int
    objecting_agents: tuple[str, ...]
    dissenting_agents: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "deadlocked": self.deadlocked,
            "rule": self.rule,
            "reason": self.reason,
            "contested_prediction": self.contested_prediction,
            "disagreement_cycles": self.disagreement_cycles,
            "stagnant_steps": self.stagnant_steps,
            "objecting_agents": list(self.objecting_agents),
            "dissenting_agents": list(self.dissenting_agents),
        }


def detect_deadlock(
    history: Sequence[HistoryEvent],
    config: DeadlockConfig | None = None,
) -> DeadlockReport:
    """
    Check Blackboard history for a deadlock.

    Args:
        history: Chronological history, e.g. ``board.get_history()``
        config: Thresholds (defaults to ``DeadlockConfig()``)

    Returns:
        DeadlockReport describing whether and why the history is deadlocked
    """
    config = config or DeadlockConfig()
    epoch = proposal_epoch(history)
    proposal = epoch.proposal
    stances = latest_stances(history)

    if proposal is None or epoch.start_index is None:
        cycles = 0
        stagnant_steps = len(history)
        objecting: tuple[str, ...] = ()
        dissenting: tuple[str, ...] = tuple(stances)
    else:
        cycles = len(objections_in_epoch(history))
        novel_index = last_novel_proposal_index(history)
        stagnant_steps = len(history) - 1 - (novel_index if novel_index is not None else -1)
        objecting = tuple(a for a, e in stances.items() if objects_to(e, proposal))
        dissenting = tuple(a for a, e in stances.items() if not supports(e, proposal))

    def report(deadlocked: bool, rule: str | None, reason: str) -> DeadlockReport:
        return DeadlockReport(
            deadlocked=deadlocked,
            rule=rule,
            reason=reason,
            contested_prediction=proposal,
            disagreement_cycles=cycles,
            stagnant_steps=stagnant_steps,
            objecting_agents=objecting,
            dissenting_agents=dissenting,
        )

    if cycles >= config.max_disagreement_cycles and objecting:
        return report(
            True,
            RULE_REPEATED_DISAGREEMENT,
            f"'{proposal}' was objected to {cycles} time(s) without being revised "
            f"(threshold {config.max_disagreement_cycles}); still objecting: "
            f"{', '.join(objecting)}",
        )

    if (
        config.max_stagnant_steps is not None
        and stagnant_steps >= config.max_stagnant_steps
        and dissenting
    ):
        subject = f"'{proposal}'" if proposal is not None else "any proposal"
        return report(
            True,
            RULE_STAGNATION,
            f"No novel proposal for {stagnant_steps} step(s) "
            f"(threshold {config.max_stagnant_steps}) and no agreement on {subject}; "
            f"dissenting: {', '.join(dissenting)}",
        )

    return report(
        False,
        None,
        f"{cycles}/{config.max_disagreement_cycles} disagreement cycle(s) on "
        f"{repr(proposal) if proposal is not None else 'no proposal'}",
    )


class DeadlockDetector:
    """Configured wrapper around ``detect_deadlock`` for injection into the Scheduler."""

    def __init__(self, config: DeadlockConfig | None = None) -> None:
        self.config = config or DeadlockConfig()

    def detect(self, history: Sequence[HistoryEvent]) -> DeadlockReport:
        """Check history using this detector's configuration."""
        return detect_deadlock(history, self.config)
