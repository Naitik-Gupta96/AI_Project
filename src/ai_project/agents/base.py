from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard
from ai_project.agents.models import AgentDecision, AgentContext
from ai_project.blackboard.models import HistoryEvent
from ai_project.llm import LLMProvider, AgentDecisionParser, ParseError


class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Agents are independent reasoning units that:
    - Have a stable identity and role
    - Can inspect Blackboard state and history
    - Produce structured decisions
    - Convert decisions to PXP messages
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        llm_provider: Optional[LLMProvider] = None,
        parser: Optional[AgentDecisionParser] = None,
    ):
        """
        Initialize agent.

        Args:
            agent_id: Unique identifier for this agent
            role: Human-readable role description
            llm_provider: LLM provider for reasoning (uses mock if None)
            parser: Parser for structured output (uses default if None)
        """
        self.agent_id = agent_id
        self.role = role
        self.llm_provider = llm_provider
        self.parser = parser or AgentDecisionParser()

    @abstractmethod
    def reason(self, context: AgentContext) -> AgentDecision:
        """
        Perform reasoning based on context.

        Args:
            context: Structured context from Blackboard

        Returns:
            AgentDecision with tag, prediction, explanation, confidence
        """
        pass

    def act(self, board: Blackboard) -> PXPMessage:
        """
        Execute agent action: build context, reason, create PXP message.

        This is the main entry point for the scheduler.

        Args:
            board: Blackboard to read from and publish to

        Returns:
            PXPMessage ready for board.publish_message()

        Raises:
            AgentError: If reasoning or parsing fails
        """
        context = self._build_context(board)
        decision = self.reason(context)

        iteration = board.get_iteration() + 1
        return decision.to_pxp_message(self.agent_id, iteration)

    def _build_context(self, board: Blackboard) -> AgentContext:
        """Build structured context from Blackboard state."""
        state = board.get_state()
        history = board.get_history()

        return AgentContext(
            task=state.task,
            current_prediction=state.current_prediction,
            current_explanation=state.current_explanation,
            status=state.status.value,
            iteration=state.iteration,
            recent_history=list(history),  # All history by default
            agent_id=self.agent_id,
            agent_role=self.role,
        )

    def _call_llm(self, prompt: str) -> AgentDecision:
        """
        Call LLM provider and parse response.

        Args:
            prompt: Formatted prompt for the LLM

        Returns:
            Parsed AgentDecision

        Raises:
            AgentError: If provider unavailable or parsing fails
        """
        if self.llm_provider is None:
            raise AgentError("No LLM provider configured")

        if not self.llm_provider.is_available():
            raise AgentError("LLM provider not available")

        try:
            raw_output = self.llm_provider.generate(prompt)
        except Exception as e:
            raise AgentError(f"LLM provider error: {e}")

        try:
            return self.parser.parse(raw_output)
        except ParseError as e:
            raise AgentError(f"Failed to parse LLM output: {e}")

    def get_identity(self) -> Dict[str, str]:
        """Get agent identity info."""
        return {"agent_id": self.agent_id, "role": self.role}