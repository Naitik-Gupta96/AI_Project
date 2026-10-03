"""Intelligible Blackboard Architecture with Counterfactual Agents (research prototype)."""

from ai_project.protocol import PXPMessage, PXPTag, PXPValidator, ValidationError
from ai_project.blackboard import (
    Blackboard,
    BlackboardStatus,
    BlackboardState,
    HistoryEvent,
    BlackboardSnapshot,
    BlackboardError,
    InvalidMessageError,
    BlackboardNotInitializedError,
    InvalidStatusTransitionError,
    SnapshotError,
)
from ai_project.agents import (
    BaseAgent,
    AgentError,
    AgentDecision,
    AgentContext,
    AnalystAgent,
    CriticAgent,
    SpecialistAgent,
    build_team,
)
from ai_project.llm import (
    LLMProvider,
    LLMProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    MockLLMProvider,
    OllamaProvider,
    AgentDecisionParser,
    ParseError,
)
from ai_project.tasks import DecisionTask, Evidence, flash_talk_task, generate_tasks
from ai_project.pipeline import PipelineRun, RunConfig, run_task

__version__ = "0.1.0"

__all__ = [
    # Protocol
    "PXPMessage",
    "PXPTag",
    "PXPValidator",
    "ValidationError",
    # Blackboard
    "Blackboard",
    "BlackboardStatus",
    "BlackboardState",
    "HistoryEvent",
    "BlackboardSnapshot",
    "BlackboardError",
    "InvalidMessageError",
    "BlackboardNotInitializedError",
    "InvalidStatusTransitionError",
    "SnapshotError",
    # Agents
    "BaseAgent",
    "AgentError",
    "AgentDecision",
    "AgentContext",
    "AnalystAgent",
    "CriticAgent",
    "SpecialistAgent",
    "build_team",
    # LLM
    "LLMProvider",
    "LLMProviderError",
    "ProviderUnavailableError",
    "ProviderTimeoutError",
    "MockLLMProvider",
    "OllamaProvider",
    "AgentDecisionParser",
    "ParseError",
    # Tasks and the end-to-end pipeline
    "DecisionTask",
    "Evidence",
    "flash_talk_task",
    "generate_tasks",
    "PipelineRun",
    "RunConfig",
    "run_task",
]