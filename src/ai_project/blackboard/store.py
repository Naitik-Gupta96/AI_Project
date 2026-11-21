"""
Persistence for Blackboard sessions.

A store keeps each session's event log. The Blackboard appends every event
before it notifies anyone, so whatever a subscriber has seen is on disk.

``MemoryStore``  in-process; the default, and what counterfactual sandboxes use
``JsonStore``    one directory per session: ``events.jsonl`` (append-only, one
                 event per line, flushed and fsynced per event) and
                 ``meta.json`` (written to a temporary file, then renamed).
                 A torn last line from a crash is ignored on load, so a
                 session always reloads to its last complete event.
``RedisStore``   one Redis stream per session (``pip install redis``)
"""

import json
import os
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from ai_project.blackboard.exceptions import StoreError
from ai_project.blackboard.models import BoardEvent


class BoardStore(Protocol):
    def append(self, session_id: str, event: BoardEvent) -> None: ...

    def load(self, session_id: str) -> list[BoardEvent]: ...

    def sessions(self) -> list[str]: ...

    def write_meta(self, session_id: str, meta: dict[str, Any]) -> None: ...

    def read_meta(self, session_id: str) -> dict[str, Any]: ...


class MemoryStore:
    def __init__(self) -> None:
        self._events: dict[str, list[BoardEvent]] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def append(self, session_id: str, event: BoardEvent) -> None:
        with self._lock:
            self._events.setdefault(session_id, []).append(event)

    def load(self, session_id: str) -> list[BoardEvent]:
        with self._lock:
            if session_id not in self._events:
                raise StoreError(f"Unknown session '{session_id}'")
            return list(self._events[session_id])

    def sessions(self) -> list[str]:
        with self._lock:
            return list(self._events)

    def write_meta(self, session_id: str, meta: dict[str, Any]) -> None:
        with self._lock:
            self._meta[session_id] = json.loads(json.dumps(meta))

    def read_meta(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._meta.get(session_id, {}))


class JsonStore:
    """
    Args:
        root: Directory holding one sub-directory per session
        fsync: Force each event to disk (turn off only for throwaway runs)
    """

    EVENTS = "events.jsonl"
    META = "meta.json"

    def __init__(self, root: str | Path, fsync: bool = True) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.fsync = fsync
        self._lock = threading.Lock()

    def _dir(self, session_id: str) -> Path:
        unsafe = any(c in session_id for c in '/\\:*?"<>|') if session_id else True
        if unsafe or session_id in {".", ".."}:
            raise StoreError(f"Invalid session id '{session_id}'")
        return self.root / session_id

    def append(self, session_id: str, event: BoardEvent) -> None:
        directory = self._dir(session_id)
        line = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            directory.mkdir(parents=True, exist_ok=True)
            with open(directory / self.EVENTS, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                if self.fsync:
                    os.fsync(f.fileno())

    def load(self, session_id: str) -> list[BoardEvent]:
        path = self._dir(session_id) / self.EVENTS
        if not path.is_file():
            raise StoreError(f"Unknown session '{session_id}'")
        events = []
        with self._lock, open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                events.append(BoardEvent.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError) as exc:
                if i == len(lines) - 1:  # torn final write
                    break
                raise StoreError(f"Corrupt event on line {i + 1} of {path}: {exc}") from exc
        return events

    def sessions(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / self.EVENTS).is_file())

    def discard(self, session_id: str) -> None:
        """Delete a session's log and metadata, so the id can be reused for a new session."""
        directory = self._dir(session_id)
        with self._lock:
            for name in (self.EVENTS, self.META, f".{self.META}.tmp"):
                (directory / name).unlink(missing_ok=True)

    def write_meta(self, session_id: str, meta: dict[str, Any]) -> None:
        directory = self._dir(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / f".{self.META}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            f.flush()
            if self.fsync:
                os.fsync(f.fileno())
        os.replace(tmp, directory / self.META)

    def read_meta(self, session_id: str) -> dict[str, Any]:
        path = self._dir(session_id) / self.META
        if not path.is_file():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)


class RedisStore:
    """
    Args:
        url: Redis URL, e.g. ``redis://localhost:6379/0``
        prefix: Key prefix; session ``s`` lives in stream ``<prefix>:<s>``
        client: An existing redis client (overrides ``url``)
    """

    def __init__(self, url: str = "redis://localhost:6379/0", prefix: str = "blackboard",
                 client: Any = None) -> None:
        if client is None:
            try:
                import redis
            except ImportError as exc:
                raise StoreError("RedisStore needs the 'redis' package: pip install redis") from exc
            client = redis.Redis.from_url(url, decode_responses=True)
        self.client = client
        self.prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}:{session_id}"

    def append(self, session_id: str, event: BoardEvent) -> None:
        self.client.xadd(self._key(session_id), {"event": json.dumps(event.to_dict())})

    def load(self, session_id: str) -> list[BoardEvent]:
        entries = self.client.xrange(self._key(session_id))
        if not entries:
            raise StoreError(f"Unknown session '{session_id}'")
        return [BoardEvent.from_dict(json.loads(fields["event"])) for _, fields in entries]

    def sessions(self) -> list[str]:
        keys: Iterable[str] = self.client.scan_iter(match=f"{self.prefix}:*")
        start = len(self.prefix) + 1
        return sorted(k[start:] for k in keys if not k.endswith(":meta"))

    def write_meta(self, session_id: str, meta: dict[str, Any]) -> None:
        self.client.set(f"{self._key(session_id)}:meta", json.dumps(meta))

    def read_meta(self, session_id: str) -> dict[str, Any]:
        raw = self.client.get(f"{self._key(session_id)}:meta")
        return json.loads(raw) if raw else {}
