from typing import Any, Dict, Optional

from ai_project.agents.base import BaseAgent
from ai_project.agents.models import AgentContext, AgentDecision
from ai_project.llm import LLMProvider, MockLLMProvider
from ai_project.protocol.pxp import PXPTag


class CriticAgent(BaseAgent):
    """
    Critic Agent: Challenges or validates the current reasoning.

    Role: Identify weaknesses, contradictions, or unsupported assumptions.
    """

    def __init__(
        self,
        agent_id: str = "critic",
        llm_provider: Optional[LLMProvider] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            role="Critic - Challenge current reasoning",
            llm_provider=llm_provider or MockLLMProvider(),
        )

    def reason(self, context: AgentContext) -> AgentDecision:
        if self.llm_provider is None or isinstance(self.llm_provider, MockLLMProvider):
            return self._mock_reason(context)
        return self._llm_reason(context)

    def _mock_reason(self, context: AgentContext) -> AgentDecision:
        """Deterministic mock reasoning for Critic."""
        # If no current prediction, request one
        if not context.current_prediction or context.current_prediction == "(none)":
            return AgentDecision(
                tag=PXPTag.REVISE,
                prediction="Need initial prediction first",
                explanation="Cannot critique without an existing prediction. Requesting Analyst to provide initial reasoning.",
                confidence=0.5,
                metadata={"reasoning_mode": "mock", "role": "critic"},
            )

        # Deterministic decision based on iteration and task
        task_hash = hash(context.task) % 3
        iteration = context.iteration

        if task_hash == 0:
            # Ratify - agree
            return AgentDecision(
                tag=PXPTag.RATIFY,
                prediction=context.current_prediction,
                explanation=f"The reasoning for {context.current_prediction} is logically sound and addresses the key constraints of the task.",
                confidence=0.82,
                metadata={"reasoning_mode": "mock", "role": "critic"},
            )
        elif task_hash == 1:
            # Revise - agree but modify
            alt_options = ["Option A", "Option B", "Option C", "Option D"]
            current_idx = alt_options.index(context.current_prediction) if context.current_prediction in alt_options else 0
            alt = alt_options[(current_idx + 1) % len(alt_options)]
            return AgentDecision(
                tag=PXPTag.REVISE,
                prediction=alt,
                explanation=f"While {context.current_prediction} has merit, {alt} better satisfies the implicit constraints identified in the task.",
                confidence=0.75,
                metadata={"reasoning_mode": "mock", "role": "critic"},
            )
        else:
            # Refute - disagree
            alt_options = ["Option A", "Option B", "Option C", "Option D"]
            current_idx = alt_options.index(context.current_prediction) if context.current_prediction in alt_options else 0
            alt = alt_options[(current_idx + 2) % len(alt_options)]
            return AgentDecision(
                tag=PXPTag.REFUTE,
                prediction=context.current_prediction,
                explanation=f"{context.current_prediction} fails to account for critical edge cases. {alt} provides a more robust solution.",
                confidence=0.78,
                metadata={"reasoning_mode": "mock", "role": "critic"},
            )

    def _llm_reason(self, context: AgentContext) -> AgentDecision:
        """Real LLM reasoning for Critic."""
        # Load prompt template
        try:
            with open("prompts/critic.md", "r") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            prompt_template = self._get_default_prompt()

        prompt = self._render_prompt(prompt_template, context)
        return self._call_llm(prompt)

    def _render_prompt(self, template: str, context: AgentContext) -> str:
        """Simple template rendering."""
        prompt = template.replace("{{task}}", context.task)
        prompt = prompt.replace("{{status}}", context.status)
        prompt = prompt.replace("{{iteration}}", str(context.iteration))
        prompt = prompt.replace("{{current_prediction}}", context.current_prediction or "(none)")
        prompt = prompt.replace("{{current_explanation}}", context.current_explanation or "(none)")
        prompt = prompt.replace("{{agent_id}}", context.agent_id)
        prompt = prompt.replace("{{agent_role}}", context.agent_role)

        history_str = ""
        for event in context.recent_history:
            history_str += f"- Iteration {event.iteration}: {event.agent_id} ({event.tag}) - {event.prediction} - {event.explanation} (confidence: {event.confidence})\n"
        prompt = prompt.replace("{% for event in recent_history %}\n- Iteration {{event.iteration}}: {{event.agent_id}} ({{event.tag}}) - {{event.prediction}} - {{event.explanation}} (confidence: {{event.confidence}})\n{% endfor %}", history_str)

        return prompt

    def _get_default_prompt(self) -> str:
        return """You are the Critic agent. Task: {{task}}. Current: {{current_prediction}}. Critique and return JSON with tag, prediction, explanation, confidence."""