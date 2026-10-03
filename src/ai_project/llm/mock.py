"""
Deterministic mock provider: explicit role rules standing in for a model.

This is not a language model. It reads the structured ``AgentContext`` (the
same information the prompt contains) and applies the rules below. Each
output is a pure function of the context: no randomness, no hashing, no
hidden state. The same board therefore always yields the same message, in
any process.

Notation: P is the standing proposal; "acceptable" means the agent's own
evidence has no objection; candidates are ranked by the agent's own scores,
ties broken by option order.

Forward rules (first match wins):

    analyst     no P               -> RATIFY best acceptable option not yet refuted
                                      (REJECT if there is none)
                P not acceptable   -> REFUTE P, citing the reason
                otherwise          -> RATIFY P
    critic      no P               -> RATIFY best acceptable option
                P not acceptable   -> REFUTE P, citing the constraint it breaks.
                                      The critic reports violations only; it does
                                      not volunteer an alternative.
                otherwise          -> RATIFY P
    specialist  latest message objects to P and names an acceptable
                alternative X      -> REVISE to X
                no P               -> RATIFY best acceptable option
                P not acceptable   -> REFUTE P, citing the domain limit
                otherwise          -> RATIFY P

Counterfactual reflection: after a deadlock, an agent is shown the whole
run and one of its own past messages, and asked what it would have said
instead. It may use what the run made public (which options were refuted)
plus its own evidence, never other agents' private evidence. Y is its best
acceptable option that nobody refuted in the run.

    analyst     own opening proposal X was later refuted -> RATIFY Y instead
    critic      own REFUTE X named no alternative        -> same REFUTE X, naming Y
    specialist  own REFUTE X / RATIFY X, X was refuted   -> REVISE to Y instead
    otherwise / no Y                                     -> no change

Confidence values are fixed per rule (they label the rule, they are not
calibrated probabilities).
"""

import json
from typing import Any

from ai_project.agents.models import ALTERNATIVE_KEY, AgentContext
from ai_project.blackboard.models import HistoryEvent
from ai_project.llm.base import LLMProvider, LLMRequest, LLMResponse
from ai_project.protocol.pxp import PXPTag

RATIFY, REVISE, REFUTE, REJECT = (t.value for t in PXPTag)


class MockLLMProvider(LLMProvider):
    """Rule-based deterministic provider (see module docstring for the rules)."""

    name = "deterministic-mock"
    deterministic = True

    def generate(self, request: LLMRequest) -> LLMResponse:
        ctx = request.context
        if ctx.is_reflection:
            output = _reflect(ctx)
        else:
            output = _ROLE_RULES.get(ctx.role, _generic)(ctx)
        output.setdefault("metadata", {})
        return LLMResponse(text=json.dumps(output, ensure_ascii=False), usage=None)


# ---------------------------------------------------------------- helpers


def _decision(tag: str, prediction: str, explanation: str, confidence: float, rule: str,
              **metadata: Any) -> dict[str, Any]:
    return {
        "tag": tag,
        "prediction": prediction,
        "explanation": explanation,
        "confidence": confidence,
        "metadata": {"rule": rule, **metadata},
    }


def _refuted(history: tuple[HistoryEvent, ...]) -> set[str]:
    """Options refuted on the board so far."""
    return {e.prediction for e in history if e.tag == REFUTE}


def _ranked(ctx: AgentContext, exclude: set[str]) -> list[str]:
    """Acceptable options not in ``exclude``, best first by own score, then option order."""
    scores = ctx.evidence.scores
    candidates = [o for o in ctx.options if o not in ctx.evidence.objections and o not in exclude]
    return sorted(candidates, key=lambda o: (-scores.get(o, 0.0), ctx.options.index(o)))


def _score_note(ctx: AgentContext, option: str) -> str:
    score = ctx.evidence.scores.get(option)
    return f" (estimated benefit {score:.2f})" if score is not None else ""


def _open(ctx: AgentContext, rule: str = "open") -> dict[str, Any]:
    ranked = _ranked(ctx, _refuted(ctx.history))
    if not ranked:
        return _decision(
            REJECT,
            "No acceptable option",
            "Every option is either ruled out by my evidence or already refuted.",
            0.8,
            rule,
        )
    choice = ranked[0]
    return _decision(
        RATIFY,
        choice,
        f"Opening proposal: {choice}{_score_note(ctx, choice)} is the best option "
        f"I can accept for this task.",
        0.8,
        rule,
    )


