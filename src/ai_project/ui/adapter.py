"""
Backend -> UI adapter.

Converts real Scheduler runs and counterfactual outcomes into the UI data
models (``UIEvent``, ``RunSummary``, ``SimulationResult``) that the Streamlit
frontend renders. The frontend only depends on these models, never on the
Scheduler or engine types directly.

``DEMO_RUNS`` maps a label to a function that runs one demo end to end and
returns a ``SimulationResult``.
"""

from collections.abc import Callable, Mapping
from typing import Any

from ai_project.agents import AnalystAgent, CriticAgent, SpecialistAgent
from ai_project.blackboard import Blackboard
from ai_project.counterfactual.engine import CounterfactualOutcome
from ai_project.counterfactual.scenarios import run_deadlock_counterfactual
from ai_project.scheduler.policies import PriorityPolicy
from ai_project.scheduler.scenarios import (
    DEFAULT_TASK,
    Scenario,
    alternating_deadlock_scenario,
    consensus_scenario,
    deadlock_scenario,
)
from ai_project.scheduler.scheduler import Scheduler, SchedulerConfig, SchedulerResult
from ai_project.ui.models import RunSummary, SimulationResult, UIEvent


def event_to_ui(event: Mapping[str, Any]) -> UIEvent:
    """Convert one serialized history event (``HistoryEvent.to_dict()``) to a UIEvent."""
    return UIEvent(
        step=event["iteration"],
        agent_id=event["agent_id"],
        tag=event["tag"],
        prediction=event["prediction"],
        explanation=event["explanation"],
        confidence=event.get("confidence"),
    )


def summarize(result: SchedulerResult) -> RunSummary:
    """Convert a SchedulerResult to a RunSummary."""
    return RunSummary(
        status=result.status,
        prediction=result.final_prediction,
        iterations=result.iterations,
        deadlocked=result.deadlocked,
    )


def build_simulation_result(
    original: SchedulerResult, outcome: CounterfactualOutcome | None = None
) -> SimulationResult:
    """
    Pair an original run with its counterfactual outcome (if any).

    ``divergence_step`` is the first iteration whose event differs between the
    two histories (``BranchComparison.divergence_iteration``); it is ``None``
    when there is no counterfactual or the histories are identical.
    """
    simulation = SimulationResult(
        original_summary=summarize(original),
        original_events=[event_to_ui(e) for e in original.history],
    )
    if outcome is not None:
        simulation.counterfactual_summary = summarize(outcome.result)
        simulation.counterfactual_events = [event_to_ui(e) for e in outcome.result.history]
        simulation.divergence_step = outcome.comparison.divergence_iteration
        simulation.summary = outcome.comparison.summary
    return simulation


def run_scenario(scenario: Scenario) -> SimulationResult:
    """Run a scheduler scenario without a counterfactual branch."""
    _, _, result = scenario.run()
    return build_simulation_result(result)


def run_deadlock_counterfactual_demo() -> SimulationResult:
    """Scenario C: original DEADLOCK, counterfactual branch reaches CONSENSUS."""
    run = run_deadlock_counterfactual()
    return build_simulation_result(run.original_result, run.outcome)


def run_pex_agents_demo(task: str = DEFAULT_TASK) -> SimulationResult:
    """
    Person 2's Analyst, Critic and Specialist (MockLLMProvider) under the Scheduler.

    These agents choose options with Python's ``hash(task)``, so the outcome can
    differ between processes unless ``PYTHONHASHSEED`` is set.
    """
    board = Blackboard()
    board.initialize_task(task)
    scheduler = Scheduler(
        board,
        [AnalystAgent(), CriticAgent(), SpecialistAgent()],
        policy=PriorityPolicy(proposer="analyst", critic="critic", resolver="specialist"),
        config=SchedulerConfig(max_steps=12),
    )
    return build_simulation_result(scheduler.run())


DEMO_RUNS: dict[str, Callable[[], SimulationResult]] = {
    "Deadlock -> counterfactual consensus (Scenario C)": run_deadlock_counterfactual_demo,
    "Consensus (Scenario A)": lambda: run_scenario(consensus_scenario()),
    "Deadlock (Scenario B)": lambda: run_scenario(deadlock_scenario()),
    "Alternating deadlock": lambda: run_scenario(alternating_deadlock_scenario()),
    "PEX agents (MockLLMProvider)": run_pex_agents_demo,
}
