"""
Scheduling policies: decide which agent acts next.

A policy is a replaceable component. It receives a read-only
``SchedulingContext`` built from the Blackboard's public API and returns a
``Selection`` (agent id + the rule and reason behind the choice).

Policies shipped here are stateless: their choice depends only on the
context. That makes counterfactual replay deterministic, because a branch
board with the same history yields the same selection.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ai_project.blackboard.models import BlackboardState, HistoryEvent
from ai_project.deadlock.stances import is_objection, latest_stances, proposal_epoch, supports


@dataclass(frozen=True)
class SchedulingContext:
    """
    Read-only view of the board handed to a policy.

    Attributes:
        state: Current Blackboard state
        history: Chronological history
        agent_ids: Registered agents in registration order
        step: Number of agent actions this scheduler has already performed
    """

    state: BlackboardState
    history: tuple[HistoryEvent, ...]
    agent_ids: tuple[str, ...]
    step: int

    @property
    def last_event(self) -> HistoryEvent | None:
        """Most recent history event, or None."""
        return self.history[-1] if self.history else None

    @property
    def last_agent(self) -> str | None:
        """Agent that produced the most recent event, or None."""
        last = self.last_event
        return last.agent_id if last else None


@dataclass(frozen=True)
class Selection:
    """
    A policy's decision.

    Attributes:
        agent_id: Agent to invoke next
        rule: Short machine-readable name of the rule that fired
        reason: Human-readable explanation (shown in the trace / UI)
    """

    agent_id: str
    rule: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {"agent_id": self.agent_id, "rule": self.rule, "reason": self.reason}


class SchedulingPolicy(ABC):
    """Base class for scheduling policies."""

    name: str = "policy"

    @abstractmethod
    def select(self, context: SchedulingContext) -> Selection:
        """
        Choose the next agent.

        Args:
            context: Read-only board view

        Returns:
            Selection naming one of ``context.agent_ids``
        """

    def describe(self) -> dict[str, Any]:
        """Serializable description of this policy and its configuration."""
        return {"name": self.name}


def _next_after(agent_ids: tuple[str, ...], last_agent: str | None) -> str:
    """Agent following ``last_agent`` in registration order (first if unknown/None)."""
    if last_agent in agent_ids:
        return agent_ids[(agent_ids.index(last_agent) + 1) % len(agent_ids)]
    return agent_ids[0]


class RoundRobinPolicy(SchedulingPolicy):
    """Agents take turns in registration order, starting after the last speaker."""

    name = "round_robin"

    def select(self, context: SchedulingContext) -> Selection:
        if not context.agent_ids:
            raise ValueError("No agents registered")
        agent_id = _next_after(context.agent_ids, context.last_agent)
        if context.last_agent is None:
            reason = f"First turn goes to the first registered agent ({agent_id})"
        else:
            reason = f"Round robin: {agent_id} follows {context.last_agent}"
        return Selection(agent_id, "round_robin", reason)


class PriorityPolicy(SchedulingPolicy):
    """
    Deterministic role-based priority.

    Rules, checked in order. A rule is skipped if its agent is not registered
    or just acted (no agent speaks twice in a row while others are available):

    1. ``no_proposal``: nothing proposed yet -> ``proposer``
    2. ``after_disagreement``: last message is REFUTE/REJECT -> ``resolver``
    3. ``after_new_proposal``: last message introduced a new proposal -> ``critic``
    4. ``pending_agreement``: first registered agent whose latest stance does not
       support the standing proposal (silent agents included)
    5. ``fallback``: round robin after the last speaker
    """

    name = "priority"

    def __init__(self, proposer: str, critic: str, resolver: str) -> None:
        """
        Args:
            proposer: Agent that opens with a prediction (e.g. "analyst")
            critic: Agent that reviews new proposals (e.g. "critic")
            resolver: Agent that responds to disagreement (e.g. "specialist")
        """
        self.proposer = proposer
        self.critic = critic
        self.resolver = resolver

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "proposer": self.proposer,
            "critic": self.critic,
            "resolver": self.resolver,
        }

    def select(self, context: SchedulingContext) -> Selection:
        if not context.agent_ids:
            raise ValueError("No agents registered")

        def eligible(agent_id: str) -> bool:
            return agent_id in context.agent_ids and (
                agent_id != context.last_agent or len(context.agent_ids) == 1
            )

        epoch = proposal_epoch(context.history)
        last = context.last_event

        if epoch.proposal is None and eligible(self.proposer):
            return Selection(
                self.proposer,
                "no_proposal",
                f"No prediction on the board yet; {self.proposer} proposes first",
            )

        if last is not None and is_objection(last) and eligible(self.resolver):
            return Selection(
                self.resolver,
                "after_disagreement",
                f"{last.agent_id} sent {last.tag} on '{last.prediction}'; "
                f"{self.resolver} responds to the disagreement",
            )

        introduced_by_last = (
            epoch.start_index is not None and epoch.start_index == len(context.history) - 1
        )
        if introduced_by_last and eligible(self.critic):
            return Selection(
                self.critic,
                "after_new_proposal",
                f"New proposal '{epoch.proposal}' from {last.agent_id}; "
                f"{self.critic} reviews it",
            )

        if epoch.proposal is not None:
            stances = latest_stances(context.history)
            for agent_id in context.agent_ids:
                if not eligible(agent_id):
                    continue
                stance = stances.get(agent_id)
                if stance is None or not supports(stance, epoch.proposal):
                    position = (
                        "has not spoken yet"
                        if stance is None
                        else f"last sent {stance.tag} '{stance.prediction}'"
                    )
                    return Selection(
                        agent_id,
                        "pending_agreement",
                        f"{agent_id} {position} and has not endorsed '{epoch.proposal}'",
                    )

        agent_id = _next_after(context.agent_ids, context.last_agent)
        return Selection(
            agent_id,
            "fallback",
            f"No priority rule applies; round robin after {context.last_agent}",
        )
