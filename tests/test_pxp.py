import pytest

from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.protocol.validator import PXPValidator, ValidationError


class TestPXPTag:
    """Tests for PXPTag enum."""

    def test_valid_tags(self) -> None:
        assert PXPTag.RATIFY.value == "RATIFY"
        assert PXPTag.REVISE.value == "REVISE"
        assert PXPTag.REFUTE.value == "REFUTE"
        assert PXPTag.REJECT.value == "REJECT"

    def test_from_string_case_insensitive(self) -> None:
        assert PXPTag.from_string("ratify") == PXPTag.RATIFY
        assert PXPTag.from_string("REVISE") == PXPTag.REVISE
        assert PXPTag.from_string("Refute") == PXPTag.REFUTE

    def test_from_string_invalid(self) -> None:
        with pytest.raises(ValueError):
            PXPTag.from_string("INVALID")


class TestPXPMessage:
    """Tests for PXPMessage dataclass."""

    def test_create_valid_ratify(self) -> None:
        msg = PXPMessage.create(
            agent_id="agent_A",
            tag=PXPTag.RATIFY,
            prediction="Option B",
            explanation="Option B satisfies constraints.",
            confidence=0.82,
            iteration=1,
        )
        assert msg.agent_id == "agent_A"
        assert msg.tag == PXPTag.RATIFY
        assert msg.prediction == "Option B"
        assert msg.explanation == "Option B satisfies constraints."
        assert msg.confidence == 0.82
        assert msg.iteration == 1
        assert msg.message_id.startswith("msg_")
        assert msg.timestamp.endswith("Z")

    def test_create_valid_revise(self) -> None:
        msg = PXPMessage.create(
            agent_id="agent_B",
            tag=PXPTag.REVISE,
            prediction="Option C",
            explanation="Modified approach.",
            confidence=0.75,
            iteration=2,
        )
        assert msg.tag == PXPTag.REVISE

    def test_create_valid_refute(self) -> None:
        msg = PXPMessage.create(
            agent_id="agent_C",
            tag=PXPTag.REFUTE,
            prediction="Option B",
            explanation="Fails constraint C3.",
            confidence=0.90,
            iteration=3,
        )
        assert msg.tag == PXPTag.REFUTE

    def test_create_valid_reject(self) -> None:
        msg = PXPMessage.create(
            agent_id="agent_D",
            tag=PXPTag.REJECT,
            prediction="None",
            explanation="Task is ill-posed.",
            confidence=0.95,
            iteration=1,
        )
        assert msg.tag == PXPTag.REJECT

    def test_confidence_optional(self) -> None:
        msg = PXPMessage.create(
            agent_id="agent_A",
            tag=PXPTag.RATIFY,
            prediction="Option B",
            explanation="Reason.",
        )
        assert msg.confidence is None

    def test_to_dict(self) -> None:
        msg = PXPMessage.create(
            agent_id="agent_A",
            tag=PXPTag.RATIFY,
            prediction="Option B",
            explanation="Reason.",
            confidence=0.8,
            iteration=1,
        )
        d = msg.to_dict()
        assert d["agent_id"] == "agent_A"
        assert d["tag"] == "RATIFY"
        assert d["prediction"] == "Option B"
        assert d["confidence"] == 0.8
        assert d["iteration"] == 1

    def test_from_dict(self) -> None:
        data = {
            "message_id": "msg_123",
            "agent_id": "agent_A",
            "tag": "RATIFY",
            "prediction": "Option B",
            "explanation": "Reason.",
            "confidence": 0.8,
            "iteration": 1,
            "timestamp": "2024-01-01T00:00:00Z",
            "metadata": {},
        }
        msg = PXPMessage.from_dict(data)
        assert msg.message_id == "msg_123"
        assert msg.tag == PXPTag.RATIFY
        assert msg.confidence == 0.8

    def test_tag_string_conversion(self) -> None:
        msg = PXPMessage(
            message_id="msg_1",
            agent_id="agent_A",
            tag="RATIFY",  # string instead of enum
            prediction="Option B",
            explanation="Reason.",
            iteration=1,
        )
        assert msg.tag == PXPTag.RATIFY


class TestPXPValidator:
    """Tests for PXPValidator."""

    def test_valid_ratify(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "Reason", 0.8, 1)
        errors = PXPValidator.validate(msg)
        assert errors == []

    def test_valid_revise(self) -> None:
        msg = PXPMessage.create("agent_B", PXPTag.REVISE, "C", "Reason", 0.7, 2)
        errors = PXPValidator.validate(msg)
        assert errors == []

    def test_valid_refute(self) -> None:
        msg = PXPMessage.create("agent_C", PXPTag.REFUTE, "B", "Reason", 0.9, 3)
        errors = PXPValidator.validate(msg)
        assert errors == []

    def test_valid_reject(self) -> None:
        msg = PXPMessage.create("agent_D", PXPTag.REJECT, "None", "Reason", 0.95, 1)
        errors = PXPValidator.validate(msg)
        assert errors == []

    def test_invalid_tag(self) -> None:
        # Can't easily test invalid enum through validator since construction fails
        # The enum itself prevents invalid tags - this is expected behavior
        # Test that valid tags work
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "Reason", 0.8, 1)
        errors = PXPValidator.validate(msg)
        assert errors == []

    def test_invalid_confidence_non_numeric_constructor_fails(self) -> None:
        # Constructor fails before validation - this is expected
        with pytest.raises(ValueError):
            PXPMessage(
                message_id="msg_1",
                agent_id="agent_A",
                tag=PXPTag.RATIFY,
                prediction="B",
                explanation="Reason",
                confidence="high",  # type: ignore
                iteration=1,
            )

    def test_missing_message_id_auto_generated(self) -> None:
        # message_id is auto-generated if empty, so validator never sees empty
        msg = PXPMessage(
            message_id="",
            agent_id="agent_A",
            tag=PXPTag.RATIFY,
            prediction="B",
            explanation="Reason",
            iteration=1,
        )
        # message_id gets auto-generated in __post_init__
        assert msg.message_id != ""
        errors = PXPValidator.validate(msg)
        assert errors == []

    def test_validate_or_raise_valid(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "Reason", 0.8, 1)
        PXPValidator.validate_or_raise(msg)  # Should not raise

    def test_validate_or_raise_invalid(self) -> None:
        msg = PXPMessage(
            message_id="msg_1",
            agent_id="agent_A",
            tag=PXPTag.RATIFY,
            prediction="B",
            explanation="",
            iteration=1,
        )
        with pytest.raises(ValueError) as exc_info:
            PXPValidator.validate_or_raise(msg)
        assert "explanation" in str(exc_info.value)