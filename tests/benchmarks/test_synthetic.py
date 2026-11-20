import pytest

from ai_project.benchmarks import SyntheticBenchmark, Task, architecture_task
from ai_project.benchmarks.synthetic import best_feasible, feasible_options


def test_generation_is_deterministic():
    a = [t.to_dict() for t in SyntheticBenchmark().load(10, seed=1)]
    b = [t.to_dict() for t in SyntheticBenchmark().load(10, seed=1)]
    c = [t.to_dict() for t in SyntheticBenchmark().load(10, seed=2)]
    assert a == b and a != c


def test_reference_is_the_best_feasible_option():
    for task in SyntheticBenchmark().load(50, seed=7):
        assert task.reference == best_feasible(task)
        if task.reference is not None:
            assert task.reference in feasible_options(task)


def test_architecture_task():
    task = architecture_task()
    assert feasible_options(task) == ("Option B",)
    assert task.reference == "Option B"


def test_scoring():
    bench = SyntheticBenchmark()
    task = architecture_task()
    assert bench.score(task, "Option B").correct
    assert not bench.score(task, "Option A").correct
    assert not bench.score(task, None).correct


def test_task_round_trip():
    task = SyntheticBenchmark().load(1, seed=0)[0]
    assert Task.from_dict(task.to_dict()) == task


def test_option_count_is_validated():
    with pytest.raises(ValueError):
        SyntheticBenchmark(n_options=1)
