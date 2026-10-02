"""
Stance analysis over Blackboard history.

These pure functions turn the append-only PXP history into the facts that
consensus detection, deadlock detection and scheduling policies reason about:

- the *standing proposal* (the prediction currently on the table),
- the *proposal epoch* (the stretch of history since that proposal appeared),
- each agent's *latest stance* (its most recent message).

PXP tag semantics used throughout:

- RATIFY X  -> the agent supports X
- REVISE X  -> the agent proposes (and therefore supports) X
- REFUTE X  -> the agent objects to X
- REJECT    -> the agent rejects the current task/approach, which objects
               to whatever proposal is standing, regardless of its prediction
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ai_project.blackboard.models import HistoryEvent
from ai_project.protocol.pxp import PXPTag

SUPPORT_TAGS = frozenset({PXPTag.RATIFY.value, PXPTag.REVISE.value})
OBJECTION_TAGS = frozenset({PXPTag.REFUTE.value, PXPTag.REJECT.value})


def is_support(event: HistoryEvent) -> bool:
    """True if the event supports its own prediction (RATIFY or REVISE)."""
    return event.tag in SUPPORT_TAGS


def is_objection(event: HistoryEvent) -> bool:
    """True if the event is a REFUTE or REJECT."""
    return event.tag in OBJECTION_TAGS


def supports(event: HistoryEvent, prediction: str) -> bool:
    """True if the event supports exactly this prediction."""
    return is_support(event) and event.prediction == prediction


def objects_to(event: HistoryEvent, prediction: str) -> bool:
    """True if the event objects to this prediction (REFUTE of it, or any REJECT)."""
    if event.tag == PXPTag.REJECT.value:
        return True
    return event.tag == PXPTag.REFUTE.value and event.prediction == prediction


@dataclass(frozen=True)
class ProposalEpoch:
    """
    The standing proposal and where in history it was introduced.

    Attributes:
        proposal: The standing prediction, or None if nothing was proposed yet
        start_index: Index in history of the event that introduced the proposal
            (None if there is no proposal)
    """

    proposal: str | None
    start_index: int | None


def proposal_epoch(history: Sequence[HistoryEvent]) -> ProposalEpoch:
    """
    Find the standing proposal and the history index where it was introduced.

    The proposal changes only when a RATIFY or REVISE carries a prediction
    different from the standing one. Objections never change the proposal.
    """
    proposal: str | None = None
    start_index: int | None = None
    for index, event in enumerate(history):
        if is_support(event) and event.prediction != proposal:
            proposal = event.prediction
            start_index = index
    return ProposalEpoch(proposal=proposal, start_index=start_index)


def current_proposal(history: Sequence[HistoryEvent]) -> str | None:
    """The standing proposal, or None if no agent has proposed anything yet."""
    return proposal_epoch(history).proposal


def last_novel_proposal_index(history: Sequence[HistoryEvent]) -> int | None:
    """
    Index of the last RATIFY/REVISE whose prediction had never been proposed before.

    Re-proposing an earlier prediction (e.g. cycling A -> B -> A) is not novel,
    so oscillating proposals do not count as progress.
    """
    seen: set[str] = set()
    index: int | None = None
    for i, event in enumerate(history):
        if is_support(event) and event.prediction not in seen:
            seen.add(event.prediction)
            index = i
    return index


def latest_stances(history: Sequence[HistoryEvent]) -> dict[str, HistoryEvent]:
    """
    Map each agent to its most recent event.

    Keys are ordered by each agent's first appearance in history, so the
    result is deterministic for a given history.
    """
    stances: dict[str, HistoryEvent] = {}
    for event in history:
        # Re-assigning an existing key keeps its original (first-seen) position
        stances[event.agent_id] = event
    return stances


def objections_in_epoch(history: Sequence[HistoryEvent]) -> list[HistoryEvent]:
    """
    Objections raised against the standing proposal since it was introduced.

    Each entry is one *disagreement cycle*: the proposal was on the table and
    an agent objected to it without the proposal being changed.
    """
    epoch = proposal_epoch(history)
    if epoch.proposal is None or epoch.start_index is None:
        return []
    return [
        event for event in history[epoch.start_index + 1 :] if objects_to(event, epoch.proposal)
    ]
