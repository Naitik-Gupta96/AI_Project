import pytest

from ai_project.agents import AnalystAgent, CriticAgent, SpecialistAgent
from ai_project.llm import MockLLMProvider
from ai_project.protocol.pxp import PXPTag
from ai_project.blackboard import Blackboard


class TestAgentIntegration:
    """End-to-end integration tests."""

    def setup_method(self) -> None:
        self.analyst = AnalystAgent(llm_provider=MockLLMProvider())
        self.critic = CriticAgent(llm_provider=MockLLMProvider())
        self.specialist = SpecialistAgent(llm_provider=MockLLMProvider())

    def test_full_agent_cycle(self) -> None:
        """Test complete cycle: Analyst -> Critic -> Specialist."""
        board = Blackboard()
        board.initialize_task("Choose the best approach for the project")

        # Analyst acts
        msg1 = self.analyst.act(board)
        board.publish_message(msg1)

        assert board.get_iteration() == 1
        assert msg1.agent_id == "analyst"
        assert msg1.tag == PXPTag.RATIFY

        # Critic acts
        msg2 = self.critic.act(board)
        board.publish_message(msg2)

        assert board.get_iteration() == 2
        assert msg2.agent_id == "critic"
        assert msg2.tag in [PXPTag.RATIFY, PXPTag.REVISE, PXPTag.REFUTE]

        # Specialist acts
        msg3 = self.specialist.act(board)
        board.publish_message(msg3)

        assert board.get_iteration() == 3
        assert msg3.agent_id == "specialist"
        assert msg3.tag in [PXPTag.RATIFY, PXPTag.REVISE, PXPTag.REFUTE]

        # Verify history
        history = board.get_history()
        assert len(history) == 3
        assert history[0].agent_id == "analyst"
        assert history[1].agent_id == "critic"
        assert history[2].agent_id == "specialist"

    def test_critic_has_access_to_analyst_reasoning(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task")

        msg1 = self.analyst.act(board)
        board.publish_message(msg1)

        msg2 = self.critic.act(board)

        # Critic should have access to analyst's prediction
        assert msg2.iteration == 2
        assert msg2.explanation != ""

    def test_specialist_has_access_to_full_history(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task")

        msg1 = self.analyst.act(board)
        board.publish_message(msg1)

        msg2 = self.critic.act(board)
        board.publish_message(msg2)

        msg3 = self.specialist.act(board)

        assert msg3.iteration == 3
        assert msg3.explanation != ""

    def test_all_messages_valid_pxp(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task")

        msg1 = self.analyst.act(board)
        board.publish_message(msg1)

        msg2 = self.critic.act(board)
        board.publish_message(msg2)

        msg3 = self.specialist.act(board)
        board.publish_message(msg3)

        # All should be valid PXP messages
        for msg in [msg1, msg2, msg3]:
            assert msg.agent_id != ""
            assert msg.tag in [PXPTag.RATIFY, PXPTag.REVISE, PXPTag.REFUTE, PXPTag.REJECT]
            assert msg.prediction != ""
            assert msg.explanation != ""
            if msg.confidence is not None:
                assert 0.0 <= msg.confidence <= 1.0
            assert msg.iteration > 0

    def test_board_state_reflects_last_message(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task")

        msg1 = self.analyst.act(board)
        board.publish_message(msg1)

        state1 = board.get_state()
        assert state1.current_prediction == msg1.prediction
        assert state1.current_explanation == msg1.explanation

        msg2 = self.critic.act(board)
        board.publish_message(msg2)

        state2 = board.get_state()
        assert state2.current_prediction == msg2.prediction
        assert state2.current_explanation == msg2.explanation