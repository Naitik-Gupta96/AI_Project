"""
Deadlock detection.

Rules, checked in order over the current *epoch* (the messages committed
since the last counterfactual intervention; the whole session if there was
none):

1. ``reject``: a REJECT was sent. In the PXP interaction procedure
   (2410.20600, Algorithm 3) a REJECT ends the session; here it is a deadlock
   that a counterfactual agent may still resolve.
2. ``refute_loop``: the last ``refute_streak`` messages are all REFUTE: agents
   keep objecting and nobody can revise.
3. ``stagnation``: none of the last ``stagnation`` messages put forward a
   prediction that had not appeared earlier in the session, while there is
   no consensus (the scheduler checks consensus first).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard.models import MessageRecord
from ai_project.protocol.pxp import PXPTag

RULE_REJECT = "reject"
RULE_REFUTE_LOOP = "refute_loop"
RULE_STAGNATION = "stagnation"

REJECT = PXPTag.REJECT.value
REFUTE = PXPTag.REFUTE.value


@dataclass(frozen=True)
class DeadlockConfig:
    refute_streak: int = 3
    stagnation: int | None = 6

    def __post_init__(self) -> None:
        if self.refute_streak < 1:
            raise ValueError("refute_streak must be >= 1")
        if self.stagnation is not None and self.stagnation < 1:
            raise ValueError("stagnation must be >= 1 or None")

    def to_dict(self) -> dict[str, Any]:
        return {"refute_streak": self.refute_streak, "stagnation": self.stagnation}


@dataclass(frozen=True)
class DeadlockReport:
    deadlocked: bool
    rule: str | None = None
    reason: str = ""
    positions: dict[str, str] = field(default_factory=dict)
    objectors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "deadlocked": self.deadlocked,
            "rule": self.rule,
            "reason": self.reason,
            "positions": dict(self.positions),
            "objectors": list(self.objectors),
        }


class DeadlockDetector:
    def __init__(self, config: DeadlockConfig | None = None) -> None:
        self.config = config or DeadlockConfig()

    def detect(
        self, messages: Sequence[MessageRecord], epoch_start: int = 0
    ) -> DeadlockReport:
        """
        Args:
            messages: All messages of the session, in order
            epoch_start: Message number after which the current epoch begins
        """
        epoch = [m for m in messages if m.iteration > epoch_start]
        positions = {m.agent_id: m.prediction for m in messages}
        latest = {m.agent_id: m for m in epoch}
        objectors = tuple(a for a, m in latest.items() if m.tag in (REFUTE, REJECT))

        rejects = [m for m in epoch if m.tag == REJECT]
        if rejects:
            m = rejects[-1]
            return DeadlockReport(
                True, RULE_REJECT,
                f"{m.agent_id} sent REJECT at message {m.iteration}: it disagrees with both the "
                f"prediction and the explanation it answered",
                positions, objectors,
            )

        n = self.config.refute_streak
        if len(epoch) >= n and all(m.tag == REFUTE for m in epoch[-n:]):
            agents = ", ".join(dict.fromkeys(m.agent_id for m in epoch[-n:]))
            return DeadlockReport(
                True, RULE_REFUTE_LOOP,
                f"The last {n} messages are all REFUTE ({agents}); nobody can revise",
                positions, objectors,
            )

        s = self.config.stagnation
        if s is not None and len(epoch) >= s:
            window = epoch[-s:]
            first = window[0].iteration
            seen = {m.prediction for m in messages if m.iteration < first}
            novel = [m for m in window if m.prediction not in seen]
            if not novel:
                return DeadlockReport(
                    True, RULE_STAGNATION,
                    f"No new prediction in the last {s} messages and no consensus",
                    positions, objectors,
                )
        return DeadlockReport(False, positions=positions, objectors=objectors)
