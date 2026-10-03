"""Backend -> UI adapter and the Streamlit app, on real runs."""

import json
from pathlib import Path

import pytest

from ai_project.experiment import load_results, run_pilot, save_results
from ai_project.ui import experiment_view, find_results, flash_talk_demo, trial_demo_view

APP = Path(__file__).resolve().parents[2] / "frontend" / "app.py"


def test_flash_talk_view():
    demo = flash_talk_demo()
    original = [(e.kind, e.step, e.agent_id, e.tag, e.prediction) for e in demo.original.events]
    assert original == [
        ("message", 1, "analyst", "RATIFY", "Option A"),
        ("message", 2, "critic", "REFUTE", "Option A"),
        ("message", 3, "specialist", "REFUTE", "Option A"),
        ("status", 3, None, "DEADLOCK", "Option A"),
    ]
    assert all(e.timestamp and e.rule for e in demo.original.messages)
    assert demo.original.mode == "DETERMINISTIC MOCK"

    cf = demo.shown_branch
    assert cf.recovered and cf.branch_point == 2 and cf.divergence_step == 2
    assert cf.original_event.alternative is None
    assert cf.revised_event.alternative == "Option B"
    assert [e.kind for e in cf.branch.events] == [
        "inherited", "intervention", "message", "message", "message", "status"]
    assert cf.branch.outcome.status == "CONSENSUS"
    assert demo.final.status == "CONSENSUS"
    assert demo.original_preserved
    json.dumps(demo.to_dict())


def test_flash_talk_without_cf_agents():
    demo = flash_talk_demo(())
    assert demo.deadlocked and demo.branches == [] and demo.final.status == "DEADLOCK"


def test_unrecovered_branch_is_still_shown():
    demo = flash_talk_demo(("analyst", "critic", "specialist"))
    assert demo.reflections[0].agent_id == "specialist"
    assert demo.shown_branch is demo.recovering_branch


@pytest.fixture
def results_dir(tmp_path):
    save_results(run_pilot(n_tasks=6, seed=3), tmp_path / "pilot_mock_seed3_n6.json")
    return tmp_path


def test_experiment_view_and_trial_replay(results_dir):
    (path,) = find_results(results_dir)
    ev = experiment_view(path)
    assert ev.n_trials == 48 and ev.mode.startswith("END-TO-END PILOT")
    assert len(ev.by_fraction) == 4 and len(ev.by_condition) == 8
    doc = load_results(path)
    for trial in doc["trials"][::7]:
        view, reproduced = trial_demo_view(doc, trial)
        assert reproduced
        assert view.original.outcome.status == trial["original"]["status"]


def test_app_renders_all_tabs(results_dir, monkeypatch):
    app_test = pytest.importorskip("streamlit.testing.v1").AppTest
    monkeypatch.setenv("AI_PROJECT_RESULTS_DIR", str(results_dir))
    at = app_test.from_file(str(APP), default_timeout=60).run()
    assert not at.exception

    at.button(key="talk_run").click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    for expected in ("DEADLOCK", "CONSENSUS", "counterfactual revision", "REVISED IN HINDSIGHT"):
        assert expected in text, expected

    at.radio(key="explore_source").set_value("Recorded pilot trial").run()
    assert not at.exception
    assert not at.error
    assert any("matches the recorded trace" in c.value for c in at.caption)

    assert any("deterministic pilot" in w.value for w in at.warning)
