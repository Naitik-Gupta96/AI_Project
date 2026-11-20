"""
Ollama provider (native ``/api/chat``).

The JSON schema of the request is passed as ``format``, so Ollama constrains
the output to it. Temperature 0 and a fixed seed make answers repeatable on
one machine; this is not guaranteed across hardware or model versions, so
``deterministic`` is False.

    ollama pull qwen2.5:7b-instruct
"""

from typing import Any

from ai_project.llm import prompts
from ai_project.llm.base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse
from ai_project.llm.providers.http import get_json, post_json


class OllamaProvider(LLMProvider):
    name = "ollama"
    deterministic = False

    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct",
        host: str = "http://localhost:11434",
        seed: int = 0,
        temperature: float = 0.0,
        num_ctx: int = 8192,
        timeout: float = 300.0,
        constrained: bool = True,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.seed = seed
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.constrained = constrained

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "deterministic": self.deterministic,
            "model": self.model,
            "host": self.host,
            "seed": self.seed,
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
            "constrained": self.constrained,
        }

    def is_available(self) -> bool:
        try:
            models = get_json(f"{self.host}/api/tags").get("models", [])
        except LLMProviderError:
            return False
        names = {m.get("name") for m in models} | {m.get("model") for m in models}
        return self.model in names

    def _format(self, request: LLMRequest) -> Any:
        if not self.constrained:
            return "json"
        return request.json_schema or prompts.schema(request.schema)

    def generate(self, request: LLMRequest) -> LLMResponse:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "stream": False,
            "think": False,
            "format": self._format(request),
            "options": {"temperature": self.temperature, "seed": self.seed,
                        "num_ctx": self.num_ctx},
        }
        data = post_json(f"{self.host}/api/chat", body, self.timeout)
        text = (data.get("message") or {}).get("content", "")
        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = {"prompt_tokens": int(data.get("prompt_eval_count", 0)),
                     "completion_tokens": int(data.get("eval_count", 0))}
        return LLMResponse(text=text, usage=usage,
                           meta={"total_duration_ms": data.get("total_duration", 0) / 1e6})
