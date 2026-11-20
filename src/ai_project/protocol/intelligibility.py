"""
Session intelligibility (Mestha et al., arXiv 2410.20600, Definitions 1 and 2).

For agent m, let T_m be the tags m sent in the session, INIT excluded (the
paper counts <INIT_m, RATIFY_h, RATIFY_m> as Strong for m, so INIT does not
enter the "every element" test).

    One-Way      T_m has at least one RATIFY or REVISE, and no REJECT
    Strong       every element of T_m is RATIFY or REVISE (T_m non-empty)
    Ultra-Strong Strong, and at least one element of T_m is REVISE

The paper defines these per agent for a two-agent session; two-way
intelligibility requires one-way intelligibility for both agents. With more
than two agents we take the same route: the session level is the weakest
level over the agents that sent at least one non-INIT message.

The experiments also apply ``classify`` to the messages after the last
counterfactual intervention. That segment measure is our addition and is
reported separately from the paper's whole-session measure.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import IntEnum

from ai_project.protocol.pxp import PXPTag


class Level(IntEnum):
    NONE = 0
    ONE_WAY = 1
    STRONG = 2
    ULTRA_STRONG = 3

    @property
    def label(self) -> str:
        return {
            Level.NONE: "None",
            Level.ONE_WAY: "One-Way",
            Level.STRONG: "Strong",
            Level.ULTRA_STRONG: "Ultra-Strong",
        }[self]


def agent_level(tags: Iterable[str | PXPTag]) -> Level:
    """Level for one agent from the tags it sent (INIT is ignored)."""
    seq = [t.value if isinstance(t, PXPTag) else str(t) for t in tags]
    seq = [t for t in seq if t != PXPTag.INIT.value]
    if not seq:
        return Level.NONE
    positive = {PXPTag.RATIFY.value, PXPTag.REVISE.value}
    if all(t in positive for t in seq):
        return Level.ULTRA_STRONG if PXPTag.REVISE.value in seq else Level.STRONG
    if any(t in positive for t in seq) and PXPTag.REJECT.value not in seq:
        return Level.ONE_WAY
    return Level.NONE


@dataclass(frozen=True)
class IntelligibilityReport:
    session: Level
    per_agent: dict[str, Level]

    def to_dict(self) -> dict[str, object]:
        return {
            "session": self.session.label,
            "per_agent": {a: lvl.label for a, lvl in self.per_agent.items()},
        }


def classify(messages: Sequence[tuple[str, str]]) -> IntelligibilityReport:
    """
    Classify a session.

    Args:
        messages: (agent_id, tag) pairs in commit order
    """
    tags: dict[str, list[str]] = {}
    for agent_id, tag in messages:
        tags.setdefault(agent_id, []).append(tag)
    per_agent = {a: agent_level(t) for a, t in tags.items()}
    speaking = [lvl for a, lvl in per_agent.items()
                if any(t != PXPTag.INIT.value for t in tags[a])]
    session = min(speaking) if speaking else Level.NONE
    return IntelligibilityReport(session=session, per_agent=per_agent)
