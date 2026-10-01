import pytest

from ai_project.llm import MockLLMProvider, AgentDecisionParser, ParseError
from ai_project.protocol.pxp import PXPTag
from ai_project.agents.models import AgentDecision


class TestMockLLMProvider:
    """Tests for MockLLMProvider."""

    def setup_method(self) -> None:
        self.provider = MockLLMProvider()

    def test_is_available(self) -> None:
        assert self.provider.is_available() is True

    def test_generate_returns_json(self) -> None:
        prompt = "You are the Analyst agent. Task: test."
        output = self.provider.generate(prompt)

        # Should be valid JSON
        import json
        data = json.loads(output)
        assert "tag" in data
        assert "prediction" in data
        assert "explanation" in data
        assert "confidence" in data

    def test_analyst_prompt_produces_ratify(self) -> None:
        prompt = "You are the Analyst agent. Task: test."
        output = self.provider.generate(prompt)

        import json
        data = json.loads(output)
        assert data["tag"] == "RATIFY"
        assert data["prediction"] in ["Option A", "Option B", "Option C", "Option D"]
        assert 0.0 <= data["confidence"] <= 1.0

    def test_critic_prompt_produces_valid_tag(self) -> None:
        prompt = "You are the Critic agent. Task: test. Current prediction: Option A."
        output = self.provider.generate(prompt)

        import json
        data = json.loads(output)
        assert data["tag"] in ["RATIFY", "REVISE", "REFUTE", "REJECT"]

    def test_specialist_prompt_produces_valid_tag(self) -> None:
        prompt = "You are the Specialist agent. Task: test."
        output = self.provider.generate(prompt)

        import json
        data = json.loads(output)
        assert data["tag"] in ["RATIFY", "REVISE", "REFUTE", "REJECT"]

    def test_deterministic_for_same_prompt(self) -> None:
        prompt = "You are the Analyst agent. Task: same task."
        out1 = self.provider.generate(prompt)
        out2 = self.provider.generate(prompt)

        assert out1 == out2

    def test_different_roles_different_outputs(self) -> None:
        analyst_prompt = "You are the Analyst agent. Task: test."
        critic_prompt = "You are the Critic agent. Task: test."

        out1 = self.provider.generate(analyst_prompt)
        out2 = self.provider.generate(critic_prompt)

        # Should be different (different roles)
        import json
        data1 = json.loads(out1)
        data2 = json.loads(out2)

        # Both should be valid
        assert data1["tag"] in ["RATIFY", "REVISE", "REFUTE", "REJECT"]
        assert data2["tag"] in ["RATIFY", "REVISE", "REFUTE", "REJECT"]


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