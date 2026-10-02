from dataclasses import dataclass
from typing import Optional, List

@dataclass
class UIEvent:
    step: int
    agent_id: str
    tag: str
    prediction: str
    explanation: str
    confidence: float

@dataclass
class RunSummary:
    status: str
    prediction: Optional[str]
    iterations: int
    deadlocked: bool

@dataclass
class SimulationResult:
    original_summary: RunSummary
    original_events: List[UIEvent]
    counterfactual_summary: Optional[RunSummary] = None
    counterfactual_events: Optional[List[UIEvent]] = None
    divergence_step: Optional[int] = None
