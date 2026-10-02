from typing import Any, Dict, Optional

from ai_project.agents.base import BaseAgent
from ai_project.agents.models import AgentContext, AgentDecision
from ai_project.llm import LLMProvider, MockLLMProvider
from ai_project.protocol.pxp import PXPTag


class AnalystAgent(BaseAgent):
    """
    Analyst Agent: Generates initial or independent predictions.

    Role: Analyze the task and form a reasoned prediction with explanation.
    """

    def __init__(
        self,
        agent_id: str = "analyst",
        llm_provider: Optional[LLMProvider] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            role="Analyst - Generate initial prediction",
            llm_provider=llm_provider or MockLLMProvider(),
        )

    def reason(self, context: AgentContext) -> AgentDecision:
        if self.llm_provider is None or isinstance(self.llm_provider, MockLLMProvider):
            return self._mock_reason(context)
        return self._llm_reason(context)

    def _mock_reason(self, context: AgentContext) -> AgentDecision:
        """Deterministic mock reasoning for Analyst."""
        # If no current prediction, generate one
        if not context.current_prediction or context.current_prediction == "(none)":
            task_hash = hash(context.task) % 4
            options = ["Option A", "Option B", "Option C", "Option D"]
            prediction = options[task_hash]

            return AgentDecision(
                tag=PXPTag.RATIFY,
                prediction=prediction,
                explanation=f"Initial analysis of '{context.task}' suggests {prediction} as the most viable option based on the stated requirements.",
                confidence=0.78,
                metadata={"reasoning_mode": "mock", "role": "analyst"},
            )

        # If there's a prediction, evaluate it independently
        return AgentDecision(
            tag=PXPTag.RATIFY,
            prediction=context.current_prediction,
            explanation=f"Independent review confirms {context.current_prediction} remains the best choice for '{context.task}'.",
            confidence=0.72,
            metadata={"reasoning_mode": "mock", "role": "analyst"},
        )

    def _llm_reason(self, context: AgentContext) -> AgentDecision:
        """Real LLM reasoning for Analyst."""
        from ai_project.llm import AgentDecisionParser

        # Load prompt template
        try:
            with open("prompts/analyst.md", "r") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            prompt_template = self._get_default_prompt()

        # Render prompt
        prompt = self._render_prompt(prompt_template, context)

        # Call LLM and parse
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

        # Render history
        history_str = ""
        for event in context.recent_history:
            history_str += f"- Iteration {event.iteration}: {event.agent_id} ({event.tag}) - {event.prediction} - {event.explanation} (confidence: {event.confidence})\n"
        prompt = prompt.replace("{% for event in recent_history %}\n- Iteration {{event.iteration}}: {{event.agent_id}} ({{event.tag}}) - {{event.prediction}} - {{event.explanation}} (confidence: {{event.confidence}})\n{% endfor %}", history_str)

        return prompt

    def _get_default_prompt(self) -> str:
        return """You are the Analyst agent. Task: {{task}}. Current: {{current_prediction}}. Return JSON with tag, prediction, explanation, confidence."""