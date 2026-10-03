import pytest

from ai_project.agents.models import AgentDecision, AgentContext
from ai_project.protocol.pxp import PXPTag
from ai_project.blackboard.models import HistoryEvent
from ai_project.tasks import Evidence


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
    def test_latest_and_reflection_flags(self) -> None:
        event = HistoryEvent(1, "analyst", "RATIFY", "t", "Option A", "why", 0.8)
        ctx = AgentContext(
            agent_id="critic", role="critic", task="T", options=("Option A",),
            evidence=Evidence(), status="RUNNING", iteration=1, proposal="Option A",
            history=(event,),
        )
        assert ctx.latest is event
        assert not ctx.is_reflection

    def test_decision_alternative(self) -> None:
        decision = AgentDecision(PXPTag.REFUTE, "Option A", "bad", 0.8, {"alternative": "Option B"})
        assert decision.alternative == "Option B"
        assert decision.to_pxp_message("critic", 2).metadata["alternative"] == "Option B"
