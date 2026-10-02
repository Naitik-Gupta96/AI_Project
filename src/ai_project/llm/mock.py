import json
import hashlib
from typing import Any, Dict, List, Optional

from ai_project.llm.base import LLMProvider, ProviderUnavailableError
from ai_project.protocol.pxp import PXPTag
from ai_project.agents.models import AgentDecision


class MockLLMProvider(LLMProvider):
    """
    Deterministic mock LLM provider for testing and demos.

    Produces role-appropriate responses based on the prompt content.
    Uses prompt hashing for deterministic output.
    """

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._call_count = 0

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a deterministic mock response."""
        self._call_count += 1

        # Extract role from prompt
        role = self._extract_role(prompt)

        # Create deterministic response based on role and prompt
        decision = self._create_decision(role, prompt)

        return json.dumps(decision.to_dict(), ensure_ascii=False)

    def _extract_role(self, prompt: str) -> str:
        """Extract agent role from prompt."""
        prompt_lower = prompt.lower()
        if "analyst" in prompt_lower:
            return "analyst"
        elif "critic" in prompt_lower:
            return "critic"
        elif "specialist" in prompt_lower:
            return "specialist"
        return "analyst"

    def _create_decision(self, role: str, prompt: str) -> AgentDecision:
        """Create a role-appropriate decision deterministically."""
        # Hash prompt for deterministic variation
        prompt_hash = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)

        # Extract current prediction from prompt
        current_pred = self._extract_current_prediction(prompt)

        if role == "analyst":
            return self._analyst_decision(current_pred, prompt_hash)
        elif role == "critic":
            return self._critic_decision(current_pred, prompt_hash)
        elif role == "specialist":
            return self._specialist_decision(current_pred, prompt_hash)
        else:
            return self._analyst_decision(current_pred, prompt_hash)

    def _extract_current_prediction(self, prompt: str) -> Optional[str]:
        """Extract current prediction from prompt context."""
        import re
        # Look for "current_prediction" in the prompt
        match = re.search(r'current_prediction[:\s]+"?([^"\n]+)"?', prompt, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _analyst_decision(self, current_pred: Optional[str], seed: int) -> AgentDecision:
        """Analyst generates initial or independent prediction."""
        options = ["Option A", "Option B", "Option C", "Option D"]
        pred = options[seed % len(options)]

        explanations = [
            f"Based on the task requirements, {pred} provides the best balance of feasibility and impact.",
            f"Analysis of the constraints suggests {pred} is the most viable approach.",
            f"{pred} aligns well with the stated objectives and available evidence.",
        ]
        exp = explanations[seed % len(explanations)]

        return AgentDecision(
            tag=PXPTag.RATIFY,
            prediction=pred,
            explanation=exp,
            confidence=0.75 + (seed % 20) / 100.0,
            metadata={"role": "analyst", "seed": seed},
        )

    def _critic_decision(self, current_pred: Optional[str], seed: int) -> AgentDecision:
        """Critic challenges or refines the current prediction."""
        if not current_pred or current_pred == "(none)":
            # No prediction yet - critic acts as initial reviewer
            return AgentDecision(
                tag=PXPTag.REVISE,
                prediction="Need more information",
                explanation="Cannot evaluate without an existing prediction to critique.",
                confidence=0.5,
                metadata={"role": "critic", "seed": seed},
            )

        # Deterministically decide: RATIFY, REVISE, or REFUTE
        decision_type = seed % 3
        confidence = 0.6 + (seed % 30) / 100.0

        if decision_type == 0:
            # RATIFY - agree with current
            return AgentDecision(
                tag=PXPTag.RATIFY,
                prediction=current_pred,
                explanation=f"The reasoning for {current_pred} is sound and well-supported.",
                confidence=confidence,
                metadata={"role": "critic", "seed": seed},
            )
        elif decision_type == 1:
            # REVISE - agree but modify
            alt_options = ["Option A", "Option B", "Option C", "Option D"]
            alt = alt_options[(seed + 1) % len(alt_options)]
            return AgentDecision(
                tag=PXPTag.REVISE,
                prediction=alt,
                explanation=f"While {current_pred} has merit, {alt} better addresses the constraints.",
                confidence=confidence,
                metadata={"role": "critic", "seed": seed},
            )
        else:
            # REFUTE - disagree
            alt_options = ["Option A", "Option B", "Option C", "Option D"]
            alt = alt_options[(seed + 2) % len(alt_options)]
            return AgentDecision(
                tag=PXPTag.REFUTE,
                prediction=current_pred,
                explanation=f"{current_pred} fails to account for key constraints. Consider {alt} instead.",
                confidence=confidence,
                metadata={"role": "critic", "seed": seed},
            )

    def _specialist_decision(self, current_pred: Optional[str], seed: int) -> AgentDecision:
        """Specialist provides independent perspective."""
        options = ["Option A", "Option B", "Option C", "Option D"]
        pred = options[(seed + 1) % len(options)]

        explanations = [
            f"From a specialized perspective, {pred} offers unique advantages not previously considered.",
            f"Domain analysis indicates {pred} is more robust under edge cases.",
            f"Specialized evaluation favors {pred} due to secondary criteria.",
        ]
        exp = explanations[seed % len(explanations)]

        # Sometimes ratify, sometimes revise/refute
        if seed % 2 == 0:
            tag = PXPTag.RATIFY
        else:
            tag = PXPTag.REVISE if seed % 3 != 0 else PXPTag.REFUTE

        return AgentDecision(
            tag=tag,
            prediction=pred,
            explanation=exp,
            confidence=0.7 + (seed % 25) / 100.0,
            metadata={"role": "specialist", "seed": seed},
        )

    def is_available(self) -> bool:
        return True