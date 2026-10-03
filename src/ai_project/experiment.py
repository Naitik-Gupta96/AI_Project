"""
End-to-end pilot experiment.

Every trial runs the real system (``pipeline.run_task``): Blackboard, the
three role agents, Scheduler, deadlock detection, and, after a deadlock,
counterfactual reflection, branching and replay. Nothing is simulated or
sampled; with the deterministic mock provider each trial is reproducible
from (seed, task index, condition).

Condition: which agents are counterfactual-capable. ``cf_fraction`` is the
share of the 3-agent team that is (0, 1/3, 2/3, 1). Every subset of each
size is run on every task, so a fraction's numbers average over which agents
are capable instead of depending on one arbitrary choice.

What this pilot is: a deterministic check of how the implemented mechanism
behaves over procedurally generated tasks. What it is not: evidence about
LLM agents or real-world tasks; the agents follow the explicit rules in
``ai_project.llm.mock``.
"""

import itertools
import json
import math
import platform
import statistics
import subprocess
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ai_project
from ai_project.llm import LLMProvider, MockLLMProvider
from ai_project.pipeline import PipelineRun, RunConfig, run_task
from ai_project.tasks import ROLES, DecisionTask, generate_tasks

SCHEMA = "ai_project.pilot/v1"

DEFINITIONS = {
    "cf_fraction": "Share of the 3 agents that are counterfactual-capable, i.e. that may "
    "revise one of their own past messages after a deadlock.",
    "deadlock": "Deadlock detector fired (see ai_project.deadlock): the standing proposal "
    "was objected to max_disagreement_cycles times without being revised, or no novel "
    "proposal appeared for max_stagnant_steps messages while dissent remained.",
    "feasible": "The task has an option no role objects to (ground truth from the task's "
    "evidence; agents never see other roles' evidence).",
    "recovered": "A deadlocked run for which some counterfactual branch, replayed with the "
    "same agents, policy and config, reached CONSENSUS.",
    "best_decision": "The run ends in CONSENSUS on the feasible option with the highest "
    "analyst benefit score.",
}


def conditions() -> list[tuple[str, ...]]:
    """All subsets of the roles, smallest first."""
    return [c for k in range(len(ROLES) + 1) for c in itertools.combinations(ROLES, k)]


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")


def _compact(history: Iterable[dict[str, Any]]) -> list[list[Any]]:
    """[step, agent, tag, prediction] per event: enough to compare and re-check a run."""
    return [[e["iteration"], e["agent_id"], e["tag"], e["prediction"]] for e in history]


def trial_record(run: PipelineRun, trial_id: str, seed: int) -> dict[str, Any]:
    """Serialize one pipeline run as a trial record with its metrics."""
    task, original, final = run.task, run.original, run.final
    best = task.best_feasible()
    resolution = run.resolution
    counterfactual = None
    if resolution is not None:
        success = resolution.success
        counterfactual = {
            "recovered": resolution.recovered,
            "reflections": len(resolution.reflections),
            "revisions_proposed": sum(r.revised is not None for r in resolution.reflections),
            "branches_replayed": len(resolution.attempts),
            "branches": [
                {
                    "agent_id": r.agent_id,
                    "branch_point": r.iteration,
                    "revised": [r.revised["tag"], r.revised["prediction"],
                                r.revised["metadata"].get("alternative")],
                    "status": r.outcome.result.status,
                    "final_prediction": r.outcome.result.final_prediction,
                    "iterations": r.outcome.result.iterations,
                    "divergence_step": r.outcome.comparison.divergence_iteration,
                    "trace": _compact(r.outcome.result.history),
                }
                for r in resolution.attempts
            ],
            "recovering_branch": (
                {"agent_id": success.agent_id, "branch_point": success.iteration}
                if success else None
            ),
        }
    return {
        "trial_id": trial_id,
        "seed": seed,
        "task_id": task.task_id,
        "condition": {"cf_agents": list(run.config.cf_agents),
                      "cf_fraction": round(run.config.cf_fraction, 4)},
        "original": {
            "status": original.status,
            "stop_reason": original.stop_reason,
            "deadlock_rule": original.deadlock.rule if original.deadlocked else None,
            "final_prediction": original.final_prediction,
            "iterations": original.iterations,
            "trace": _compact(original.history),
        },
        "counterfactual": counterfactual,
        "metrics": {
            "task_feasible": best is not None,
            "original_consensus": original.consensus_reached,
            "original_deadlock": original.deadlocked,
            "original_iterations": original.iterations,
            "recovered": run.recovered if original.deadlocked else None,
            "final_status": final.status,
            "final_prediction": final.final_prediction,
            "best_decision": final.consensus_reached and final.final_prediction == best,
            "provider_calls": run.provider_calls(),
            "tokens": run.token_usage(),
            "runtime_ms": {k: round(v, 3) for k, v in run.runtime_ms.items()},
        },
    }


