"""
Optional local-model provider backed by an Ollama server (https://ollama.com).

Not used by the Flash Talk demo, the tests' expected outcomes, or the
reported pilot results; those use ``MockLLMProvider``. It exists so the same
agents can be run against a real model:

    ollama pull qwen3:4b
    python examples/flash_talk_demo.py --provider ollama --model qwen3:4b

Requests use temperature 0 and a fixed seed, which makes Ollama's output
repeatable on one machine, but this is not guaranteed across model versions
or hardware, so ``deterministic`` is False.
"""

import json
import urllib.error
import urllib.request
from typing import Any

from ai_project.llm.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class OllamaProvider(LLMProvider):
    """Sends the rendered prompt to a local Ollama model and returns its JSON reply."""

    name = "ollama"
    deterministic = False

    def __init__(
        self,
        model: str = "qwen3:4b",
        host: str = "http://localhost:11434",
        seed: int = 0,
        temperature: float = 0.0,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.seed = seed
        self.temperature = temperature
        self.timeout = timeout

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "deterministic": self.deterministic,
            "model": self.model,
            "host": self.host,
            "seed": self.seed,
            "temperature": self.temperature,
        }

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=3) as resp:
                models = json.load(resp).get("models", [])
        except (OSError, ValueError):
            return False
        names = {m.get("name") for m in models} | {m.get("model") for m in models}
        return self.model in names

    def generate(self, request: LLMRequest) -> LLMResponse:
        body = json.dumps(
            {
                "model": self.model,
                "prompt": request.prompt,
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"temperature": self.temperature, "seed": self.seed},
            }
        ).encode()
        http_request = urllib.request.Request(
            f"{self.host}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as resp:
                data = json.load(resp)
        except TimeoutError as exc:
            raise ProviderTimeoutError(f"Ollama did not answer within {self.timeout}s") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ProviderUnavailableError(f"Cannot reach Ollama at {self.host}: {exc}") from exc

        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = {
                "prompt_tokens": int(data.get("prompt_eval_count", 0)),
                "completion_tokens": int(data.get("eval_count", 0)),
            }
        return LLMResponse(text=data.get("response", ""), usage=usage)
