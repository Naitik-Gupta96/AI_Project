"""
Provider interface: the single path every agent decision goes through.

An agent renders a prompt from its ``AgentContext`` and sends both to
``LLMProvider.generate``. A model-backed provider reads the prompt; the
deterministic mock reads the structured context the prompt was rendered
from. Both return the same JSON schema, which the agent parses.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_project.agents.models import AgentContext


@dataclass(frozen=True)
class LLMRequest:
    """A rendered prompt plus the structured context it was rendered from."""

    prompt: str
    context: "AgentContext"


@dataclass(frozen=True)
class LLMResponse:
    """
    Raw provider output.

    Attributes:
        text: Raw text (expected to contain the decision JSON)
        usage: Token counts reported by the provider
            ({"prompt_tokens", "completion_tokens"}), or None if it reports none
    """

    text: str
    usage: dict[str, int] | None = None


class LLMProvider(ABC):
    """Base class for decision providers."""

    #: Short identifier recorded with every message and experiment result
    name: str = "provider"
    #: True if the same request always yields the same response
    deterministic: bool = False

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Produce a response for one decision request."""

    def is_available(self) -> bool:
        """Whether the provider can currently serve requests."""
        return True

    def describe(self) -> dict[str, Any]:
        """Serializable provider configuration (recorded for reproducibility)."""
        return {"name": self.name, "deterministic": self.deterministic}


class LLMProviderError(Exception):
    """Base exception for provider errors."""


class ProviderUnavailableError(LLMProviderError):
    """Raised when the provider cannot be reached."""


class ProviderTimeoutError(LLMProviderError):
    """Raised when a provider request times out."""
