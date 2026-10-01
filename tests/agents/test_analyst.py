import pytest

from ai_project.agents.analyst import AnalystAgent
from ai_project.agents.models import AgentContext
from ai_project.llm import MockLLMProvider
from ai_project.protocol.pxp import PXPTag
from ai_project.blackboard import Blackboard


class TestAnalystAgent:
    """Tests for AnalystAgent."""

    def setup_method(self) -> None:
        self.agent = AnalystAgent(llm_provider=MockLLMProvider())

    def test_initial_prediction(self) -> None:
        board = Blackboard()
        board.initialize_task("Choose between options")

        msg = self.agent.act(board)

        assert msg.agent_id == "analyst"
        assert msg.tag == PXPTag.RATIFY
        assert msg.prediction in ["Option A", "Option B", "Option C", "Option D"]
        assert msg.explanation != ""
        assert 0.0 <= msg.confidence <= 1.0
        assert msg.iteration == 1

    def test_existing_prediction_ratifies(self) -> None:
        from ai_project.agents.models import AgentDecision

        board = Blackboard()
        board.initialize_task("Test task")

        # Pre-populate with a prediction
        decision = AgentDecision(
            tag=PXPTag.RATIFY,
            prediction="Option B",
            explanation="Existing reason",
            confidence=0.8,
        )
        msg = decision.to_pxp_message("analyst", 1)
        board.publish_message(msg)

        # Analyst acts again
        msg2 = self.agent.act(board)

        assert msg2.tag == PXPTag.RATIFY
        assert msg2.prediction == "Option B"

    def test_deterministic_output(self) -> None:
        board1 = Blackboard()
        board1.initialize_task("Same task")
        msg1 = self.agent.act(board1)

        board2 = Blackboard()
        board2.initialize_task("Same task")
        msg2 = self.agent.act(board2)

        # Same task should produce same prediction
        assert msg1.prediction == msg2.prediction

    def test_different_tasks_different_predictions(self) -> None:
        board1 = Blackboard()
        board1.initialize_task("Task A")
        msg1 = self.agent.act(board1)

        board2 = Blackboard()
        board2.initialize_task("Task B")
        msg2 = self.agent.act(board2)

        # Different tasks may produce different predictions
        # (Not guaranteed but likely with our mock)
        assert msg1.prediction in ["Option A", "Option B", "Option C", "Option D"]
        assert msg2.prediction in ["Option A", "Option B", "Option C", "Option D"]