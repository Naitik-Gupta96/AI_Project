from dataclasses import dataclass
from typing import List, Optional

from ai_project.protocol.pxp import PXPMessage, PXPTag


@dataclass
class ValidationError:
    """Represents a validation error with field and message."""
    field: str
    message: str


class PXPValidator:
    """Validates PXP messages for structural/protocol correctness."""

    @staticmethod
    def validate(message: PXPMessage) -> List[ValidationError]:
        """
        Validate a PXP message.

        Returns:
            List of ValidationError objects. Empty list means valid.
        """
        errors = []

        # message_id must be present
        if not message.message_id or not message.message_id.strip():
            errors.append(ValidationError("message_id", "message_id must be non-empty"))

        # agent_id must be non-empty
        if not message.agent_id or not message.agent_id.strip():
            errors.append(ValidationError("agent_id", "agent_id must be non-empty"))

        # tag must be valid (handled by PXPTag enum, but check anyway)
        if not isinstance(message.tag, PXPTag):
            errors.append(ValidationError("tag", f"tag must be a valid PXPTag, got {type(message.tag)}"))

        # prediction must be present
        if not message.prediction or not message.prediction.strip():
            errors.append(ValidationError("prediction", "prediction must be non-empty"))

        # explanation must be present
        if not message.explanation or not message.explanation.strip():
            errors.append(ValidationError("explanation", "explanation must be non-empty"))

        # confidence, if present, must be numeric and between 0 and 1
        if message.confidence is not None:
            try:
                conf = float(message.confidence)
                if conf < 0.0 or conf > 1.0:
                    errors.append(ValidationError("confidence", "confidence must be between 0.0 and 1.0"))
            except (TypeError, ValueError):
                errors.append(ValidationError("confidence", "confidence must be a numeric value"))

        # iteration must be non-negative
        if message.iteration < 0:
            errors.append(ValidationError("iteration", "iteration must be non-negative"))

        # timestamp must be valid/serializable (basic check)
        if not message.timestamp or not isinstance(message.timestamp, str):
            errors.append(ValidationError("timestamp", "timestamp must be a valid string"))

        return errors

    @staticmethod
    def validate_or_raise(message: PXPMessage) -> None:
        """
        Validate a PXP message, raising ValueError if invalid.

        Args:
            message: The PXPMessage to validate

        Raises:
            ValueError: If validation fails, with details of all errors
        """
        errors = PXPValidator.validate(message)
        if errors:
            error_msgs = "; ".join(f"{e.field}: {e.message}" for e in errors)
            raise ValueError(f"PXP message validation failed: {error_msgs}")