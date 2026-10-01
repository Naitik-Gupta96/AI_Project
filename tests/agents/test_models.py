import pytest

from ai_project.agents.models import AgentDecision, AgentContext
from ai_project.protocol.pxp import PXPTag


class TestAgentDecision:
    """Tests for AgentDecision model."""

    def test_valid_creation(self) -> None:
        decision = AgentDecision(
            tag=PXPTag.RATIFY,
            prediction="Option A",
            explanation="Good choice",
            confidence=0.8,
        )
        assert decision.tag == PXPTag.RATIFY
        assert decision.prediction == "Option A"
        assert decision.confidence == 0.8

    def test_valid_creation_with_metadata(self) -> None:
        decision = AgentDecision(
            tag=PXPTag.REVISE,
            prediction="Option B",
            explanation="Modified approach",
            confidence=0.75,
            metadata={"source": "test"},
        )
        assert decision.metadata["source"] == "test"

    def test_string_tag_conversion(self) -> None:
        decision = AgentDecision(
            tag="REFUTE",
            prediction="Option A",
            explanation="Disagree",
            confidence=0.9,
        )
        assert decision.tag == PXPTag.REFUTE

    def test_invalid_confidence_high(self) -> None:
        with pytest.raises(ValueError):
            AgentDecision(
                tag=PXPTag.RATIFY,
                prediction="Option A",
                explanation="Good",
                confidence=1.5,
            )

    def test_invalid_confidence_low(self) -> None:
        with pytest.raises(ValueError):
            AgentDecision(
                tag=PXPTag.RATIFY,
                prediction="Option A",
                explanation="Good",
                confidence=-0.1,
            )

    def test_empty_prediction(self) -> None:
        with pytest.raises(ValueError):
            AgentDecision(
                tag=PXPTag.RATIFY,
                prediction="",
                explanation="Good",
                confidence=0.8,
            )

    def test_empty_explanation(self) -> None:
        with pytest.raises(ValueError):
            AgentDecision(
                tag=PXPTag.RATIFY,
                prediction="Option A",
                explanation="",
                confidence=0.8,
            )

    def test_to_pxp_message(self) -> None:
        decision = AgentDecision(
            tag=PXPTag.RATIFY,
            prediction="Option A",
            explanation="Good",
            confidence=0.8,
        )
        msg = decision.to_pxp_message("agent_test", 1)
        assert msg.agent_id == "agent_test"
        assert msg.iteration == 1
        assert msg.tag == PXPTag.RATIFY
        assert msg.prediction == "Option A"


class TestAgentContext:
    """Tests for AgentContext model."""

    def test_creation(self) -> None:
        from ai_project.blackboard.models import HistoryEvent
        context = AgentContext(
            task="Test task",
            current_prediction="Option A",
            current_explanation="Reason",
            status="RUNNING",
            iteration=1,
            recent_history=[],
            agent_id="analyst",
            agent_role="Analyst",
        )
        assert context.task == "Test task"
        assert context.iteration == 1

    def test_to_prompt_context(self) -> None:
        from ai_project.blackboard.models import HistoryEvent
        history = [
            HistoryEvent(
                iteration=1,
                agent_id="analyst",
                tag="RATIFY",
                timestamp="2024-01-01T00:00:00Z",
                prediction="Option A",
                explanation="Good",
                confidence=0.8,
            )
        ]
        context = AgentContext(
            task="Test task",
            current_prediction="Option A",
            current_explanation="Reason",
            status="RUNNING",
            iteration=1,
            recent_history=history,
            agent_id="critic",
            agent_role="Critic",
        )
        prompt_ctx = context.to_prompt_context()
        assert prompt_ctx["task"] == "Test task"
        assert prompt_ctx["iteration"] == 1
        assert len(prompt_ctx["recent_history"]) == 1
        assert prompt_ctx["agent_id"] == "critic"