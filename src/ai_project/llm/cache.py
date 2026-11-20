"""
Persistent response cache (SQLite).

The key is a hash of the provider configuration, the system prompt, the user
prompt and the output schema, so a cached answer is exactly what the same
model would be asked again. Two uses:

- reproducibility: re-running an experiment returns the recorded answers;
- the ablation: the four groups share every session up to the first
  deadlock (counterfactual agents only act after one), so those calls are
  made once and served from the cache for the other groups.

A cached response keeps its original token counts and is marked
``cached=True``; token cost is reported both with and without cache hits.
"""

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ai_project.llm.base import LLMProvider, LLMRequest, LLMResponse

_VOLATILE = {"timeout", "host", "base_url"}  # do not change the answer


class ResponseCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "key TEXT PRIMARY KEY, text TEXT NOT NULL, usage TEXT, provider TEXT)"
        )
        self._db.commit()

    def get(self, key: str) -> LLMResponse | None:
        with self._lock:
            row = self._db.execute("SELECT text, usage FROM responses WHERE key = ?",
                                   (key,)).fetchone()
        if row is None:
            return None
        return LLMResponse(text=row[0], usage=json.loads(row[1]) if row[1] else None, cached=True)

    def put(self, key: str, response: LLMResponse, provider: dict[str, Any]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO responses (key, text, usage, provider) VALUES (?, ?, ?, ?)",
                (key, response.text, json.dumps(response.usage) if response.usage else None,
                 json.dumps(provider, sort_keys=True)),
            )
            self._db.commit()

    def __len__(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM responses").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._db.close()


class CachedProvider(LLMProvider):
    def __init__(self, inner: LLMProvider, cache: ResponseCache) -> None:
        self.inner = inner
        self.cache = cache
        self.name = inner.name
        self.deterministic = inner.deterministic
        self.hits = 0
        self.misses = 0

    def describe(self) -> dict[str, Any]:
        return {**self.inner.describe(), "cache": str(self.cache.path)}

    def is_available(self) -> bool:
        return self.inner.is_available()

    def key(self, request: LLMRequest) -> str:
        provider = {k: v for k, v in self.inner.describe().items() if k not in _VOLATILE}
        payload = json.dumps({"provider": provider, "system": request.system,
                              "prompt": request.prompt,
                              "schema": request.json_schema or request.schema},
                             sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def generate(self, request: LLMRequest) -> LLMResponse:
        key = self.key(request)
        cached = self.cache.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        response = self.inner.generate(request)
        self.cache.put(key, response, self.inner.describe())
        return response
