"""Backend -> UI adapter: real Scheduler / counterfactual runs as UI models."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from ai_project.counterfactual.scenarios import run_deadlock_counterfactual
from ai_project.scheduler.scenarios import OPTION_A, OPTION_B, consensus_scenario
from ai_project.ui import (
    DEMO_RUNS,
    RunSummary,
    UIEvent,
    build_simulation_result,
    event_to_ui,
    run_deadlock_counterfactual_demo,
    run_pex_agents_demo,
    run_scenario,
)

APP = Path(__file__).resolve().parents[2] / "frontend" / "app.py"


def steps(events):
    return [(e.step, e.agent_id, e.tag, e.prediction) for e in events]


def test_event_to_ui_maps_history_event():
    event = {
        "iteration": 2,
        "agent_id": "critic",
        "tag": "REFUTE",
        "timestamp": "2026-10-02T00:00:00Z",
        "prediction": OPTION_A,
        "explanation": "violates C3",
        "confidence": 0.8,
        "message_id": "m2",
    }
    assert event_to_ui(event) == UIEvent(2, "critic", "REFUTE", OPTION_A, "violates C3", 0.8)


def test_event_without_confidence():
    event = {
        "iteration": 1,
        "agent_id": "a",
        "tag": "RATIFY",
        "prediction": "X",
        "explanation": "e",
    }
    assert event_to_ui(event).confidence is None


def test_scenario_c_original_and_counterfactual():
    sim = run_deadlock_counterfactual_demo()
    assert sim.original_summary == RunSummary("DEADLOCK", OPTION_A, 3, True)
    assert sim.counterfactual_summary == RunSummary("CONSENSUS", OPTION_B, 5, False)
    assert steps(sim.original_events) == [
        (1, "analyst", "RATIFY", OPTION_A),
        (2, "critic", "REFUTE", OPTION_A),
        (3, "specialist", "REFUTE", OPTION_A),
    ]
    assert steps(sim.counterfactual_events) == [
        (1, "analyst", "RATIFY", OPTION_A),
        (2, "critic", "REFUTE", OPTION_A),
        (3, "specialist", "REVISE", OPTION_B),
        (4, "critic", "RATIFY", OPTION_B),
        (5, "analyst", "RATIFY", OPTION_B),
    ]
    assert sim.divergence_step == 2
    assert sim.counterfactual_events[1].explanation != sim.original_events[1].explanation


def test_simulation_matches_branch_comparison():
    run = run_deadlock_counterfactual()
    sim = build_simulation_result(run.original_result, run.outcome)
    cmp = run.outcome.comparison
    assert sim.original_summary.status == cmp.original_status
    assert sim.original_summary.prediction == cmp.original_prediction
    assert sim.original_summary.iterations == cmp.original_iterations
    assert sim.original_summary.deadlocked == cmp.original_deadlocked
    assert sim.counterfactual_summary.status == cmp.counterfactual_status
    assert sim.counterfactual_summary.prediction == cmp.counterfactual_prediction
    assert sim.counterfactual_summary.iterations == cmp.counterfactual_iterations
    assert sim.counterfactual_summary.deadlocked == cmp.counterfactual_deadlocked
    assert sim.divergence_step == cmp.divergence_iteration
    assert sim.summary == cmp.summary


def test_run_without_counterfactual():
    sim = run_scenario(consensus_scenario())
    assert sim.original_summary == RunSummary("CONSENSUS", OPTION_B, 3, False)
    assert sim.counterfactual_summary is None
    assert sim.counterfactual_events is None
    assert sim.divergence_step is None
    assert sim.summary is None


def test_pex_agents_run_under_scheduler():
    # Person 2's agents pick options via hash(task): check structure, not values.
    sim = run_pex_agents_demo()
    events = sim.original_events
    assert events
    assert [e.step for e in events] == list(range(1, len(events) + 1))
    assert {e.agent_id for e in events} <= {"analyst", "critic", "specialist"}
    assert sim.original_summary.status in {"CONSENSUS", "DEADLOCK", "RUNNING"}
    assert sim.original_summary.iterations == len(events)


@pytest.mark.parametrize("name", list(DEMO_RUNS))
def test_demo_runs_are_json_serializable(name):
    sim = DEMO_RUNS[name]()
    json.dumps(asdict(sim))
    assert sim.original_summary.iterations == len(sim.original_events)


def test_frontend_runs_every_demo():
    app_test = pytest.importorskip("streamlit.testing.v1").AppTest
    at = app_test.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    for name in DEMO_RUNS:
        at.selectbox(key="scenario").select(name).run()
        at.button(key="demo").click().run()
        assert not at.exception, name
        text = " ".join(m.value for m in at.markdown)
        assert "#### Original Path" in text, name
    at.selectbox(key="scenario").select(next(iter(DEMO_RUNS))).run()
    at.button(key="demo").click().run()
    assert [i.value for i in at.info] == ["Diverged at Step 2"]
