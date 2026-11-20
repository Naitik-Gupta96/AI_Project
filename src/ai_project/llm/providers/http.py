"""Minimal JSON-over-HTTP client (standard library only) shared by the model providers."""

import json
import urllib.error
import urllib.request
from typing import Any

from ai_project.llm.base import LLMProviderError, ProviderTimeoutError, ProviderUnavailableError


def post_json(url: str, body: dict[str, Any], timeout: float,
              headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        if exc.code in (429, 502, 503, 504):
            raise ProviderUnavailableError(f"HTTP {exc.code} from {url}: {detail}") from exc
        raise LLMProviderError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except TimeoutError as exc:
        raise ProviderTimeoutError(f"No answer from {url} within {timeout}s") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ProviderUnavailableError(f"Cannot reach {url}: {exc}") from exc


def get_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ProviderUnavailableError(f"Cannot reach {url}: {exc}") from exc
