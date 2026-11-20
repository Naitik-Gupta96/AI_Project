"""
OpenAI-compatible chat provider: vLLM's server, Ollama's ``/v1``, or any other
server that speaks ``/v1/chat/completions``.

The answer is constrained to the request's JSON schema with
``response_format = {"type": "json_schema", ...}``, which vLLM (guided decoding)
and recent Ollama versions honour. Token counts come from the server's
``usage`` field.

Start vLLM on the GPU machine with, for example:

    vllm serve Qwen/Qwen2.5-7B-Instruct --max-model-len 8192 --port 8000

and use ``base_url="http://127.0.0.1:8000/v1"``.
"""

from typing import Any

from ai_project.llm import prompts
from ai_project.llm.base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse
from ai_project.llm.providers.http import get_json, post_json


class OpenAICompatibleProvider(LLMProvider):
    """
    Args:
        model: Model name as the server knows it
        base_url: Server root including ``/v1``
        api_key: Bearer token, if the server needs one
        temperature, seed, max_tokens: Sampling settings (recorded with results)
        timeout: Seconds per request
        constrained: Send the JSON schema as ``response_format``
        name: Label recorded with results (e.g. "vllm" or "ollama-openai")
    """

    deterministic = False

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:8000/v1",
        api_key: str | None = None,
        temperature: float = 0.0,
        seed: int | None = 0,
        max_tokens: int = 700,
        timeout: float = 180.0,
        constrained: bool = True,
        name: str = "vllm",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.constrained = constrained
        self.name = name

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "deterministic": self.deterministic,
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "seed": self.seed,
            "max_tokens": self.max_tokens,
            "constrained": self.constrained,
        }

    def is_available(self) -> bool:
        try:
            models = get_json(f"{self.base_url}/models").get("data", [])
        except LLMProviderError:
            return False
        return any(m.get("id") == self.model for m in models)

    def generate(self, request: LLMRequest) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            body["seed"] = self.seed
        if self.constrained:
            schema = request.json_schema or prompts.schema(request.schema)
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": request.schema, "schema": schema},
            }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        data = post_json(f"{self.base_url}/chat/completions", body, self.timeout, headers)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Unexpected response shape: {str(data)[:300]}") from exc
        usage = data.get("usage") or None
        if usage:
            usage = {"prompt_tokens": int(usage.get("prompt_tokens", 0)),
                     "completion_tokens": int(usage.get("completion_tokens", 0))}
        return LLMResponse(text=text, usage=usage,
                           meta={"finish_reason": data["choices"][0].get("finish_reason")})
