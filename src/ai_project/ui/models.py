from dataclasses import dataclass


@dataclass
class UIEvent:
    step: int
    agent_id: str
    tag: str
    prediction: str
    explanation: str
    confidence: float | None = None


@dataclass
class RunSummary:
    status: str
    prediction: str | None
    iterations: int
    deadlocked: bool


@dataclass
class SimulationResult:
    original_summary: RunSummary
    original_events: list[UIEvent]
    counterfactual_summary: RunSummary | None = None
    counterfactual_events: list[UIEvent] | None = None
    divergence_step: int | None = None
    summary: str | None = None