def _refute(ctx: AgentContext, proposal: str) -> dict[str, Any]:
    reason = ctx.evidence.objections[proposal]
    return _decision(REFUTE, proposal, f"{proposal} is unacceptable: {reason}.", 0.85, "object")


def _endorse(ctx: AgentContext, proposal: str, note: str) -> dict[str, Any]:
    return _decision(RATIFY, proposal, note, 0.75, "endorse")


# ---------------------------------------------------------------- forward rules


def _analyst(ctx: AgentContext) -> dict[str, Any]:
    p = ctx.proposal
    if p is None:
        return _open(ctx)
    if p in ctx.evidence.objections:
        return _refute(ctx, p)
    top = _ranked(ctx, set())
    if top and top[0] == p:
        note = f"{p} is my top-ranked option{_score_note(ctx, p)}."
    else:
        note = f"{p} is acceptable{_score_note(ctx, p)}; I have no objection to it."
    return _endorse(ctx, p, note)


def _critic(ctx: AgentContext) -> dict[str, Any]:
    p = ctx.proposal
    if p is None:
        return _open(ctx)
    if p in ctx.evidence.objections:
        return _refute(ctx, p)
    return _endorse(ctx, p, f"{p} passes all of my constraint checks.")


def _specialist(ctx: AgentContext) -> dict[str, Any]:
    p, latest = ctx.proposal, ctx.latest
    if latest is not None and latest.tag in (REFUTE, REJECT):
        alt = latest.metadata.get(ALTERNATIVE_KEY)
        if alt and alt != p and alt in ctx.options and alt not in ctx.evidence.objections:
            return _decision(
                REVISE,
                alt,
                f"{latest.agent_id} showed {p} is flawed and named {alt}; {alt} passes my "
                f"domain checks, so I revise the proposal to {alt}.",
                0.8,
                "adopt_alternative",
                adopted_from=latest.agent_id,
            )
    if p is None:
        return _open(ctx)
    if p in ctx.evidence.objections:
        return _refute(ctx, p)
    return _endorse(ctx, p, f"{p} raises no issue in my domain checks.")


def _generic(ctx: AgentContext) -> dict[str, Any]:
    """Fallback for unknown roles: endorse what is acceptable, refute what is not."""
    return _critic(ctx)


_ROLE_RULES = {"analyst": _analyst, "critic": _critic, "specialist": _specialist}


# ---------------------------------------------------------------- reflection


def _no_change(reason: str) -> dict[str, Any]:
    return {"no_change": True, "explanation": reason}


def _reflect(ctx: AgentContext) -> dict[str, Any]:
    own = ctx.reflect_on
    assert own is not None
    refuted = _refuted(ctx.history)
    ranked = _ranked(ctx, refuted | {own.prediction})
    alt = ranked[0] if ranked else None
    refuters = sorted({e.agent_id for e in ctx.history if e.tag == REFUTE
                       and e.prediction == own.prediction})
    by = f" by {', '.join(refuters)}" if refuters else ""

    if ctx.role == "analyst":
        if own.tag in (RATIFY, REVISE) and own.prediction in refuted and alt:
            return _decision(
                RATIFY,
                alt,
                f"In hindsight: {own.prediction} was refuted{by} later in the run. "
                f"Opening with {alt}{_score_note(ctx, alt)} avoids that objection.",
                0.8,
                "hindsight_reopen",
            )
    elif ctx.role == "critic":
        if own.tag == REFUTE and not own.metadata.get(ALTERNATIVE_KEY) and alt:
            return _decision(
                REFUTE,
                own.prediction,
                f"{own.explanation} {alt} passes my checks and is an acceptable alternative.",
                own.confidence if own.confidence is not None else 0.85,
                "hindsight_name_alternative",
                **{ALTERNATIVE_KEY: alt},
            )
    elif ctx.role == "specialist":
        if own.tag in (REFUTE, RATIFY) and own.prediction in refuted and alt:
            return _decision(
                REVISE,
                alt,
                f"In hindsight: {own.prediction} was refuted{by}. Instead of "
                f"{own.tag} {own.prediction} I propose {alt}, which passes my domain checks "
                f"and was not refuted.",
                0.8,
                "hindsight_propose",
            )
    if alt is None:
        return _no_change("No acceptable option was left unrefuted, so a different message "
                          "would not have helped.")
    return _no_change(f"My {own.tag} {own.prediction} at step {own.iteration} is not one "
                      f"my reflection rules would change.")
