"""
BaseAgent: the one decision pipeline every agent uses.

    act(board):  Blackboard -> AgentContext -> prompt -> provider -> parser
                 -> AgentDecision -> PXPMessage (the Scheduler publishes it)
    reflect():   same pipeline in reflection mode, for counterfactual replay

Roles differ only in their role name and prompt instructions; what an agent
decides comes from the provider (the deterministic mock's role rules, or a
model).
"""

from collections.abc import Sequence
from dataclasses import replace
from importlib import resources
from string import Template
from typing import Any, ClassVar

from ai_project.agents.models import ALTERNATIVE_KEY, AgentContext, AgentDecision
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import HistoryEvent
from ai_project.deadlock.stances import current_proposal
from ai_project.llm import AgentDecisionParser, LLMProvider, LLMRequest, MockLLMProvider, ParseError
from ai_project.llm.base import LLMProviderError
from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.tasks import Evidence


class AgentError(Exception):
    """Raised when an agent cannot produce a valid decision."""


def _template(name: str) -> Template:
    text = resources.files("ai_project.llm").joinpath("prompts", name).read_text(encoding="utf-8")
    return Template(text)


def _format_event(e: HistoryEvent) -> str:
    alt = e.metadata.get(ALTERNATIVE_KEY)
    alt_note = f" [alternative: {alt}]" if alt else ""
    return f"{e.iteration}. {e.agent_id} {e.tag} {e.prediction}{alt_note}: {e.explanation}"


def _format_evidence(evidence: Evidence) -> str:
    lines = [f"- benefit estimate for {o}: {s:.2f}" for o, s in evidence.scores.items()]
    lines += [f"- {o} is ruled out: {r}" for o, r in evidence.objections.items()]
    return "\n".join(lines) or "- (no private evidence)"


