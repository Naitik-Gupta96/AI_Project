from typing import Any, Dict, Optional

from ai_project.agents.base import BaseAgent
from ai_project.agents.models import AgentContext, AgentDecision
from ai_project.llm import LLMProvider, MockLLMProvider
from ai_project.protocol.pxp import PXPTag


class SpecialistAgent(BaseAgent):
    """
    Specialist Agent: Provides independent specialized perspective.

    Role: Bring domain-specific considerations or alternative framing.
    """

    def __init__(
        self,
        agent_id: str = "specialist",
        llm_provider: Optional[LLMProvider] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            role="Specialist - Independent perspective",
            llm_provider=llm_provider or MockLLMProvider(),
        )

    def reason(self, context: AgentContext) -> AgentDecision:
        if self.llm_provider is None or isinstance(self.llm_provider, MockLLMProvider):
            return self._mock_reason(context)
        return self._llm_reason(context)

    def _mock_reason(self, context: AgentContext) -> AgentDecision:
        """Deterministic mock reasoning for Specialist."""
        task_hash = hash(context.task + "specialist") % 4
        options = ["Option A", "Option B", "Option C", "Option D"]
        prediction = options[task_hash]

        # Determine tag based on relationship to current prediction
        if not context.current_prediction or context.current_prediction == "(none)":
            tag = PXPTag.RATIFY
        elif prediction == context.current_prediction:
            tag = PXPTag.RATIFY
        else:
            tag = PXPTag.REVISE if task_hash % 2 == 0 else PXPTag.REFUTE

        explanations = [
            f"Specialized analysis of '{context.task}' indicates {prediction} is optimal when considering secondary criteria like maintainability and scalability.",
            f"From a domain-specific perspective, {prediction} addresses constraints that general analysis may overlook.",
            f"Specialized evaluation reveals {prediction} has superior robustness under varying conditions.",
        ]
        explanation = explanations[task_hash % len(explanations)]

        return AgentDecision(
            tag=tag,
            prediction=prediction,
            explanation=explanation,
            confidence=0.78 + (task_hash % 15) / 100.0,
            metadata={"reasoning_mode": "mock", "role": "specialist"},
        )

    def _llm_reason(self, context: AgentContext) -> AgentDecision:
        """Real LLM reasoning for Specialist."""
        try:
            with open("prompts/specialist.md", "r") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            prompt_template = self._get_default_prompt()

        prompt = self._render_prompt(prompt_template, context)
        return self._call_llm(prompt)

    def _render_prompt(self, template: str, context: AgentContext) -> str:
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
        return """You are the Specialist agent. Task: {{task}}. Current: {{current_prediction}}. Provide specialized perspective. Return JSON with tag, prediction, explanation, confidence."""