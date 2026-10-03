import pytest

from ai_project.llm import AgentDecisionParser, ParseError
from ai_project.protocol.pxp import PXPTag
from ai_project.agents.models import AgentDecision


class TestAgentDecisionParser:
    """Tests for AgentDecisionParser."""

    def setup_method(self) -> None:
        self.parser = AgentDecisionParser()

    def test_valid_json(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "explanation": "Good", "confidence": 0.8}'
        decision = self.parser.parse(json_str)

        assert decision.tag == PXPTag.RATIFY
        assert decision.prediction == "Option A"
        assert decision.confidence == 0.8

    def test_valid_json_with_metadata(self) -> None:
        json_str = '{"tag": "REFUTE", "prediction": "Option B", "explanation": "Bad", "confidence": 0.7, "metadata": {"key": "value"}}'
        decision = self.parser.parse(json_str)

        assert decision.metadata["key"] == "value"

    def test_markdown_fence_removed(self) -> None:
        json_str = '```json\n{"tag": "RATIFY", "prediction": "Option A", "explanation": "Good", "confidence": 0.8}\n```'
        decision = self.parser.parse(json_str)

        assert decision.tag == PXPTag.RATIFY

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ParseError):
            self.parser.parse("not valid json")

    def test_missing_tag_raises(self) -> None:
        json_str = '{"prediction": "Option A", "explanation": "Good", "confidence": 0.8}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_missing_prediction_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "explanation": "Good", "confidence": 0.8}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_missing_explanation_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "confidence": 0.8}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_missing_confidence_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "explanation": "Good"}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_empty_prediction_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "", "explanation": "Good", "confidence": 0.8}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_empty_explanation_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "explanation": "", "confidence": 0.8}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_confidence_too_high_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "explanation": "Good", "confidence": 1.5}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_confidence_negative_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "explanation": "Good", "confidence": -0.1}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_invalid_tag_raises(self) -> None:
        json_str = '{"tag": "INVALID", "prediction": "Option A", "explanation": "Good", "confidence": 0.8}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_invalid_confidence_type_raises(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "explanation": "Good", "confidence": "high"}'
        with pytest.raises(ParseError):
            self.parser.parse(json_str)

    def test_extra_fields_allowed(self) -> None:
        json_str = '{"tag": "RATIFY", "prediction": "Option A", "explanation": "Good", "confidence": 0.8, "extra": "field"}'
        decision = self.parser.parse(json_str)
        assert decision.tag == PXPTag.RATIFY

class TestReflectionParsing:
    def setup_method(self) -> None:
        self.parser = AgentDecisionParser()

    def test_no_change_returns_none(self) -> None:
        assert self.parser.parse_reflection('{"no_change": true, "explanation": "fine"}') is None

    def test_revision_parsed(self) -> None:
        raw = ('{"tag": "REFUTE", "prediction": "Option A", "explanation": "x", '
               '"confidence": 0.8, "metadata": {"alternative": "Option B"}}')
        decision = self.parser.parse_reflection(raw)
        assert decision.tag == PXPTag.REFUTE
        assert decision.metadata["alternative"] == "Option B"

    def test_non_object_rejected(self) -> None:
        with pytest.raises(ParseError):
            self.parser.parse_reflection("[1, 2]")
