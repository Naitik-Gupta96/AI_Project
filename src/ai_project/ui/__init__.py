"""UI data models and the backend -> UI adapter (Person 4 frontend)."""

from ai_project.ui.adapter import (
    DEMO_RUNS,
    build_simulation_result,
    event_to_ui,
    run_deadlock_counterfactual_demo,
    run_pex_agents_demo,
    run_scenario,
    summarize,
)
from ai_project.ui.models import RunSummary, SimulationResult, UIEvent

__all__ = [
    "DEMO_RUNS",
    "build_simulation_result",
    "event_to_ui",
    "run_deadlock_counterfactual_demo",
    "run_pex_agents_demo",
    "run_scenario",
    "summarize",
    "RunSummary",
    "SimulationResult",
    "UIEvent",
]
