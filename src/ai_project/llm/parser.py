"""
Parsing provider output.

Providers are asked for one JSON object (constrained by the JSON schemas in
``prompts/schemas`` where the provider supports it). The parser only checks
shape and types; whether a message is allowed is the PXP grammar's job.
"""

import json
from typing import Any

from ai_project.agents.models import AgentOutput, Candidate
from ai_project.llm.base import LLMProviderError
from ai_project.protocol.pxp import Judgment, PXPTag


class ParseError(LLMProviderError):
    """Provider output is not a well-formed decision."""


def extract_json(text: str) -> dict[str, Any]:
    """The first top-level JSON object in ``text`` (markdown fences and prose are skipped)."""
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    raise ParseError(f"No JSON object in provider output: {text[:200]!r}")


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ParseError(f"'{key}' must be a non-empty string")
    return value.strip()


def _judgment(data: dict[str, Any]) -> Judgment | None:
    raw = data.get("judgment")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ParseError("'judgment' must be an object or null")
    try:
        return Judgment(
            prediction_matches=_bool(raw, "prediction_matches"),
            explanation_agrees=_bool(raw, "explanation_agrees"),
            changed=_bool(raw, "changed"),
        )
    except KeyError as exc:
        raise ParseError(f"judgment is missing {exc}") from exc


def _bool(data: dict[str, Any], key: str) -> bool:
    value = data[key]
    if not isinstance(value, bool):
        raise ParseError(f"judgment.{key} must be true or false")
    return value


def parse_output(data: dict[str, Any]) -> AgentOutput:
    try:
        tag = PXPTag.from_string(data.get("tag", ""))
    except ValueError as exc:
        raise ParseError(str(exc)) from exc
    confidence = data.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ParseError("'confidence' must be a number") from exc
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ParseError("'metadata' must be an object")
    return AgentOutput(
        tag=tag,
        prediction=_text(data, "prediction"),
        explanation=_text(data, "explanation"),
        confidence=confidence,
        judgment=_judgment(data),
        metadata=metadata,
    )


def parse_act(text: str) -> AgentOutput:
    return parse_output(extract_json(text))


def parse_reflection(text: str) -> tuple[list[Candidate], str]:
    """Candidates (possibly none) and the lesson."""
    data = extract_json(text)
    raw = data.get("candidates", [])
    if not isinstance(raw, list):
        raise ParseError("'candidates' must be a list")
    candidates = []
    for item in raw:
        if not isinstance(item, dict):
            raise ParseError("each candidate must be an object")
        candidates.append(Candidate(parse_output(item), str(item.get("rationale", "")).strip()))
    lesson = data.get("lesson", "")
    if not isinstance(lesson, str):
        raise ParseError("'lesson' must be a string")
    return candidates, lesson.strip()
