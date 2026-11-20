"""
Provider interface: the single path every agent decision goes through.

An agent renders a prompt from its ``AgentContext`` and sends both, with the
name of the JSON schema the answer must follow, to ``LLMProvider.generate``.
A model-backed provider reads the prompt (and constrains its output to the
schema where it can); the deterministic mock reads the structured context.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_project.agents.models import AgentContext


@dataclass(frozen=True)
class LLMRequest:
    """
    Attributes:
        prompt: Rendered user prompt
        context: Structured context the prompt was rendered from
        schema: Name of the output JSON schema ("pxp_message" or "reflection")
        system: System prompt (persona and lessons)
        phase: "live" or "sandbox", for token accounting
    """

    prompt: str
    context: "AgentContext"
    schema: str = "pxp_message"
    system: str = ""
    phase: str = "live"


@dataclass(frozen=True)
class LLMResponse:
    """
    Attributes:
        text: Raw text (expected to contain one JSON object)
        usage: {"prompt_tokens", "completion_tokens"} as reported by the provider, or None
        cached: True if served from the response cache
    """

    text: str
    usage: dict[str, int] | None = None
    cached: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    #: Short identifier recorded with every message and result
    name: str = "provider"
    #: True if the same request always yields the same response
    deterministic: bool = False

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Produce a response for one request."""

    def is_available(self) -> bool:
        return True

    def describe(self) -> dict[str, Any]:
        """Serializable configuration (recorded for reproducibility)."""
        return {"name": self.name, "deterministic": self.deterministic}


class LLMProviderError(Exception):
    """Base exception for provider errors."""


class ProviderUnavailableError(LLMProviderError):
    """The provider cannot be reached."""


class ProviderTimeoutError(LLMProviderError):
    """A request timed out."""
