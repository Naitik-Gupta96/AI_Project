import json
from typing import Any, Dict, Optional

from ai_project.protocol.pxp import PXPTag
from ai_project.agents.models import AgentDecision
from ai_project.llm.base import LLMProviderError


class ParseError(LLMProviderError):
    """Raised when LLM output cannot be parsed into a valid AgentDecision."""
    pass


class AgentDecisionParser:
    """Parses and validates structured LLM output into AgentDecision."""

    REQUIRED_FIELDS = ["tag", "prediction", "explanation", "confidence"]

    def parse(self, raw_output: str) -> AgentDecision:
        """
        Parse raw LLM output into AgentDecision.

        Args:
            raw_output: Raw text from LLM (expected JSON)

        Returns:
            Validated AgentDecision

        Raises:
            ParseError: If output is invalid or missing required fields
        """
        # Try to extract JSON from output
        json_str = self._extract_json(raw_output)
        if not json_str:
            raise ParseError(f"No valid JSON found in output: {raw_output[:200]}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON: {e}")
        if not isinstance(data, dict):
            raise ParseError("Expected a JSON object")

        return self._validate_and_create(data)

    def parse_reflection(self, raw_output: str) -> Optional[AgentDecision]:
        """
        Parse a counterfactual-reflection answer.

        Returns None if the agent answered ``{"no_change": true, ...}``,
        otherwise the revised decision.
        """
        json_str = self._extract_json(raw_output)
        if not json_str:
            raise ParseError(f"No valid JSON found in output: {raw_output[:200]}")
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON: {e}")
        if not isinstance(data, dict):
            raise ParseError("Expected a JSON object")
        if data.get("no_change") is True:
            return None
        return self._validate_and_create(data)

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON object from text, handling markdown fences."""
        # Remove markdown code fences if present
        text = text.strip()

        # Try to find JSON object
        if text.startswith("```"):
            # Remove fences
            lines = text.split("\n")
            # Find first { and last }
            start = -1
            end = -1
            for i, line in enumerate(lines):
                if "{" in line and start == -1:
                    start = i
                if "}" in line:
                    end = i
            if start != -1 and end != -1:
                text = "\n".join(lines[start:end+1])

        # Direct JSON object
        if text.startswith("{") and text.endswith("}"):
            return text

        # Try to find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]

        return None

    def _validate_and_create(self, data: Dict[str, Any]) -> AgentDecision:
        """Validate data and create AgentDecision."""
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in data:
                raise ParseError(f"Missing required field: {field}")

        # Validate tag
        tag_str = str(data["tag"]).strip().upper()
        try:
            tag = PXPTag.from_string(tag_str)
        except ValueError as e:
            raise ParseError(f"Invalid tag: {tag_str}. {e}")

        # Validate prediction
        prediction = str(data["prediction"]).strip()
        if not prediction:
            raise ParseError("prediction must be non-empty")

        # Validate explanation
        explanation = str(data["explanation"]).strip()
        if not explanation:
            raise ParseError("explanation must be non-empty")

        # Validate confidence
        try:
            confidence = float(data["confidence"])
        except (TypeError, ValueError):
            raise ParseError("confidence must be numeric")

        if not 0.0 <= confidence <= 1.0:
            raise ParseError(f"confidence must be between 0.0 and 1.0, got {confidence}")

        # Optional metadata
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return AgentDecision(
            tag=tag,
            prediction=prediction,
            explanation=explanation,
            confidence=confidence,
            metadata=metadata,
        )