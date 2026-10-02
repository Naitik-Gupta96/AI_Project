from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The input prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Raw text response from the LLM
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available/configured."""
        pass


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class ProviderUnavailableError(LLMProviderError):
    """Raised when provider is not available."""
    pass


class ProviderTimeoutError(LLMProviderError):
    """Raised when provider request times out."""
    pass