import pytest

from ai_project.agents.specialist import SpecialistAgent
from ai_project.agents.models import AgentDecision
from ai_project.llm import MockLLMProvider
from ai_project.protocol.pxp import PXPTag
from ai_project.blackboard import Blackboard


class TestSpecialistAgent:
    """Tests for SpecialistAgent."""

    def setup_method(self) -> None:
        self.agent = SpecialistAgent(llm_provider=MockLLMProvider())

    def test_initial_prediction(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task")

        msg = self.agent.act(board)

        assert msg.agent_id == "specialist"
        assert msg.tag in [PXPTag.RATIFY, PXPTag.REVISE, PXPTag.REFUTE]
        assert msg.prediction in ["Option A", "Option B", "Option C", "Option D"]
        assert msg.explanation != ""
        assert 0.0 <= msg.confidence <= 1.0
        assert msg.iteration == 1

    def test_responds_to_existing_prediction(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task")

        decision = AgentDecision(
            tag=PXPTag.RATIFY,
            prediction="Option A",
            explanation="Good reason",
            confidence=0.8,
        )
        msg = decision.to_pxp_message("analyst", 1)
        board.publish_message(msg)

        msg2 = self.agent.act(board)

        assert msg2.tag in [PXPTag.RATIFY, PXPTag.REVISE, PXPTag.REFUTE]
        assert msg2.iteration == 2

    def test_deterministic_output(self) -> None:
        board1 = Blackboard()
        board1.initialize_task("Same task")
        msg1 = self.agent.act(board1)

        board2 = Blackboard()
        board2.initialize_task("Same task")
        msg2 = self.agent.act(board2)

        assert msg1.prediction == msg2.prediction
        assert msg1.tag == msg2.tag