def run_pilot(
    n_tasks: int = 100,
    seed: int = 42,
    n_options: int = 3,
    objection_rate: float = 0.3,
    provider: LLMProvider | None = None,
    config: RunConfig | None = None,
    cf_conditions: Sequence[tuple[str, ...]] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Run every condition on ``n_tasks`` generated tasks and return the results document.
    """
    provider = provider or MockLLMProvider()
    config = config or RunConfig()
    tasks = generate_tasks(n_tasks, seed, n_options=n_options, objection_rate=objection_rate)
    conds = list(cf_conditions) if cf_conditions is not None else conditions()
    trials = []
    total = len(tasks) * len(conds)
    for task in tasks:
        for cond in conds:
            run = run_task(task, provider=provider, config=RunConfig(
                cf_agents=cond,
                max_steps=config.max_steps,
                max_disagreement_cycles=config.max_disagreement_cycles,
                max_stagnant_steps=config.max_stagnant_steps,
            ))
            label = "+".join(run.config.cf_agents) or "none"
            trials.append(trial_record(run, f"{task.task_id}/{label}", seed))
            if progress:
                progress(len(trials), total)

    mode = (
        "END-TO-END PILOT: deterministic mock agents on synthetic tasks"
        if provider.deterministic
        else f"END-TO-END PILOT: {provider.name} model on synthetic tasks (not deterministic)"
    )
    return {
        "schema": SCHEMA,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "package_version": ai_project.__version__,
        "python": platform.python_version(),
        "provider": provider.describe(),
        "parameters": {
            "seed": seed,
            "n_tasks": n_tasks,
            "n_options": n_options,
            "objection_rate": objection_rate,
            "conditions": [list(c) for c in conds],
            "run_config": {k: v for k, v in config.to_dict().items()
                           if k not in ("cf_agents", "cf_fraction")},
            "policy": "priority(proposer=analyst, critic=critic, resolver=specialist)",
        },
        "definitions": DEFINITIONS,
        "tasks": [t.to_dict() for t in tasks],
        "trials": trials,
    }


# ------------------------------------------------------------------ analysis


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for a binomial proportion (None if n == 0)."""
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def _summarize_group(trials: list[dict[str, Any]], with_ci: bool) -> dict[str, Any]:
    m = [t["metrics"] for t in trials]
    deadlocked = [x for x in m if x["original_deadlock"]]
    feasible_dl = [x for x in deadlocked if x["task_feasible"]]
    recovered = sum(bool(x["recovered"]) for x in deadlocked)
    recovered_feasible = sum(bool(x["recovered"]) for x in feasible_dl)
    iterations = [x["original_iterations"] for x in m]
    branches = [t["counterfactual"]["branches_replayed"] for t in trials if t["counterfactual"]]
    row: dict[str, Any] = {
        "trials": len(m),
        "original_consensus_rate": _rate(sum(x["original_consensus"] for x in m), len(m)),
        "deadlock_rate": _rate(len(deadlocked), len(m)),
        "deadlocked": len(deadlocked),
        "deadlocked_feasible": len(feasible_dl),
        "recovered": recovered,
        "recovery_rate": _rate(recovered, len(deadlocked)),
        "recovery_rate_feasible": _rate(recovered_feasible, len(feasible_dl)),
        "final_consensus_rate": _rate(sum(x["final_status"] == "CONSENSUS" for x in m), len(m)),
        "best_decision_rate": _rate(sum(x["best_decision"] for x in m), len(m)),
        "mean_iterations": statistics.fmean(iterations) if iterations else None,
        "median_iterations": statistics.median(iterations) if iterations else None,
        "mean_branches_replayed": statistics.fmean(branches) if branches else None,
        "mean_runtime_ms": statistics.fmean(
            sum(x["runtime_ms"].values()) for x in m) if m else None,
    }
    if with_ci:
        row["recovery_rate_feasible_ci95"] = wilson_interval(recovered_feasible, len(feasible_dl))
    return row


def summarize(doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """
    Descriptive summary of a results document.

    Returns ``by_fraction`` (pooled over the subsets of each size; trials
    share tasks, so no interval is given) and ``by_condition`` (one subset;
    each trial is a distinct task, so a Wilson interval over the generated
    task distribution is reported for the feasible-recovery rate).
    """
    by_fraction: dict[float, list[dict[str, Any]]] = {}
    by_condition: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for t in doc["trials"]:
        by_fraction.setdefault(t["condition"]["cf_fraction"], []).append(t)
        by_condition.setdefault(tuple(t["condition"]["cf_agents"]), []).append(t)
    return {
        "by_fraction": [
            {"cf_fraction": f, **_summarize_group(ts, with_ci=False)}
            for f, ts in sorted(by_fraction.items())
        ],
        "by_condition": [
            {"cf_agents": "+".join(c) or "none", "cf_fraction": ts[0]["condition"]["cf_fraction"],
             **_summarize_group(ts, with_ci=True)}
            for c, ts in sorted(by_condition.items(), key=lambda kv: (len(kv[0]), kv[0]))
        ],
    }


def save_results(doc: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def load_results(path: str | Path) -> dict[str, Any]:
    """Load a results document, refusing files that are not pilot results."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError(f"{path} is not a {SCHEMA} results file")
    return doc


def rerun_trial(doc: dict[str, Any], trial: dict[str, Any]) -> PipelineRun:
    """Re-execute one recorded trial from its task and condition (deterministic provider only)."""
    task = next(DecisionTask.from_dict(t) for t in doc["tasks"]
                if t["task_id"] == trial["task_id"])
    rc = doc["parameters"]["run_config"]
    return run_task(task, provider=MockLLMProvider(), config=RunConfig(
        cf_agents=tuple(trial["condition"]["cf_agents"]), **rc))
