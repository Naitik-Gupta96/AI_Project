"""Benchmark lookup by name, used by the CLI, the server and the experiment runner."""

from collections.abc import Callable
from typing import Any

from ai_project.benchmarks.base import Benchmark
from ai_project.benchmarks.synthetic import SyntheticBenchmark

_FACTORIES: dict[str, Callable[..., Benchmark]] = {
    "synthetic": SyntheticBenchmark,
}


def register(name: str, factory: Callable[..., Benchmark]) -> None:
    _FACTORIES[name] = factory


def names() -> list[str]:
    return list(_FACTORIES)


def get_benchmark(name: str, **kwargs: Any) -> Benchmark:
    try:
        return _FACTORIES[name](**kwargs)
    except KeyError:
        raise KeyError(f"Unknown benchmark '{name}'. Known: {names()}") from None
