"""
Prompt matrix: personas per (domain, role), JSON output schemas, and the
templates every agent prompt is rendered from.

    prompts/matrix.json         domain -> ordered roles, each with a persona file and a schema
    prompts/personas/<domain>/  one persona per role
    prompts/schemas/            JSON Schemas for provider output (and for constrained decoding)
    prompts/system.md, act.md, reflect.md   templates ($placeholders)
"""

import copy
import json
from dataclasses import dataclass
from functools import cache, lru_cache
from importlib import resources
from string import Template
from typing import Any

from ai_project.agents.models import AgentContext
from ai_project.blackboard.models import MessageRecord
from ai_project.protocol.grammar import Position


@dataclass(frozen=True)
class RoleSpec:
    role: str
    persona: str
    schema: str


def _read(path: str) -> str:
    return resources.files("ai_project.llm").joinpath("prompts", path).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def matrix() -> dict[str, Any]:
    return json.loads(_read("matrix.json"))


def domains() -> list[str]:
    return list(matrix())


def roles(domain: str) -> list[RoleSpec]:
    try:
        entry = matrix()[domain]
    except KeyError:
        raise KeyError(f"No personas for domain '{domain}'. Known: {domains()}") from None
    return [RoleSpec(r["role"], _read(r["persona"]).strip(), r["schema"]) for r in entry["roles"]]


@cache
def schema(name: str) -> dict[str, Any]:
    return json.loads(_read(f"schemas/{name}.schema.json"))


TOOL_CALL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool", "arguments"],
    "properties": {"tool": {"type": "string"}, "arguments": {"type": "object"}},
}


def output_schema(name: str, options: tuple[str, ...] = (), max_candidates: int = 3,
                  tools: bool = False, replying: bool = False) -> dict[str, Any]:
    """
    The base schema specialised for one request: with listed options the
    prediction is an enum of them and ``prediction_matches`` is dropped (the
    procedure computes MATCH); when the message answers a peer (``replying``,
    any message after the first) the judgments the procedure requires cannot
    be null; with tools a tool call is also allowed.
    """
    out = copy.deepcopy(schema(name))
    item = out["properties"]["candidates"]["items"] if name == "reflection" else out
    if options:
        item["properties"]["prediction"] = {"type": "string", "enum": list(options)}
        del item["properties"]["prediction_matches"]
        item["required"].remove("prediction_matches")
    if replying:
        for key in ("explanation_agrees", "prediction_matches"):
            if key in item["properties"]:
                item["properties"][key] = {"type": "boolean"}
    if name == "reflection":
        out["properties"]["candidates"]["maxItems"] = max_candidates
    if tools:
        title = out.pop("title", name)
        out = {"title": title, "anyOf": [out, TOOL_CALL_SCHEMA]}
    return out


@cache
def template(name: str) -> Template:
    return Template(_read(name))


# ---------------------------------------------------------------- rendering


HISTORY_CHARS = 240  # per field, for messages other than the peer and own position


def _clip(text: str, limit: int | None) -> str:
    if limit is None or len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …"


def format_message(m: MessageRecord, limit: int | None = None) -> str:
    return (f"#{m.iteration} {m.agent_id} {m.tag} \"{_clip(m.prediction, limit)}\": "
            f"{_clip(m.explanation, limit)}")


def _history(messages: tuple[MessageRecord, ...]) -> str:
    """The log, with long messages clipped (the peer message and own position are shown in full)."""
    return "\n".join(format_message(m, HISTORY_CHARS) for m in messages) or "(no messages yet)"


def _position(p: Position | None, first_reply_note: str) -> str:
    if p is None:
        return first_reply_note
    return f"prediction \"{p.prediction}\": {p.explanation}"


def _evidence(ctx: AgentContext) -> str:
    lines = [f"- benefit estimate for {o}: {s:.2f}" for o, s in ctx.evidence.scores.items()]
    lines += [f"- {o} is ruled out: {r}" for o, r in ctx.evidence.objections.items()]
    return "\n".join(lines) or "- (none beyond the task itself)"


def _options(ctx: AgentContext) -> str:
    if ctx.options:
        return "Your prediction must be exactly one of: " + ", ".join(ctx.options) + "\n"
    return ("The prediction is a free-form answer. "
            + (ctx.task.answer_format or "State it completely and concisely.") + "\n")