class BaseAgent:
    """
    An agent with a role, private evidence and a decision provider.

    Args:
        agent_id: Unique id (defaults to the role name)
        llm_provider: Decision provider (defaults to MockLLMProvider)
        evidence: This agent's private evidence about the task's options
        parser: Structured-output parser
    """

    role: ClassVar[str] = "agent"
    description: ClassVar[str] = "Generic agent"

    def __init__(
        self,
        agent_id: str | None = None,
        llm_provider: LLMProvider | None = None,
        evidence: Evidence | None = None,
        parser: AgentDecisionParser | None = None,
    ) -> None:
        self.agent_id = agent_id or self.role
        self.llm_provider = llm_provider or MockLLMProvider()
        self.evidence = evidence or Evidence()
        self.parser = parser or AgentDecisionParser()
        #: Provider calls made and tokens reported by the provider (None if never reported)
        self.usage: dict[str, Any] = {"calls": 0, "prompt_tokens": None, "completion_tokens": None}

    # ------------------------------------------------------------------ public API

    def act(self, board: Blackboard) -> PXPMessage:
        """Read the board and return the PXP message this agent wants to publish."""
        context = self.build_context(board)
        decision = self.decide(context)
        return decision.to_pxp_message(self.agent_id, board.get_iteration() + 1)

    def decide(self, context: AgentContext) -> AgentDecision:
        """Run the provider on a context and return a validated decision."""
        raw = self._generate(context, "act.md")
        try:
            decision = self.parser.parse(raw)
        except ParseError as exc:
            raise AgentError(f"{self.agent_id}: unparseable provider output: {exc}") from exc
        return self._normalize(decision, context)

    def reflect(
        self,
        task: str,
        options: Sequence[str],
        history: Sequence[HistoryEvent],
        own_event: HistoryEvent,
    ) -> AgentDecision | None:
        """
        Counterfactual reflection: what would this agent have sent instead of
        ``own_event``, knowing the full ``history`` of the run?

        Returns the replacement decision, or None if the agent would not change it.
        """
        if own_event.agent_id != self.agent_id:
            raise AgentError(f"{self.agent_id} can only reflect on its own messages")
        before = [e for e in history if e.iteration < own_event.iteration]
        context = AgentContext(
            agent_id=self.agent_id,
            role=self.role,
            task=task,
            options=tuple(options),
            evidence=self.evidence,
            status="DEADLOCK",
            iteration=len(history),
            proposal=current_proposal(before),
            history=tuple(history),
            reflect_on=own_event,
        )
        raw = self._generate(context, "reflect.md")
        try:
            decision = self.parser.parse_reflection(raw)
        except ParseError as exc:
            raise AgentError(f"{self.agent_id}: unparseable reflection output: {exc}") from exc
        if decision is None:
            return None
        decision = self._normalize(decision, context)
        decision.metadata["reflection_of"] = own_event.iteration
        return decision

    def build_context(self, board: Blackboard) -> AgentContext:
        """Structured view of the board for this agent."""
        state = board.get_state()
        history = tuple(board.get_history())
        return AgentContext(
            agent_id=self.agent_id,
            role=self.role,
            task=state.task,
            options=tuple(state.metadata.get("options") or self._evidence_options()),
            evidence=self.evidence,
            status=state.status.value,
            iteration=state.iteration,
            proposal=current_proposal(history),
            history=history,
        )

    def render_prompt(self, context: AgentContext, template: str = "act.md") -> str:
        """Fill a prompt template from a context (what a model-backed provider reads)."""
        values = {
            "agent_id": context.agent_id,
            "role": context.role,
            "task": context.task,
            "options": ", ".join(context.options) or "(not listed)",
            "evidence": _format_evidence(context.evidence),
            "status": context.status,
            "iteration": context.iteration,
            "proposal": context.proposal or "(none yet)",
            "history": "\n".join(_format_event(e) for e in context.history) or "(empty)",
            "role_instructions": self._role_instructions(),
            "reflect_step": context.reflect_on.iteration if context.reflect_on else "",
            "reflect_message": _format_event(context.reflect_on) if context.reflect_on else "",
        }
        return _template(template).substitute(values)

    def get_identity(self) -> dict[str, str]:
        return {"agent_id": self.agent_id, "role": self.role, "description": self.description}

    # ------------------------------------------------------------------ internals

    def _role_instructions(self) -> str:
        path = resources.files("ai_project.llm").joinpath("prompts", f"{self.role}.md")
        return path.read_text(encoding="utf-8").strip() if path.is_file() else self.description

    def _evidence_options(self) -> list[str]:
        seen = dict.fromkeys(list(self.evidence.scores) + list(self.evidence.objections))
        return list(seen)

    def _generate(self, context: AgentContext, template: str) -> str:
        request = LLMRequest(prompt=self.render_prompt(context, template), context=context)
        try:
            response = self.llm_provider.generate(request)
        except LLMProviderError as exc:
            raise AgentError(f"{self.agent_id}: provider error: {exc}") from exc
        self.usage["calls"] += 1
        if response.usage:
            for key in ("prompt_tokens", "completion_tokens"):
                self.usage[key] = (self.usage[key] or 0) + response.usage.get(key, 0)
        return response.text

    def _normalize(self, decision: AgentDecision, context: AgentContext) -> AgentDecision:
        """
        Enforce PXP semantics on provider output (a no-op for the mock, whose
        rules already follow them). Model output is repaired where the intent is
        unambiguous; each repair is recorded in metadata["normalized"].
        """
        notes: list[str] = []
        options = context.options
        tag, prediction = decision.tag, decision.prediction

        if options and tag != PXPTag.REJECT and prediction not in options:
            matches = [o for o in options if o.lower() in prediction.lower()]
            if len(matches) != 1:
                raise AgentError(
                    f"{self.agent_id}: prediction '{prediction}' is not one of {list(options)}"
                )
            notes.append(f"prediction '{prediction}' mapped to '{matches[0]}'")
            prediction = matches[0]

        metadata = dict(decision.metadata)
        proposal = context.proposal
        if proposal is not None:
            if tag == PXPTag.REFUTE and prediction != proposal:
                notes.append(f"REFUTE {prediction} read as REFUTE {proposal} naming {prediction}")
                metadata.setdefault(ALTERNATIVE_KEY, prediction)
                prediction = proposal
            elif tag == PXPTag.RATIFY and prediction != proposal:
                notes.append(f"RATIFY of non-standing {prediction} read as REVISE")
                tag = PXPTag.REVISE
            elif tag == PXPTag.REVISE and prediction == proposal:
                notes.append("REVISE to the standing proposal read as RATIFY")
                tag = PXPTag.RATIFY

        alt = metadata.get(ALTERNATIVE_KEY)
        if alt is not None and (alt not in options or alt == prediction):
            metadata.pop(ALTERNATIVE_KEY)
            notes.append(f"dropped invalid alternative '{alt}'")

        metadata.update({"role": self.role, "provider": self.llm_provider.name})
        if notes:
            metadata["normalized"] = notes
        return replace(decision, tag=tag, prediction=prediction, metadata=metadata)
