"""
Agent: one role in the team, with a persona, private evidence, optional tools
and a decision provider.

    act(board)      Blackboard -> AgentContext -> prompt -> provider -> Turn
                    -> AGENT procedure (judgment, tag) -> grammar check -> Draft.
                    On a parse, procedure or grammar error the agent retries with
                    the errors in its prompt (``max_retries``).
    reflect(...)    the same pipeline in reflection mode: given the board as it
                    was at one of the agent's past messages and the whole run,
                    propose grammatical alternatives to that message.

The agent never writes to the board; the scheduler commits its drafts.
``lessons`` is the agent's prompt delta: lessons from counterfactual
interventions, added to its system prompt for the rest of the session.
"""

import copy
import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from ai_project.agents.models import ACT, REFLECT, AgentContext, Candidate, Draft, Reflection
from ai_project.agents.procedure import TurnError, assemble
from ai_project.benchmarks.base import Evidence, Task
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import MessageRecord
from ai_project.llm import prompts
from ai_project.llm.base import LLMProvider, LLMProviderError, LLMRequest
from ai_project.llm.parser import ParseError, extract_json, parse_reflection, parse_turn
from ai_project.llm.usage import UsageMeter
from ai_project.protocol.pxp import PXPMessage


class AgentError(Exception):
    """The agent could not produce a valid output."""


class Tool(Protocol):
    name: str
    description: str

    def __call__(self, arguments: Mapping[str, Any]) -> str: ...


