import pytest

from ai_project.agents.base import BaseAgent, AgentError
from ai_project.agents.models import AgentContext, AgentDecision
from ai_project.protocol.pxp import PXPTag
from ai_project.llm import MockLLMProvider


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""

    def __init__(self, agent_id: str = "test_agent", role: str = "Test", **kwargs):
        super().__init__(agent_id, role, **kwargs)
        self._reason_result: AgentDecision = None

    def set_reason_result(self, decision: AgentDecision) -> None:
        self._reason_result = decision

    def reason(self, context: AgentContext) -> AgentDecision:
        if self._reason_result is None:
            return AgentDecision(
                tag=PXPTag.RATIFY,
                prediction="Default",
                explanation="Default",
                confidence=0.5,
            )
        return self._reason_result


class TestBaseAgent:
    """Tests for BaseAgent."""

    def test_construction(self) -> None:
        agent = ConcreteAgent(agent_id="analyst_1", role="Analyst")
        assert agent.agent_id == "analyst_1"
        assert agent.role == "Analyst"

    def test_get_identity(self) -> None:
        agent = ConcreteAgent(agent_id="critic_1", role="Critic")
        identity = agent.get_identity()
        assert identity["agent_id"] == "critic_1"
        assert identity["role"] == "Critic"

    def test_act_with_mock_provider(self) -> None:
        from ai_project.blackboard import Blackboard

        board = Blackboard()
        board.initialize_task("Test task")

        agent = ConcreteAgent(llm_provider=MockLLMProvider())
        msg = agent.act(board)

        assert msg.agent_id == "test_agent"
        assert msg.iteration == 1
        assert msg.tag in [PXPTag.RATIFY, PXPTag.REVISE, PXPTag.REFUTE, PXPTag.REJECT]

    def test_act_increments_iteration(self) -> None:
        from ai_project.blackboard import Blackboard

        board = Blackboard()
        board.initialize_task("Test task")

        agent = ConcreteAgent(llm_provider=MockLLMProvider())
        msg1 = agent.act(board)
        board.publish_message(msg1)

        msg2 = agent.act(board)
        assert msg2.iteration == 2

    def test_act_without_provider_raises(self) -> None:
        from ai_project.blackboard import Blackboard

        board = Blackboard()
        board.initialize_task("Test task")

        # Use an agent that actually tries to call the LLM
        agent = ConcreteAgent(llm_provider=None)
        # Override reason to force LLM call
        original_reason = agent.reason
        def force_llm_call(context):
            return agent._call_llm("test prompt")
        agent.reason = force_llm_call

        with pytest.raises(AgentError):
            agent.act(board)

    def test_build_context(self) -> None:
        from ai_project.blackboard import Blackboard

        board = Blackboard()
        board.initialize_task("Test task")
        msg = AgentDecision(
            tag=PXPTag.RATIFY, prediction="A", explanation="Reason", confidence=0.8
        ).to_pxp_message("analyst", 1)
        board.publish_message(msg)

        agent = ConcreteAgent()
        context = agent._build_context(board)

        assert context.task == "Test task"
        assert context.current_prediction == "A"
        assert context.iteration == 1
        assert len(context.recent_history) == 1
        assert context.agent_id == "test_agent"