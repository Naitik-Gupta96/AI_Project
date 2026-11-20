"""
Priority arbiter: scores every agent after each board change.

An agent is *eligible* if it has something to respond to: it has not spoken
yet, or another agent has posted since its last message. The author of the
latest message is never eligible (it would be answering itself), except for
an agent whose counterfactual intervention is pending: it must post next.

Score of an eligible agent (higher acts first; ties go to registration order):

    +10  counterfactual intervention pending
    +3   has not posted yet
    +2   another agent posted since its last message
    +1   its latest tag is not RATIFY (consensus needs it to speak again)
    +b   role bias for the latest tag (default: the critic reviews new
         INIT/REVISE theses first, the specialist answers REFUTE/REJECT first)

The ranking is deterministic, so a counterfactual replay of the same board
selects the same agents.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard.models import MessageRecord

DEFAULT_ROLE_BIAS: dict[str, dict[str, float]] = {
    "critic": {"INIT": 0.5, "REVISE": 0.5},
    "specialist": {"REFUTE": 0.5, "REJECT": 0.5},
}


@dataclass(frozen=True)
class Activation:
    agent_id: str
    score: float
    eligible: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "score": self.score, "eligible": self.eligible,
                "reasons": list(self.reasons)}


@dataclass
class PriorityArbiter:
    role_bias: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {r: dict(b) for r, b in DEFAULT_ROLE_BIAS.items()}
    )
    name: str = "priority"

    def rank(
        self,
        agents: Sequence[tuple[str, str]],
        messages: Sequence[MessageRecord],
        pending: Collection[str] = (),
    ) -> list[Activation]:
        """
        Args:
            agents: (agent_id, role) in registration order
            messages: Committed messages
            pending: Agents with a pending counterfactual intervention

        Returns:
            Every agent, eligible ones first, by descending score
        """
        latest = messages[-1] if messages else None
        last_index: dict[str, int] = {}
        for i, m in enumerate(messages):
            last_index[m.agent_id] = i

        ranked = []
        for order, (agent_id, role) in enumerate(agents):
            reasons: list[str] = []
            score = 0.0
            spoke = agent_id in last_index
            news = spoke and any(m.agent_id != agent_id
                                 for m in messages[last_index[agent_id] + 1:])
            is_author = latest is not None and latest.agent_id == agent_id
            if agent_id in pending:
                score += 10
                reasons.append("counterfactual intervention pending (+10)")
            if not spoke:
                score += 3
                reasons.append("has not posted yet (+3)")
            if news:
                score += 2
                reasons.append("new messages since its last post (+2)")
            if spoke and messages[last_index[agent_id]].tag != "RATIFY":
                score += 1
                reasons.append(f"its latest tag is {messages[last_index[agent_id]].tag} (+1)")
            if latest is not None:
                bias = self.role_bias.get(role, {}).get(latest.tag, 0.0)
                if bias:
                    score += bias
                    reasons.append(f"{role} answers {latest.tag} (+{bias:g})")
            eligible = agent_id in pending or (not is_author and (not spoke or news))
            if not eligible:
                reasons.append("authored the latest message" if is_author
                               else "nothing new to answer")
            ranked.append((not eligible, -score, order,
                           Activation(agent_id, score, eligible, tuple(reasons))))
        ranked.sort(key=lambda item: item[:3])
        return [item[3] for item in ranked]

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "role_bias": {r: dict(b) for r, b in self.role_bias.items()}}
