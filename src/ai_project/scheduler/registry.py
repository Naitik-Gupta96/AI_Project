"""
Agent registry for the Scheduler.

Any object with an ``agent_id`` attribute and an ``act(board) -> PXPMessage``
method can be scheduled. This matches Person 2's ``BaseAgent.act`` contract
without importing it, so the Scheduler works with LLM agents and mock agents
alike.
"""

from collections.abc import Iterable, Iterator, Mapping
from typing import Protocol, Union, runtime_checkable

from ai_project.blackboard import Blackboard
from ai_project.protocol.pxp import PXPMessage


@runtime_checkable
class SchedulableAgent(Protocol):
    """Structural interface the Scheduler requires of an agent."""

    agent_id: str

    def act(self, board: Blackboard) -> PXPMessage:
        """Read the board and return the PXP message this agent wants to publish."""
        ...


AgentsInput = Union["AgentRegistry", Mapping[str, SchedulableAgent], Iterable[SchedulableAgent]]


class AgentRegistry:
    """
    Ordered collection of agents keyed by ``agent_id``.

    Registration order is significant: policies use it to break ties, which
    keeps scheduling deterministic.
    """

    def __init__(
        self, agents: Mapping[str, SchedulableAgent] | Iterable[SchedulableAgent] = ()
    ) -> None:
        self._agents: dict[str, SchedulableAgent] = {}
        if isinstance(agents, Mapping):
            for name, agent in agents.items():
                self.register(agent, name=name)
        else:
            for agent in agents:
                self.register(agent)

    @classmethod
    def from_input(cls, agents: AgentsInput) -> "AgentRegistry":
        """Return ``agents`` if it already is a registry, else build one."""
        if isinstance(agents, AgentRegistry):
            return agents
        return cls(agents)

    def register(self, agent: SchedulableAgent, name: str | None = None) -> None:
        """
        Add an agent.

        Args:
            agent: Object with ``agent_id`` and ``act(board)``
            name: Optional registry key; must equal ``agent.agent_id`` because
                history records agent_id and policies match on it

        Raises:
            TypeError: If the agent lacks ``agent_id`` or ``act``
            ValueError: If the name mismatches or the agent_id is already registered
        """
        if not isinstance(agent, SchedulableAgent):
            raise TypeError(
                f"{agent!r} must have an 'agent_id' attribute and an 'act(board)' method"
            )
        agent_id = agent.agent_id
        if not agent_id:
            raise ValueError("agent_id must be non-empty")
        if name is not None and name != agent_id:
            raise ValueError(f"Registry key '{name}' must match agent.agent_id '{agent_id}'")
        if agent_id in self._agents:
            raise ValueError(f"Agent '{agent_id}' is already registered")
        self._agents[agent_id] = agent

    def get(self, agent_id: str) -> SchedulableAgent:
        """Return the agent with this id; raises KeyError if unknown."""
        try:
            return self._agents[agent_id]
        except KeyError:
            raise KeyError(
                f"Unknown agent '{agent_id}'. Registered: {list(self._agents)}"
            ) from None

    @property
    def agent_ids(self) -> tuple[str, ...]:
        """Registered agent ids in registration order."""
        return tuple(self._agents)

    def __contains__(self, agent_id: object) -> bool:
        return agent_id in self._agents

    def __iter__(self) -> Iterator[SchedulableAgent]:
        return iter(list(self._agents.values()))

    def __len__(self) -> int:
        return len(self._agents)
