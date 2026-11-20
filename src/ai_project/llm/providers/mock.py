"""
Deterministic mock provider: explicit rules standing in for a model.

Used by the tests, the synthetic benchmark and the offline demo. It reads the
structured ``AgentContext`` and applies the rules below; the same context
always gives the same answer, in any process.

It answers with turns, like a model: a prediction, an explanation and the
judgments the agent procedure needs. Every mock message carries
``metadata["claims"]``: the option it supports and the options it rules out
(with reasons). Claims are the mock's explanation in machine-readable form,
and they define its judgments:

    AGREE(e1, e2)  = neither explanation supports an option the other rules out
    changed        = false (claims are fixed by the evidence, so only the
                     prediction moves, and the procedure detects that itself)

Beliefs (current output):

    with benefit scores     the option its scores rank highest among options it
    (the analyst)           can accept. It cannot check the other roles'
                            objections, so it does not move in a forward run.
    without scores          if the peer's prediction is acceptable to its own
    (critic, specialist)    evidence, that prediction; otherwise its first
                            acceptable option that nobody has ruled out on the
                            board (option order).

If the peer's prediction equals the agent's previous one and the
explanations agree, the agent answers with the peer's prediction (it
ratifies). Otherwise it answers with its belief. The agent procedure assigns
the tag (Algorithm 1), so mock messages always pass the grammar.

Reflection (counterfactual): for its own past message m, the agent may use
everything the full run made public. Its candidate is its best acceptable
option that nobody ruled out anywhere in the run, other than m's prediction,
judged against the peer and position it had at m. No such option: no
candidate. Confidence values label the rule; they are not calibrated.
"""

import json
from collections.abc import Iterable
from typing import Any

from ai_project.agents.models import AgentContext
from ai_project.blackboard.models import MessageRecord
from ai_project.llm.base import LLMProvider, LLMRequest, LLMResponse

CLAIMS = "claims"


class MockLLMProvider(LLMProvider):
    name = "deterministic-mock"
    deterministic = True

    def generate(self, request: LLMRequest) -> LLMResponse:
        ctx = request.context
        output = _reflect(ctx) if request.schema == "reflection" else _act(ctx)
        return LLMResponse(text=json.dumps(output, ensure_ascii=False), usage=None)


# ---------------------------------------------------------------- claims and judgments


def _acceptable(ctx: AgentContext) -> list[str]:
    return [o for o in ctx.options if o not in ctx.evidence.objections]


def _ranked(ctx: AgentContext, candidates: Iterable[str]) -> list[str]:
    scores = ctx.evidence.scores
    return sorted(candidates, key=lambda o: (-scores.get(o, 0.0), ctx.options.index(o)))


def _claims(ctx: AgentContext, prediction: str) -> dict[str, Any]:
    supports = prediction if prediction in _acceptable(ctx) else None
    return {"supports": supports, "objects": dict(ctx.evidence.objections)}


def _claims_of(record: MessageRecord) -> dict[str, Any]:
    claims = record.metadata.get(CLAIMS)
    if isinstance(claims, dict):
        return {"supports": claims.get("supports"), "objects": dict(claims.get("objects") or {})}
    return {"supports": record.prediction, "objects": {}}


