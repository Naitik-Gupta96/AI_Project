"""
Backend -> UI adapter.

Builds the UI data contract (``ai_project.ui.models``) from real executions:
``pipeline.run_task`` runs for the Flash Talk and Run Explorer views, and
pilot results files for the Evaluation view. Nothing here decides anything;
it only reshapes results.
"""

from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from typing import Any

from ai_project.agents import ALTERNATIVE_KEY
from ai_project.counterfactual.resolver import Reflection
from ai_project.experiment import _compact, load_results, rerun_trial, summarize
from ai_project.llm import LLMProvider
from ai_project.pipeline import PipelineRun, run_task
from ai_project.scheduler.scheduler import SchedulerResult
from ai_project.scheduler.trace import (
    KIND_ACTION,
    KIND_INHERITED,
    KIND_INTERVENTION,
    TraceEntry,
)
from ai_project.tasks import DecisionTask, flash_talk_task
from ai_project.ui.models import (
    EVENT_INHERITED,
    EVENT_INTERVENTION,
    EVENT_MESSAGE,
    EVENT_STATUS,
    MODE_LOCAL_MODEL,
    MODE_MOCK,
    AgentView,
    CounterfactualView,
    DemoView,
    ExperimentView,
    Outcome,
    ReflectionView,
    RunEvent,
    RunView,
)

#: Default counterfactual-capable agent in the Flash Talk demo
FLASH_TALK_CF_AGENTS = ("critic",)

_KINDS = {
    KIND_ACTION: EVENT_MESSAGE,
    KIND_INHERITED: EVENT_INHERITED,
    KIND_INTERVENTION: EVENT_INTERVENTION,
}


def mode_label(provider: Mapping[str, Any]) -> str:
    return MODE_MOCK if provider.get("deterministic") else MODE_LOCAL_MODEL


def events_from_trace(
    trace: Iterable[TraceEntry], history: Iterable[Mapping[str, Any]]
) -> list[RunEvent]:
    """Merge scheduler trace entries with the history events they produced."""
    by_step = {e["iteration"]: e for e in history}
    events = []
    for entry in trace:
        kind = _KINDS.get(entry.kind, EVENT_STATUS)
        if kind == EVENT_STATUS:
            events.append(RunEvent(
                kind=kind, step=entry.step, tag=entry.event, prediction=entry.prediction,
                reason=entry.reason, status_after=entry.status,
            ))
            continue
        hist = by_step.get(entry.step, {})
        meta = hist.get("metadata") or {}
        events.append(RunEvent(
            kind=kind,
            step=entry.step,
            tag=entry.event,
            agent_id=entry.agent,
            role=meta.get("role"),
            prediction=entry.prediction,
            explanation=entry.explanation,
            confidence=entry.confidence,
            alternative=meta.get(ALTERNATIVE_KEY),
            rule=meta.get("rule"),
            reason=entry.reason,
            status_after=entry.status,
            timestamp=hist.get("timestamp"),
            message_id=entry.message_id,
        ))
    return events


def _outcome(result: SchedulerResult) -> Outcome:
    if result.consensus_reached:
        reason = result.consensus.reason
    elif result.deadlocked:
        reason = result.deadlock.reason
    elif result.error:
        reason = result.error
    else:
        reason = f"Stopped: {result.stop_reason}"
    return Outcome(result.status, result.final_prediction, result.iterations, reason)


def run_view(
    result: SchedulerResult,
    task: DecisionTask,
    provider: Mapping[str, Any],
    title: str,
    trace: Iterable[TraceEntry] | None = None,
) -> RunView:
    """RunView for an original run (or a branch, passing the branch's full trace)."""
    return RunView(
        title=title,
        task=task.question,
        options=list(task.options),
        mode=mode_label(provider),
        provider=dict(provider),
        policy=result.policy,
        config=result.config,
        events=events_from_trace(trace if trace is not None else result.trace, result.history),
        outcome=_outcome(result),
    )


