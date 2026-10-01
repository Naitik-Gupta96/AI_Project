"""End-to-end scenarios A (consensus), B (deadlock) and C (deadlock -> counterfactual consensus)."""

import json
import subprocess
import sys
from pathlib import Path

from ai_project.blackboard import BlackboardStatus
from ai_project.counterfactual.scenarios import run_deadlock_counterfactual
from ai_project.scheduler.scenarios import OPTION_A, OPTION_B, consensus_scenario, deadlock_scenario

DEMO = Path(__file__).resolve().parents[2] / "examples" / "scheduler_demo.py"


def actions(result):
    return [(t.agent, t.event, t.prediction) for t in result.trace if t.kind == "agent_action"]


def test_scenario_a_consensus():
    board, _, result = consensus_scenario().run()
    assert board.get_state().status == BlackboardStatus.CONSENSUS
    assert actions(result) == [
        ("analyst", "RATIFY", OPTION_B),
        ("critic", "RATIFY", OPTION_B),
        ("specialist", "RATIFY", OPTION_B),
    ]


def test_scenario_b_deadlock():
    board, _, result = deadlock_scenario().run()
    assert board.get_state().status == BlackboardStatus.DEADLOCK
    assert actions(result) == [
        ("analyst", "RATIFY", OPTION_A),
        ("critic", "REFUTE", OPTION_A),
        ("specialist", "REFUTE", OPTION_A),
    ]


def test_scenario_c_counterfactual_resolves_deadlock():
    run = run_deadlock_counterfactual()
    assert run.original_result.deadlocked
    assert run.outcome.result.consensus_reached
    assert actions(run.outcome.result) == [
        ("specialist", "REVISE", OPTION_B),
        ("critic", "RATIFY", OPTION_B),
        ("analyst", "RATIFY", OPTION_B),
    ]
    # The original run is preserved
    assert run.original_board.get_state().status == BlackboardStatus.DEADLOCK
    assert [e.tag for e in run.original_board.get_history()] == ["RATIFY", "REFUTE", "REFUTE"]
    json.dumps(run.to_dict())


def test_demo_script_runs():
    completed = subprocess.run(
        [sys.executable, str(DEMO)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    out = completed.stdout
    assert "=== ORIGINAL RUN ===" in out
    assert "=== COUNTERFACTUAL ===" in out
    assert "=== COMPARISON ===" in out
    assert "Original:       DEADLOCK" in out
    assert "Counterfactual: CONSENSUS" in out


def test_demo_script_json_export(tmp_path):
    out_file = tmp_path / "run.json"
    completed = subprocess.run(
        [sys.executable, str(DEMO), "--json", str(out_file)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    data = json.loads(out_file.read_text())
    assert data["original"]["status"] == "DEADLOCK"
    assert data["counterfactual"]["comparison"]["counterfactual_status"] == "CONSENSUS"