class Agent:
    """
    Args:
        agent_id: Unique id on the board
        role: Role name from the prompt matrix
        task: The task (its reference answer is never shown)
        provider: Decision provider
        persona: Persona text for the system prompt
        evidence: Private evidence (default: the task's evidence for ``role``)
        team: All agent ids in the team, in order
        max_retries: Extra attempts after a parse or grammar error
        tools: Tools the agent may call before posting (name -> tool)
        max_tool_calls: Tool calls allowed per turn
        usage: Shared usage meter (a team usually shares one)
        phase: "live" or "sandbox" (for token accounting)
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        task: Task,
        provider: LLMProvider,
        persona: str = "",
        evidence: Evidence | None = None,
        team: Sequence[str] = (),
        max_retries: int = 1,
        tools: Mapping[str, Tool] | None = None,
        max_tool_calls: int = 0,
        usage: UsageMeter | None = None,
        phase: str = "live",
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.task = task
        self.provider = provider
        self.persona = persona
        self.evidence = evidence if evidence is not None else task.evidence_for(role)
        self.team = tuple(team) or (agent_id,)
        self.max_retries = max_retries
        self.tools = dict(tools or {})
        self.max_tool_calls = max_tool_calls if self.tools else 0
        self.usage = usage or UsageMeter()
        self.phase = phase
        self.lessons: list[str] = []

    # ------------------------------------------------------------------ acting

    def act(self, board: Blackboard) -> Draft:
        """Read the board and draft this agent's next message."""
        base = self.build_context(board)
        grammar_ctx = board.grammar_context(self.agent_id)
        rejected: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        feedback: tuple[str, ...] = ()
        attempt = 0
        while attempt <= self.max_retries:
            ctx = AgentContext(**{**base.__dict__, "feedback": feedback,
                                  "tool_results": tuple(tool_calls)})
            turn = None
            try:
                tools_left = len(tool_calls) < self.max_tool_calls
                data = extract_json(self._generate(ctx, "turn", tools=tools_left))
                if "tool" in data and tools_left:
                    tool_calls.append(self._call_tool(data))
                    continue  # tool calls do not use up attempts
                turn = parse_turn(data)
                message = assemble(self.agent_id, turn, grammar_ctx, board.grammar.reject_after)
            except (ParseError, TurnError) as exc:
                rejected.append({"attempt": attempt, "output": turn.to_dict() if turn else None,
                                 "errors": [str(exc)]})
                feedback = (str(exc),)
                attempt += 1
                continue
            except LLMProviderError as exc:
                return Draft(None, rejected, error=f"provider error: {exc}", tool_calls=tool_calls)
            violations = board.grammar.check(message, grammar_ctx)
            if not violations:
                self._stamp(message, tool_calls)
                return Draft(message, rejected, tool_calls=tool_calls)
            errors = [str(v) for v in violations]
            rejected.append({"attempt": attempt, "output": turn.to_dict(), "errors": errors})
            feedback = tuple(errors)
            attempt += 1
        return Draft(None, rejected, error=f"no grammatical message after {attempt} attempt(s)",
                     tool_calls=tool_calls)

    def build_context(self, board: Blackboard) -> AgentContext:
        state = board.get_state()
        grammar_ctx = board.grammar_context(self.agent_id)
        return AgentContext(
            agent_id=self.agent_id,
            role=self.role,
            task=self.task,
            evidence=self.evidence,
            j=grammar_ctx.j,
            peer=board.peer_message(self.agent_id),
            own=grammar_ctx.own,
            messages=tuple(board.get_messages()),
            lessons=tuple(self.lessons),
            weight=state.weights.get(self.agent_id, 1.0),
            reject_after=board.grammar.reject_after,
            mode=ACT,
        )

    # ------------------------------------------------------------------ reflection

    def reflect(
        self,
        board_at_target: Blackboard,
        target: MessageRecord,
        hindsight: Sequence[MessageRecord],
        max_candidates: int = 3,
    ) -> tuple[Reflection, list[dict[str, Any]]]:
        """
        Propose alternatives to one of this agent's past messages.

        Args:
            board_at_target: The board rebuilt up to just before ``target``
            target: The agent's own past message
            hindsight: Every message of the run

        Returns:
            The reflection (grammatical, genuinely different candidates only)
            and the rejected candidates with their errors
        """
        if target.agent_id != self.agent_id:
            raise AgentError(f"{self.agent_id} can only reflect on its own messages")
        base = self.build_context(board_at_target)
        ctx = AgentContext(**{**base.__dict__, "mode": REFLECT, "reflect_on": target,
                              "hindsight": tuple(hindsight)})
        grammar_ctx = board_at_target.grammar_context(self.agent_id)
        k = board_at_target.grammar.reject_after
        rejected: list[dict[str, Any]] = []
        candidates: list[Candidate] = []
        lesson = ""
        for attempt in range(self.max_retries + 1):
            try:
                raw = self._generate(ctx, "reflection", max_candidates=max_candidates)
                turns, lesson = parse_reflection(raw)
            except ParseError as exc:
                rejected.append({"attempt": attempt, "output": None, "errors": [str(exc)]})
                ctx = AgentContext(**{**ctx.__dict__, "feedback": (str(exc),)})
                continue
            except LLMProviderError as exc:
                raise AgentError(f"{self.agent_id}: provider error: {exc}") from exc
            for turn in turns[:max_candidates]:
                try:
                    message = assemble(self.agent_id, turn, grammar_ctx, k)
                except TurnError as exc:
                    rejected.append({"attempt": attempt, "output": turn.to_dict(),
                                     "errors": [str(exc)]})
                    continue
                violations = board_at_target.grammar.check(message, grammar_ctx)
                if violations:
                    rejected.append({"attempt": attempt, "output": turn.to_dict(),
                                     "errors": [str(v) for v in violations]})
                elif not _same(message, target) and not any(
                        _same(message, c.message) for c in candidates):
                    candidates.append(Candidate(message, turn.rationale))
            break
        return Reflection(target=target, candidates=tuple(candidates), lesson=lesson), rejected

    # ------------------------------------------------------------------ helpers

    def clone(self, phase: str = "sandbox") -> "Agent":
        """A copy for a counterfactual sandbox: same provider and evidence, copied lessons."""
        twin = copy.copy(self)
        twin.lessons = list(self.lessons)
        twin.phase = phase
        return twin

    def describe(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "role": self.role, "provider": self.provider.name,
                "tools": sorted(self.tools)}

    def render(self, ctx: AgentContext, max_candidates: int = 3) -> tuple[str, str]:
        """(system prompt, user prompt) for a context."""
        system = prompts.render_system(ctx, self.persona, self.team)
        if ctx.mode == REFLECT:
            return system, prompts.render_reflect(ctx, max_candidates)
        return system, prompts.render_act(ctx)

    def _stamp(self, message: PXPMessage, tool_calls: list[dict[str, Any]]) -> None:
        message.metadata.setdefault("role", self.role)
        message.metadata.setdefault("provider", self.provider.name)
        if tool_calls:
            message.metadata["tool_calls"] = len(tool_calls)

    def _generate(self, ctx: AgentContext, schema: str, max_candidates: int = 3,
                  tools: bool = False) -> str:
        system, prompt = self.render(ctx, max_candidates)
        if self.tools and ctx.mode == ACT:
            prompt += _tool_instructions(self.tools, self.max_tool_calls - len(ctx.tool_results))
        request = LLMRequest(
            prompt=prompt, context=ctx, schema=schema, system=system, phase=self.phase,
            json_schema=prompts.output_schema(schema, ctx.options, max_candidates,
                                              tools=tools and bool(self.tools)),
        )
        response = self.provider.generate(request)
        self.usage.add(self.phase, response.usage, response.cached)
        return response.text

    def _call_tool(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("tool"))
        arguments = data.get("arguments") or {}
        tool = self.tools.get(name)
        if tool is None:
            result = f"error: unknown tool '{name}'. Available: {sorted(self.tools)}"
        else:
            try:
                result = tool(arguments)
            except Exception as exc:  # tool failures are reported back to the agent
                result = f"error: {type(exc).__name__}: {exc}"
        return {"tool": name, "arguments": arguments, "result": result}


def _same(message: PXPMessage, other: MessageRecord | PXPMessage) -> bool:
    tag = other.tag if isinstance(other.tag, str) else other.tag.value
    return (message.tag.value == tag and message.prediction == other.prediction
            and message.explanation == other.explanation)


def _tool_instructions(tools: Mapping[str, Tool], remaining: int) -> str:
    if remaining <= 0:
        return "\n\nYou have used all tool calls for this turn; answer now."
    listing = "\n".join(f"- {t.name}: {t.description}" for t in tools.values())
    return (
        f"\n\n## Tools ({remaining} call(s) left this turn)\n{listing}\n"
        'To call a tool instead of answering, return {"tool": "<name>", "arguments": {...}}. '
        "Answer once you have what you need.\n"
        + json.dumps({"tools": sorted(tools)})
    )
