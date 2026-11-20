"""
Broker: the shared front door to a model for every agent in every session.

- bounds the number of requests in flight (``max_in_flight``), so many
  sessions can run in parallel threads while the model server sees a steady
  batch (vLLM batches concurrent requests itself; the HF provider batches in
  its worker thread);
- retries unavailable and timed-out requests with exponential backoff;
- keeps request, retry, failure and latency counts.
"""

import threading
import time
from typing import Any

from ai_project.llm.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class Broker(LLMProvider):
    """
    Args:
        inner: The provider doing the work
        max_in_flight: Concurrent requests allowed
        retries: Extra attempts after an unavailable/timeout error
        backoff: Seconds before the first retry; doubles each time
    """

    def __init__(self, inner: LLMProvider, max_in_flight: int = 8, retries: int = 3,
                 backoff: float = 1.0) -> None:
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be >= 1")
        self.inner = inner
        self.name = inner.name
        self.deterministic = inner.deterministic
        self.max_in_flight = max_in_flight
        self.retries = retries
        self.backoff = backoff
        self._slots = threading.BoundedSemaphore(max_in_flight)
        self._lock = threading.Lock()
        self._stats = {"requests": 0, "retries": 0, "failures": 0, "cached": 0,
                       "latency_s": 0.0, "peak_in_flight": 0}
        self._in_flight = 0

    def describe(self) -> dict[str, Any]:
        return {**self.inner.describe(), "max_in_flight": self.max_in_flight,
                "retries": self.retries}

    def is_available(self) -> bool:
        return self.inner.is_available()

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._stats)

    def generate(self, request: LLMRequest) -> LLMResponse:
        with self._slots:
            with self._lock:
                self._stats["requests"] += 1
                self._in_flight += 1
                self._stats["peak_in_flight"] = max(self._stats["peak_in_flight"],
                                                    self._in_flight)
            start = time.perf_counter()
            try:
                return self._attempt(request)
            finally:
                with self._lock:
                    self._in_flight -= 1
                    self._stats["latency_s"] += time.perf_counter() - start

    def _attempt(self, request: LLMRequest) -> LLMResponse:
        delay = self.backoff
        for attempt in range(self.retries + 1):
            try:
                response = self.inner.generate(request)
            except (ProviderUnavailableError, ProviderTimeoutError):
                if attempt == self.retries:
                    with self._lock:
                        self._stats["failures"] += 1
                    raise
                with self._lock:
                    self._stats["retries"] += 1
                time.sleep(delay)
                delay *= 2
                continue
            if response.cached:
                with self._lock:
                    self._stats["cached"] += 1
            return response
        raise AssertionError("unreachable")
