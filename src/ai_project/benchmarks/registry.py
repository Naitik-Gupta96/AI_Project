"""
Benchmark lookup by name, used by the CLI, the server and the experiment runner.

Data lives under ``$BB_DATA_DIR`` (default ``data``), one directory per benchmark.
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ai_project.benchmarks.base import Benchmark


def data_dir(name: str) -> Path:
    return Path(os.environ.get("BB_DATA_DIR", "data")) / name


def _synthetic(**kw: Any) -> Benchmark:
    from ai_project.benchmarks.synthetic import SyntheticBenchmark
    return SyntheticBenchmark(**kw)


def _mscore(**kw: Any) -> Benchmark:
    from ai_project.benchmarks.mscore import MSCoReBenchmark
    return MSCoReBenchmark(**{"data_dir": data_dir("mscore"), **kw})


def _kramabench(**kw: Any) -> Benchmark:
    from ai_project.benchmarks.kramabench import KramaBenchmark
    return KramaBenchmark(**{"data_dir": data_dir("kramabench"), **kw})


def _medagentbench(**kw: Any) -> Benchmark:
    from ai_project.benchmarks.medagentbench import MedAgentBenchmark
    return MedAgentBenchmark(**{"data_dir": data_dir("medagentbench"), **kw})


_FACTORIES: dict[str, Callable[..., Benchmark]] = {
    "synthetic": _synthetic,
    "mscore": _mscore,
    "kramabench": _kramabench,
    "medagentbench": _medagentbench,
}


def register(name: str, factory: Callable[..., Benchmark]) -> None:
    _FACTORIES[name] = factory


def names() -> list[str]:
    return list(_FACTORIES)


def get_benchmark(name: str, **kwargs: Any) -> Benchmark:
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise KeyError(f"Unknown benchmark '{name}'. Known: {names()}") from None
    return factory(**kwargs)


def tool_factory(benchmark: Benchmark) -> Callable[..., dict[str, Any]] | None:
    """``build_team``'s tool factory for benchmarks whose agents use tools, else None."""
    return getattr(benchmark, "tools", None)