def _context(ctx: AgentContext) -> str:
    if not ctx.task.context:
        return ""
    lines = [f"- {k}: {v}" for k, v in ctx.task.context.items()]
    return "## Context\n" + "\n".join(lines) + "\n"


def _feedback(ctx: AgentContext) -> str:
    if not ctx.feedback:
        return ""
    return ("\n## Your previous attempt was rejected\n"
            + "\n".join(f"- {f}" for f in ctx.feedback) + "\nFix these and answer again.\n")


def _tools(ctx: AgentContext) -> str:
    if not ctx.tool_results:
        return ""
    lines = [f"- {r.get('tool')}({json.dumps(r.get('arguments'))}) -> {r.get('result')}"
             for r in ctx.tool_results]
    return "\n## Tool results from this turn\n" + "\n".join(lines) + "\n"


def render_system(ctx: AgentContext, persona: str, team: tuple[str, ...]) -> str:
    lessons = ""
    if ctx.lessons:
        lessons = ("\nLessons from your earlier counterfactual reflections in this session:\n"
                   + "\n".join(f"- {lesson}" for lesson in ctx.lessons))
    return template("system.md").substitute(
        agent_id=ctx.agent_id,
        team_size=len(team),
        team=", ".join(team),
        persona=persona,
        weight=f"{ctx.weight:.2f}",
        lessons=lessons,
    ).strip()


def _judgments(ctx: AgentContext, subject: str) -> str:
    """The judgment questions for a turn (``subject``: "your answer" or "each candidate")."""
    if ctx.j == 1:
        return ("This is message 1, which opens the session. Set explanation_agrees, "
                "prediction_matches and changed to null.")
    lines = [
        "- explanation_agrees: compare the PEER message's explanation with YOUR PREVIOUS "
        "position's explanation. true if the peer's reasoning is consistent with yours, false if "
        "it contradicts it or rests on something you reject.",
    ]
    if not ctx.options:
        lines.append(
            "- prediction_matches: true if the peer's answer means the same as YOUR PREVIOUS "
            "answer (wording may differ), else false.")
    if ctx.own is None:
        lines.append("- changed: false. This is your first reply, so your previous position is "
                     f"{subject} itself.")
    else:
        lines.append(f"- changed: true if {subject} departs from your previous position "
                     "(a different answer, or reasoning you would now state differently).")
    ratify = ("If the peer's answer is the same as your previous answer and you agree with its "
              "explanation, you are ratifying it: use the peer's answer as your prediction.")
    return "\n".join(lines) + "\n" + ratify


def _tag_rule(ctx: AgentContext) -> str:
    return (f"The protocol assigns the tag from your judgments (k = {ctx.reject_after}): message 1 "
            "is INIT; previous answer matches the peer's and you agree with its explanation -> "
            "RATIFY; exactly one of the two -> REVISE if changed, else REFUTE; neither -> REJECT "
            f"after message {ctx.reject_after}, before that REVISE if changed, else REFUTE.")


def render_act(ctx: AgentContext) -> str:
    peer = (format_message(ctx.peer) if ctx.peer else "(none: you are writing message 1)")
    own = _position(ctx.own, "(none yet: on this first reply, your previous position is your "
                             "new answer)")
    return template("act.md").substitute(
        task=ctx.task.question,
        options_block=_options(ctx),
        context_block=_context(ctx),
        evidence=_evidence(ctx),
        j=ctx.j,
        history=_history(ctx.messages),
        peer=peer,
        own=own,
        tool_block=_tools(ctx),
        judgments=_judgments(ctx, "your answer"),
        tag_rule=_tag_rule(ctx),
        feedback=_feedback(ctx),
    ).strip()


def render_reflect(ctx: AgentContext, max_candidates: int) -> str:
    assert ctx.reflect_on is not None
    peer = format_message(ctx.peer) if ctx.peer else "(none: it was message 1)"
    own = _position(ctx.own, "(none: it was your first reply, so your previous position is the "
                             "candidate itself)")
    return template("reflect.md").substitute(
        task=ctx.task.question,
        options_block=_options(ctx),
        context_block=_context(ctx),
        evidence=_evidence(ctx),
        hindsight=_history(ctx.hindsight),
        j=ctx.j,
        target=format_message(ctx.reflect_on),
        peer=peer,
        own=own,
        max_candidates=max_candidates,
        judgments=_judgments(ctx, "the candidate"),
        tag_rule=_tag_rule(ctx),
        feedback=_feedback(ctx),
    ).strip()
