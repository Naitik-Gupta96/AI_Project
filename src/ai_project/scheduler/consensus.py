"""
Weighted consensus.

A RATIFY agrees with the peer message it answered (``in_reply_to``). If that
message is itself a RATIFY, the agreement carries on to what it answered, and
so on, until a non-RATIFY message: the *anchor*, whose prediction is what the
chain agrees on. In the paper's two-agent protocol a session stops when both
agents' latest tags are RATIFY; with n agents and voting weights:

    supporters(a) = agents whose latest message is a RATIFY with anchor a
    share(a)      = sum of supporters' weights / sum of all agents' weights

Consensus holds for the anchor with the largest share when that share is at
least ``tau`` and at least ``min_supporters`` agents support it. The largest
share is also reported as ``proximity`` (1.0 at consensus), which the
counterfactual layer uses as its measure of how close a board is to agreement.

With equal weights and tau = 0.75, three agents must all agree. If a
counterfactual intervention lowers one agent's weight to w, the other two
carry the decision once 2 / (2 + w) >= tau.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ai_project.blackboard.models import MessageRecord
from ai_project.protocol.pxp import PXPTag

RATIFY = PXPTag.RATIFY.value


@dataclass(frozen=True)
class ConsensusConfig:
    tau: float = 0.75
    min_supporters: int = 2

    def __post_init__(self) -> None:
        if not 0.0 < self.tau <= 1.0:
            raise ValueError("tau must be in (0, 1]")
        if self.min_supporters < 1:
            raise ValueError("min_supporters must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {"tau": self.tau, "min_supporters": self.min_supporters}


@dataclass(frozen=True)
class ConsensusResult:
    reached: bool
    prediction: str | None
    anchor_id: str | None
    supporters: tuple[str, ...]
    share: float
    reason: str

    @property
    def proximity(self) -> float:
        return 1.0 if self.reached else self.share

    def to_dict(self) -> dict[str, Any]:
        return {
            "reached": self.reached,
            "prediction": self.prediction,
            "anchor_id": self.anchor_id,
            "supporters": list(self.supporters),
            "share": round(self.share, 4),
            "proximity": round(self.proximity, 4),
            "reason": self.reason,
        }


def anchor_of(record: MessageRecord, by_id: Mapping[str, MessageRecord]) -> MessageRecord:
    """Follow ``in_reply_to`` through RATIFY messages to the message they agree with."""
    current = record
    while current.tag == RATIFY and current.in_reply_to in by_id:
        current = by_id[current.in_reply_to]
    return current


def evaluate_consensus(
    messages: Sequence[MessageRecord],
    agents: Sequence[str],
    weights: Mapping[str, float],
    config: ConsensusConfig | None = None,
) -> ConsensusResult:
    config = config or ConsensusConfig()
    agent_ids = list(agents) or list(dict.fromkeys(m.agent_id for m in messages))
    total = sum(weights.get(a, 1.0) for a in agent_ids)
    if not messages or total <= 0:
        return ConsensusResult(False, None, None, (), 0.0, "No messages yet")

    by_id = {m.message_id: m for m in messages}
    latest: dict[str, MessageRecord] = {}
    for m in messages:
        latest[m.agent_id] = m

    groups: dict[str, list[str]] = {}
    for agent in agent_ids:
        m = latest.get(agent)
        if m is not None and m.tag == RATIFY:
            groups.setdefault(anchor_of(m, by_id).message_id, []).append(agent)
    if not groups:
        return ConsensusResult(False, None, None, (), 0.0, "No agent's latest message is RATIFY")

    def group_key(item: tuple[str, list[str]]) -> tuple[float, int]:
        anchor_id, members = item
        return (sum(weights.get(a, 1.0) for a in members), by_id[anchor_id].iteration)

    anchor_id, members = max(groups.items(), key=group_key)
    anchor = by_id[anchor_id]
    share = sum(weights.get(a, 1.0) for a in members) / total
    supporters = tuple(members)
    reached = share >= config.tau - 1e-9 and len(supporters) >= config.min_supporters
    if reached:
        reason = (f"{', '.join(supporters)} ratify '{anchor.prediction}' "
                  f"(weighted share {share:.2f} >= {config.tau:.2f})")
    else:
        reason = (f"Largest agreeing group {', '.join(supporters)} on '{anchor.prediction}' has "
                  f"weighted share {share:.2f} < {config.tau:.2f}"
                  if share < config.tau - 1e-9 else
                  f"Only {len(supporters)} supporter(s); {config.min_supporters} required")
    return ConsensusResult(reached, anchor.prediction, anchor_id, supporters, share, reason)
