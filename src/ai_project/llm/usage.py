"""Thread-safe token and call accounting, split by phase (live board vs counterfactual sandbox)."""

import threading
from typing import Any

PHASES = ("live", "sandbox")


class UsageMeter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data = {p: {"calls": 0, "cached_calls": 0, "prompt_tokens": 0,
                          "completion_tokens": 0, "reported": False} for p in PHASES}

    def add(self, phase: str, usage: dict[str, int] | None, cached: bool = False) -> None:
        if phase not in self._data:
            raise ValueError(f"Unknown phase '{phase}'")
        with self._lock:
            row = self._data[phase]
            row["calls"] += 1
            row["cached_calls"] += int(cached)
            if usage:
                row["reported"] = True
                row["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
                row["completion_tokens"] += int(usage.get("completion_tokens", 0))

    def merge(self, other: "UsageMeter") -> None:
        snapshot = other.to_dict()
        with self._lock:
            for phase in PHASES:
                for key in ("calls", "cached_calls", "prompt_tokens", "completion_tokens"):
                    self._data[phase][key] += snapshot[phase][key]
                self._data[phase]["reported"] |= snapshot[phase]["reported"]

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            out: dict[str, Any] = {p: dict(row) for p, row in self._data.items()}
        out["total"] = {
            key: sum(out[p][key] for p in PHASES)
            for key in ("calls", "cached_calls", "prompt_tokens", "completion_tokens")
        }
        out["total"]["reported"] = any(out[p]["reported"] for p in PHASES)
        return out