def _counterfactual_view(
    reflection: Reflection, original: RunView, task: DecisionTask, provider: Mapping[str, Any]
) -> CounterfactualView:
    outcome = reflection.outcome
    branch = outcome.branch
    view = run_view(
        outcome.result, task, provider,
        title=f"Counterfactual branch {branch.branch_id}",
        trace=branch.get_trace_entries(),
    )
    original_event = next(e for e in original.events
                          if e.is_message and e.step == reflection.iteration)
    revised_event = next(e for e in view.events if e.kind == EVENT_INTERVENTION)
    cmp = outcome.comparison
    return CounterfactualView(
        agent_id=reflection.agent_id,
        branch_point=reflection.iteration,
        original_event=original_event,
        revised_event=revised_event,
        branch=view,
        divergence_step=cmp.divergence_iteration,
        shared_prefix=cmp.shared_prefix,
        recovered=reflection.recovered,
        summary=cmp.summary,
    )


def demo_view(run: PipelineRun) -> DemoView:
    """DemoView of a pipeline run: original, reflections, replayed branches."""
    original = run_view(run.original, run.task, run.provider, title="Original run")
    agents = [
        AgentView(
            agent_id=a.agent_id,
            role=a.role,
            description=a.description,
            evidence=a.evidence.to_dict(),
            counterfactual_capable=a.agent_id in run.config.cf_agents,
        )
        for a in run.agents
    ]
    reflections, branches = [], []
    if run.resolution is not None:
        for r in run.resolution.reflections:
            reflections.append(ReflectionView(
                agent_id=r.agent_id,
                step=r.iteration,
                original=f"{r.original['tag']} {r.original['prediction']}",
                revised=(f"{r.revised['tag']} {r.revised['prediction']}"
                         + (f" (alternative: {r.revised['metadata'][ALTERNATIVE_KEY]})"
                            if r.revised["metadata"].get(ALTERNATIVE_KEY) else "")
                         if r.revised else None),
                replayed=r.outcome is not None,
                outcome=r.outcome.result.status if r.outcome else None,
            ))
            if r.outcome is not None:
                branches.append(_counterfactual_view(r, original, run.task, run.provider))
    return DemoView(
        original=original,
        agents=agents,
        cf_agents=list(run.config.cf_agents),
        reflections=reflections,
        branches=branches,
        final=_outcome(run.final),
        original_preserved=[e.to_dict() for e in run.board.get_history()] == run.original.history
        and run.board.get_state().status.value == run.original.status,
        runtime_ms={k: round(v, 2) for k, v in run.runtime_ms.items()},
    )


def flash_talk_demo(
    cf_agents: Collection[str] = FLASH_TALK_CF_AGENTS, provider: LLMProvider | None = None
) -> DemoView:
    """Run the Flash Talk task end to end."""
    return demo_view(run_task(flash_talk_task(), cf_agents, provider))


# ------------------------------------------------------------------ results files


def find_results(directory: str | Path) -> list[Path]:
    """Pilot results files in ``directory``, newest first."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("pilot_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def experiment_view(path: str | Path) -> ExperimentView:
    doc = load_results(path)
    summary = summarize(doc)
    return ExperimentView(
        path=str(path),
        mode=doc["mode"],
        provider=doc["provider"],
        generated_at=doc["generated_at"],
        git_commit=doc["git_commit"],
        parameters=doc["parameters"],
        definitions=doc["definitions"],
        by_fraction=summary["by_fraction"],
        by_condition=summary["by_condition"],
        n_trials=len(doc["trials"]),
    )


def trial_demo_view(doc: dict[str, Any], trial: dict[str, Any]) -> tuple[DemoView, bool]:
    """
    Re-execute a recorded trial and return its DemoView plus whether the
    re-execution reproduced the recorded original trace and outcome.
    """
    run = rerun_trial(doc, trial)
    reproduced = (
        _compact(run.original.history) == trial["original"]["trace"]
        and run.final.status == trial["metrics"]["final_status"]
        and run.final.final_prediction == trial["metrics"]["final_prediction"]
    )
    return demo_view(run), reproduced
