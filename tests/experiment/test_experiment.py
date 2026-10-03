"""The pilot experiment: real runs, reproducible records, honest analysis."""

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_project.experiment import (
    SCHEMA,
    conditions,
    load_results,
    rerun_trial,
    run_pilot,
    save_results,
    summarize,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def doc():
    return run_pilot(n_tasks=25, seed=5)


def strip_volatile(d):
    d = json.loads(json.dumps(d))
    for key in ("generated_at", "git_commit"):
        d.pop(key)
    for t in d["trials"]:
        t["metrics"].pop("runtime_ms")
    return d


def test_eight_conditions():
    assert len(conditions()) == 8
    assert conditions()[0] == () and conditions()[-1] == ("analyst", "critic", "specialist")


def test_pilot_is_reproducible(doc):
    assert strip_volatile(run_pilot(n_tasks=25, seed=5)) == strip_volatile(doc)


def test_trial_records_are_complete(doc):
    assert doc["schema"] == SCHEMA
    assert doc["mode"].startswith("END-TO-END PILOT")
    assert doc["provider"]["deterministic"] is True
    assert len(doc["trials"]) == 25 * 8
    for t in doc["trials"]:
        assert t["seed"] == 5 and t["task_id"] and t["trial_id"]
        assert t["original"]["trace"]
        assert t["metrics"]["tokens"] is None  # the mock reports none; never estimated
        if t["metrics"]["original_deadlock"]:
            assert t["counterfactual"] is not None
        else:
            assert t["counterfactual"] is None and t["metrics"]["recovered"] is None


def test_original_run_does_not_depend_on_condition(doc):
    by_task = {}
    for t in doc["trials"]:
        by_task.setdefault(t["task_id"], set()).add(json.dumps(t["original"]))
    assert all(len(v) == 1 for v in by_task.values())


def test_recovery_is_monotone_in_capable_agents(doc):
    recovered = {(t["task_id"], tuple(t["condition"]["cf_agents"])): t["metrics"]["recovered"]
                 for t in doc["trials"]}
    for (task_id, small), value in recovered.items():
        if not value:
            continue
        for big in conditions():
            if set(small) <= set(big):
                assert recovered[(task_id, big)], (task_id, small, big)


def test_summary_counts(doc):
    s = summarize(doc)
    fractions = [r["cf_fraction"] for r in s["by_fraction"]]
    assert fractions == sorted(fractions) and len(fractions) == 4
    none = next(r for r in s["by_condition"] if r["cf_agents"] == "none")
    assert none["recovered"] == 0
    assert sum(r["trials"] for r in s["by_condition"]) == len(doc["trials"])
    deadlock_rates = {r["deadlock_rate"] for r in s["by_fraction"]}
    assert len(deadlock_rates) == 1  # condition-independent by design


def test_wilson_interval():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3) and high == pytest.approx(0.7634, abs=1e-3)
    assert wilson_interval(10, 10)[1] == 1.0


def test_rerun_trial_reproduces_record(doc):
    for t in doc["trials"][::17]:
        run = rerun_trial(doc, t)
        assert [[e["iteration"], e["agent_id"], e["tag"], e["prediction"]]
                for e in run.original.history] == t["original"]["trace"]
        assert run.final.status == t["metrics"]["final_status"]


def test_old_synthetic_format_is_refused(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps([{"cf_fraction": 0.5, "trial": 0}]))
    with pytest.raises(ValueError):
        load_results(path)


def test_cli_scripts(tmp_path):
    out = tmp_path / "pilot_mock_seed1_n3.json"
    run = subprocess.run([sys.executable, str(ROOT / "experiments/run_experiment.py"),
                          "--tasks", "3", "--seed", "1", "--out", str(out)],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    analyze = subprocess.run([sys.executable, str(ROOT / "experiments/analyze_results.py"),
                              str(out)], capture_output=True, text=True, timeout=60)
    assert analyze.returncode == 0, analyze.stderr
    assert "not a validated research finding" in analyze.stdout
    assert (tmp_path / "pilot_mock_seed1_n3_summary.csv").exists()
    assert save_results(load_results(out), tmp_path / "copy.json").exists()


def test_subsets_cover_all_combinations():
    roles = ("analyst", "critic", "specialist")
    expected = {c for k in range(4) for c in itertools.combinations(roles, k)}
    assert set(conditions()) == expected
