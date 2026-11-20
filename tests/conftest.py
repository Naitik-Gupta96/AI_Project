from collections.abc import Callable, Sequence
from typing import Any

import pytest

from ai_project.agents import Agent, build_team
from ai_project.benchmarks import SyntheticBenchmark, Task, architecture_task
from ai_project.blackboard import Blackboard
from ai_project.llm.providers.mock import MockLLMProvider


@pytest.fixture
def options_board() -> Callable[..., Blackboard]:
    def make(options: Sequence[str] = ("A", "B", "C"), agents: Sequence[str] = ("a1", "a2", "a3"),
             **kw: Any) -> Blackboard:
        board = Blackboard(**kw)
        board.initialize_task("Pick one", {"options": list(options)}, agents=agents)
        return board

    return make


@pytest.fixture
def demo_task() -> Task:
    return architecture_task()


@pytest.fixture
def mock_team() -> Callable[[Task], list[Agent]]:
    def make(task: Task) -> list[Agent]:
        return build_team(task, MockLLMProvider())

    return make


@pytest.fixture
def synthetic() -> SyntheticBenchmark:
    return SyntheticBenchmark()
