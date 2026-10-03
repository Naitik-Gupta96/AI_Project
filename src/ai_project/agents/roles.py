"""The three agent roles, and a helper that builds a team for a task."""

from ai_project.agents.base import BaseAgent
from ai_project.llm import LLMProvider
from ai_project.tasks import DecisionTask


class AnalystAgent(BaseAgent):
    """Proposes: opens with the best option by its benefit estimates."""

    role = "analyst"
    description = "Analyst - proposes the option with the best estimated benefit"


class CriticAgent(BaseAgent):
    """Reviews: refutes proposals that break a hard constraint it knows about."""

    role = "critic"
    description = "Critic - checks proposals against hard constraints"


class SpecialistAgent(BaseAgent):
    """Resolves: adopts alternatives raised in disagreements if they pass its domain checks."""

    role = "specialist"
    description = "Specialist - resolves disagreements with domain knowledge"


ROLE_CLASSES: dict[str, type[BaseAgent]] = {
    cls.role: cls for cls in (AnalystAgent, CriticAgent, SpecialistAgent)
}


def build_team(task: DecisionTask, provider: LLMProvider | None = None) -> list[BaseAgent]:
    """Analyst, critic and specialist for ``task``, each holding its own evidence."""
    return [cls(llm_provider=provider, evidence=task.evidence_for(role))
            for role, cls in ROLE_CLASSES.items()]
