"""
Build a provider from a short spec string (CLI flags, experiment configs).

    mock                       deterministic rules (tests, offline demo)
    ollama:<model>             Ollama native API ($OLLAMA_HOST, default localhost:11434)
    vllm:<model>               vLLM OpenAI server ($VLLM_BASE_URL, default localhost:8000/v1)
    openai:<model>@<base_url>  any OpenAI-compatible server ($OPENAI_API_KEY if set)
    hf:<model>                 in-process transformers, dynamic batching

Model providers are wrapped in a ``Broker`` (bounded concurrency, retries)
and, if ``cache`` is given, a ``CachedProvider``.
"""

import os
from pathlib import Path

from ai_project.llm.base import LLMProvider
from ai_project.llm.broker import Broker
from ai_project.llm.cache import CachedProvider, ResponseCache


def make_provider(
    spec: str,
    cache: str | Path | None = None,
    max_in_flight: int = 8,
    temperature: float = 0.0,
    seed: int = 0,
) -> LLMProvider:
    kind, _, rest = spec.partition(":")
    kind = kind.strip().lower()
    if kind == "mock":
        from ai_project.llm.providers.mock import MockLLMProvider
        return MockLLMProvider()

    provider: LLMProvider
    if kind == "ollama":
        from ai_project.llm.providers.ollama import OllamaProvider
        provider = OllamaProvider(
            model=rest or "qwen2.5:7b-instruct",
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            temperature=temperature, seed=seed,
        )
    elif kind in ("vllm", "openai"):
        from ai_project.llm.providers.openai_compat import OpenAICompatibleProvider
        model, _, url = rest.partition("@")
        default_url = (os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
                       if kind == "vllm" else "https://api.openai.com/v1")
        provider = OpenAICompatibleProvider(
            model=model or "Qwen/Qwen2.5-7B-Instruct",
            base_url=url or default_url,
            api_key=os.environ.get("OPENAI_API_KEY") if kind == "openai" else None,
            temperature=temperature, seed=seed, name=kind,
        )
    elif kind == "hf":
        from ai_project.llm.providers.hf import HFTransformersProvider
        provider = HFTransformersProvider(model_name=rest or "Qwen/Qwen2.5-7B-Instruct",
                                          batch_size=max_in_flight)
    else:
        raise ValueError(f"Unknown provider spec '{spec}'. Use mock, ollama:<model>, "
                         f"vllm:<model>, openai:<model>@<url> or hf:<model>.")

    if cache is not None:
        provider = CachedProvider(provider, ResponseCache(cache))
    return Broker(provider, max_in_flight=max_in_flight)
