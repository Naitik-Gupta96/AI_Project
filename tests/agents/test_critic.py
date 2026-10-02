import pytest

from ai_project.agents.critic import CriticAgent
from ai_project.agents.models import AgentDecision
from ai_project.llm import MockLLMProvider
from ai_project.protocol.pxp import PXPTag
from ai_project.blackboard import Blackboard


class TestCriticAgent:
    """Tests for CriticAgent."""

    def setup_method(self) -> None:
        self.agent = CriticAgent(llm_provider=MockLLMProvider())

    def test_no_existing_prediction(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task")

        msg = self.agent.act(board)

        assert msg.agent_id == "critic"
        assert msg.tag == PXPTag.REVISE
        assert "Need" in msg.explanation or "cannot" in msg.explanation.lower()

    def test_can_ratify(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task for ratify")

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
        assert msg2.prediction != ""

    def test_can_refute(self) -> None:
        board = Blackboard()
        board.initialize_task("Test task for refute")

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
        assert msg2.explanation != ""

    def test_reads_history(self) -> None:
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

        assert msg2.iteration == 2

    def test_deterministic_output(self) -> None:
        board1 = Blackboard()
        board1.initialize_task("Same task")
        d1 = AgentDecision(tag=PXPTag.RATIFY, prediction="Option A", explanation="R", confidence=0.8)
        board1.publish_message(d1.to_pxp_message("analyst", 1))
        msg1 = self.agent.act(board1)

        board2 = Blackboard()
        board2.initialize_task("Same task")
        board2.publish_message(d1.to_pxp_message("analyst", 1))
        msg2 = self.agent.act(board2)

        assert msg1.tag == msg2.tag
        assert msg1.prediction == msg2.prediction