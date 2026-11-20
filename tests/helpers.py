import json
from collections.abc import Sequence
from typing import Any

from ai_project.llm.base import LLMProvider, LLMRequest, LLMResponse
from ai_project.protocol import Judgment, PXPMessage, PXPTag


class ScriptedProvider(LLMProvider):
    """Returns queued outputs in order (dicts are JSON-encoded); records every request."""

    name = "scripted"
    deterministic = True

    def __init__(self, outputs: Sequence[Any] = (), usage: dict[str, int] | None = None) -> None:
        self.outputs = list(outputs)
        self.requests: list[LLMRequest] = []
        self.usage = usage

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self.outputs:
            raise AssertionError("ScriptedProvider ran out of outputs")
        out = self.outputs.pop(0)
        if callable(out):
            out = out(request)
        text = out if isinstance(out, str) else json.dumps(out)
        return LLMResponse(text=text, usage=self.usage)


def msg(agent: str, tag: str, prediction: str, explanation: str = "because",
        judgment: tuple[bool, bool, bool] | None = None, **kw: Any) -> PXPMessage:
    return PXPMessage(
        agent_id=agent,
        tag=PXPTag.from_string(tag),
        prediction=prediction,
        explanation=explanation,
        confidence=kw.pop("confidence", 0.8),
        judgment=Judgment(*judgment) if judgment else None,
        **kw,
    )


def turn(prediction: str, agrees: bool | None = None, changed: bool | None = None,
         matches: bool | None = None, explanation: str = "because",
         rationale: str = "") -> dict[str, Any]:
    """A provider turn, as a model would return it."""
    data = {
        "prediction": prediction,
        "explanation": explanation,
        "confidence": 0.7,
        "explanation_agrees": agrees,
        "prediction_matches": matches,
        "changed": changed,
    }
    if rationale:
        data["rationale"] = rationale
    return data
