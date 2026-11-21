import json
from pathlib import Path

import pytest

from ai_project.experiments import (
    ExperimentConfig,
    ExperimentRunner,
    capable_agents,
    load_trials,
    write_report,
)
from ai_project.experiments.analysis import bootstrap_mean, mcnemar_exact, wilson

CONFIGS = Path(__file__).resolve().parents[2] / "experiments" / "configs"


def config(n=12, fractions=(0.0, 1 / 3, 2 / 3, 1.0)):
    from ai_project.experiments.runner import BenchmarkSpec
    return ExperimentConfig(name="t", provider="mock", benchmarks=(BenchmarkSpec("synthetic", n),),
                            fractions=fractions, workers=4, cache=False, keep_sessions=False)


def test_capable_agents_rotate_and_scale():
    roles = ["a", "b", "c"]
    assert capable_agents(roles, 0.0, 5) == ()
    assert capable_agents(roles, 1.0, 5) == ("a", "b", "c")
    singles = [capable_agents(roles, 1 / 3, i) for i in range(3)]
    assert singles == [("a",), ("b",), ("c",)]
    pairs = [capable_agents(roles, 2 / 3, i) for i in range(3)]
    assert pairs == [("a", "b"), ("b", "c"), ("a", "c")]


def test_every_shipped_config_parses():
    for path in CONFIGS.glob("*.toml"):
        cfg = ExperimentConfig.load(path)
        assert cfg.benchmarks and cfg.session_config().scheduler.max_messages > 0


def test_spec_ablation_config_matches_the_spec():
    cfg = ExperimentConfig.load(CONFIGS / "ablation.toml")
    assert [round(f, 2) for f in cfg.fractions] == [0.0, 0.33, 0.67, 1.0]
    assert sum(b.n for b in cfg.benchmarks) == 500
    assert {b.name for b in cfg.benchmarks} == {"mscore", "kramabench", "medagentbench"}


def test_runner_writes_paired_trials_and_resumes(tmp_path):
    runner = ExperimentRunner(config(), tmp_path)
    runner.run()
    rows = load_trials(runner.trials_path)
    assert len(rows) == 48
    by_group = {}
    for r in rows:
        by_group.setdefault(r["group"], set()).add(r["task_id"])
    assert set(by_group) == {"cf0", "cf33", "cf67", "cf100"}
    assert len({frozenset(v) for v in by_group.values()}) == 1  # same tasks in every group
    assert all(r["cf_agents"] == [] for r in rows if r["group"] == "cf0")
    assert all(len(r["cf_agents"]) == 3 for r in rows if r["group"] == "cf100")

    # interrupt: drop half the lines (and leave a torn one), then resume
    lines = runner.trials_path.read_text(encoding="utf-8").splitlines()
    runner.trials_path.write_text("\n".join(lines[:20]) + '\n{"trial_id": "cf0|tor', encoding="utf-8")
    seen = []
    ExperimentRunner(config(), tmp_path, progress=lambda d, t, r: seen.append(d)).run()
    ids = [r["trial_id"] for r in load_trials(runner.trials_path)]
    assert len(set(ids)) == 48 and seen[0] == 21


def test_a_rerun_trial_gets_a_fresh_session_log(tmp_path):
    from dataclasses import replace

    from ai_project.blackboard import JsonStore

    cfg = replace(config(n=2, fractions=(1.0,)), keep_sessions=True)
    runner = ExperimentRunner(cfg, tmp_path)
    runner.run()
    store = JsonStore(tmp_path / "t" / "sessions")
    first = {s: len(store.load(s)) for s in store.sessions()}
    assert len(first) == 2
    ExperimentRunner(cfg, tmp_path).run(resume=False)
    again = {s: store.load(s) for s in store.sessions()}
    assert {s: len(events) for s, events in again.items()} == first
    assert all(sum(e.kind == "task" for e in events) == 1 for events in again.values())


def test_report_and_mock_effect(tmp_path):
    runner = ExperimentRunner(config(n=60), tmp_path)
    runner.run()
    summary = write_report(runner.out)
    assert (runner.out / "summary.json").is_file() and (runner.out / "groups.csv").is_file()
    rows = {r["group"]: r for r in summary["groups"]}
    assert rows["cf0"]["recovered"] == 0.0
    assert rows["cf100"]["convergence_success"] >= rows["cf0"]["convergence_success"]
    for test in summary["tests"]:
        assert test["b"] == 0  # with the mock, a capable team never does worse on a task
    meta = json.loads((runner.out / "meta.json").read_text())
    assert meta["config"]["provider"] == "mock" and meta["trials"] == 240


def test_failed_trials_are_recorded_not_raised(tmp_path, monkeypatch):
    runner = ExperimentRunner(config(n=2, fractions=(0.0,)), tmp_path)
    monkeypatch.setattr("ai_project.experiments.runner.build_team",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no GPU")))
    runner.run()
    rows = load_trials(runner.trials_path)
    assert all(r["failed"] and "no GPU" in r["error"] for r in rows)
    summary = write_report(runner.out)
    assert summary["groups"][0]["trials"] == 0 and summary["groups"][0]["errors"] == 2


def test_plots(tmp_path):
    pytest.importorskip("matplotlib")
    from ai_project.experiments.plots import make_figures
    runner = ExperimentRunner(config(n=10), tmp_path)
    runner.run()
    made = make_figures(write_report(runner.out), runner.out)
    names = {p.name for p in made}
    assert {"convergence.svg", "intelligibility.svg", "groups.tex"} <= names
    assert "tokens.svg" not in names  # the mock reports no tokens


def test_statistics():
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.404, abs=1e-3) and hi == pytest.approx(0.596, abs=1e-3)
    assert wilson(0, 0) == (0.0, 0.0)
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(0, 6) == pytest.approx(0.03125)
    assert mcnemar_exact(5, 5) == 1.0
    lo, hi = bootstrap_mean([10.0] * 50)
    assert lo == hi == 10.0


def test_ollama_ablation_has_the_same_design_as_the_spec_ablation():
    spec = ExperimentConfig.load(CONFIGS / "ablation.toml")
    mac = ExperimentConfig.load(CONFIGS / "ablation-ollama.toml")
    assert mac.provider.startswith("ollama:")
    assert mac.fractions == spec.fractions
    assert [(b.name, b.n) for b in mac.benchmarks] == [(b.name, b.n) for b in spec.benchmarks]
    assert mac.session_config() == spec.session_config()


def test_health_check(tmp_path):
    from ai_project.experiments.analysis import health

    runner = ExperimentRunner(config(n=4, fractions=(0.0,)), tmp_path)
    runner.run()
    report = health(runner.out)
    assert report["problems"] == [] and report["trials"] == 4
    assert report["benchmarks"]["synthetic"]["failed_sessions"] == 0

    rows = load_trials(runner.trials_path)
    rows[0]["failed"], rows[0]["error"] = True, "RuntimeError: boom"
    rows[1]["score"] = {"correct": False, "value": 0.0, "detail": {"grader_error": "bad answer"}}
    meta = json.loads((runner.out / "meta.json").read_text())
    meta["config"]["provider"] = "ollama:qwen2.5:7b-instruct"  # a model run must report tokens
    (runner.out / "meta.json").write_text(json.dumps(meta))
    runner.trials_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    problems = " | ".join(health(runner.out)["problems"])
    assert "crashed" in problems and "grader raised" in problems and "no token counts" in problems