def _agree(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return not (a["supports"] in b["objects"] or b["supports"] in a["objects"])


def _ruled_out(messages: Iterable[MessageRecord], exclude_agent: str) -> dict[str, str]:
    """Options other agents have ruled out on the board, with who ruled them out."""
    out: dict[str, str] = {}
    for m in messages:
        if m.agent_id != exclude_agent:
            for option in _claims_of(m)["objects"]:
                out.setdefault(option, m.agent_id)
    return out


def _explain(ctx: AgentContext, prediction: str, lead: str) -> str:
    parts = [lead]
    score = ctx.evidence.scores.get(prediction)
    if score is not None:
        parts.append(f"My benefit estimate for {prediction} is {score:.2f}.")
    for option, reason in ctx.evidence.objections.items():
        parts.append(f"{option} is ruled out: {reason}.")
    return " ".join(parts)


def _turn(ctx: AgentContext, prediction: str, lead: str, confidence: float,
          rule: str, peer: MessageRecord | None,
          own: tuple[str, dict[str, Any]] | None) -> dict[str, Any]:
    """A turn for ``prediction``, with AGREE judged against ``peer`` and ``own``."""
    claims = _claims(ctx, prediction)
    agrees = None
    if ctx.j > 1:
        _, ref_claims = own if own is not None else (prediction, claims)
        peer_claims = _claims_of(peer) if peer is not None else {"supports": None, "objects": {}}
        agrees = _agree(peer_claims, ref_claims)
    return {
        "prediction": prediction,
        "explanation": _explain(ctx, prediction, lead),
        "confidence": confidence,
        "explanation_agrees": agrees,
        "prediction_matches": None,  # options only: the procedure computes MATCH
        "changed": False if ctx.j > 1 else None,  # claims follow the prediction, so only it moves
        "metadata": {CLAIMS: claims, "rule": rule},
    }


def _own_reference(ctx: AgentContext) -> tuple[str, dict[str, Any]] | None:
    if ctx.own is None:
        return None
    return ctx.own.prediction, _claims(ctx, ctx.own.prediction)


# ---------------------------------------------------------------- forward rules


def _belief(ctx: AgentContext) -> tuple[str, str, str]:
    """(prediction, lead sentence, rule name)."""
    acceptable = _acceptable(ctx)
    if not acceptable:
        fallback = ctx.peer.prediction if ctx.peer else ctx.options[0]
        return fallback, "No option is acceptable under my evidence.", "nothing_acceptable"
    if ctx.evidence.scores:
        best = _ranked(ctx, acceptable)[0]
        return best, f"{best} has the highest benefit among the options I can accept.", "best_score"
    if ctx.peer is not None and ctx.peer.prediction in acceptable:
        p = ctx.peer.prediction
        return p, f"{p} passes all of my checks.", "accept_peer"
    ruled_out = _ruled_out(ctx.messages, ctx.agent_id)
    open_options = [o for o in acceptable if o not in ruled_out] or acceptable
    best = _ranked(ctx, open_options)[0]
    if ctx.peer is not None:
        lead = f"{ctx.peer.prediction} fails my checks; {best} passes them."
    else:
        lead = f"{best} passes all of my checks."
    return best, lead, "best_open"


def _act(ctx: AgentContext) -> dict[str, Any]:
    prediction, lead, rule = _belief(ctx)
    own = _own_reference(ctx)
    if ctx.peer is not None and ctx.j > 1:
        ref_prediction, ref_claims = own or (prediction, _claims(ctx, prediction))
        if (ctx.peer.prediction == ref_prediction
                and _agree(_claims_of(ctx.peer), ref_claims)):
            # Peer agrees with my previous position on both counts: RATIFY aligns with it.
            prediction = ctx.peer.prediction
            lead = f"I agree with {ctx.peer.agent_id} on {prediction} and its reasons."
            rule = "ratify"
    return _turn(ctx, prediction, lead, 0.8, rule, ctx.peer, own)


# ---------------------------------------------------------------- reflection


def _reflect(ctx: AgentContext) -> dict[str, Any]:
    target = ctx.reflect_on
    assert target is not None
    ruled_out = _ruled_out(ctx.hindsight, ctx.agent_id)
    candidates = [o for o in _acceptable(ctx)
                  if o not in ruled_out and o != target.prediction]
    if not candidates:
        return {"candidates": [], "lesson": ""}
    alt = _ranked(ctx, candidates)[0]
    objectors = sorted({ruled_out[target.prediction]} if target.prediction in ruled_out else set())
    by = f" by {', '.join(objectors)}" if objectors else ""
    lead = (f"In hindsight: {target.prediction} was ruled out{by} later in the run, "
            f"and {alt} was not.")
    candidate = _turn(ctx, alt, lead, 0.8, "hindsight", ctx.peer, _own_reference(ctx))
    candidate["rationale"] = (f"Replace {target.tag} {target.prediction} at message "
                              f"{target.iteration} with {alt}.")
    lesson = ("Options other agents ruled out in this session: "
              + "; ".join(f"{o} (by {a})" for o, a in sorted(ruled_out.items()))
              + f". Prefer {alt}, which no one ruled out.")
    return {"candidates": [candidate], "lesson": lesson}
