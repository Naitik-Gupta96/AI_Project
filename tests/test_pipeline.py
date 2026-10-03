"""End-to-end: task -> agents -> Blackboard -> Scheduler -> deadlock -> counterfactual -> outcome."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_project.pipeline import RunConfig, run_task
from ai_project.tasks import flash_talk_task, generate_tasks

ROOT = Path(__file__).resolve().parents[1]
ALL = ("analyst", "critic", "specialist")


def test_flash_talk_regression():
    run = run_task(flash_talk_task(), ("critic",))
    assert [(e["agent_id"], e["tag"], e["prediction"]) for e in run.original.history] == [
        ("analyst", "RATIFY", "Option A"),
        ("critic", "REFUTE", "Option A"),
        ("specialist", "REFUTE", "Option A"),
    ]
    assert run.original.status == "DEADLOCK"
    assert run.original.deadlock.rule == "repeated_disagreement"
    assert run.recovered
    assert (run.final.status, run.final.final_prediction, run.final.iterations) == (
        "CONSENSUS", "Option B", 5)
    assert run.board.get_state().status.value == "DEADLOCK"  # original board untouched
    assert run.token_usage() is None
    assert run.provider_calls() == 3 + 1 + 3  # original + reflection + replay
    assert run.provider == {"name": "deterministic-mock", "deterministic": True}


def test_config_is_recorded_canonically():
    config = RunConfig(cf_agents=("specialist", "analyst"))
    assert config.cf_agents == ("analyst", "specialist")
    assert config.to_dict()["cf_fraction"] == pytest.approx(2 / 3, abs=1e-4)
    with pytest.raises(ValueError):
        RunConfig(cf_agents=("nobody",))


def test_every_consensus_is_on_a_feasible_option():
    for task in generate_tasks(60, seed=11):
        run = run_task(task, ALL)
        if run.final.consensus_reached:
            assert run.final.final_prediction in task.feasible_options(), task.task_id
        if run.original.deadlocked and task.best_feasible() is not None:
            assert run.recovered, task.task_id  # all three agents capable: always recovers here


@pytest.mark.parametrize("script", ["examples/flash_talk_demo.py"])
def test_demo_output_identical_across_processes(script):
    outputs = set()
    for seed in ("1", "2", "3"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        proc = subprocess.run([sys.executable, str(ROOT / script)], capture_output=True,
                              text=True, env=env, timeout=60)
        assert proc.returncode == 0, proc.stderr
        outputs.add(proc.stdout)
    assert len(outputs) == 1
    assert "CONSENSUS on Option B after 5 steps" in outputs.pop()
