"""
Parsing provider output into turns.

Providers are asked for one JSON object, constrained by the schema in
``prompts/schemas`` where the provider supports it. The parser checks shape
and types only. Whether the resulting message is allowed is decided by the
agent procedure and the PXP grammar.
"""

import json
from typing import Any

from ai_project.agents.procedure import Turn
from ai_project.llm.base import LLMProviderError


class ParseError(LLMProviderError):
    """Provider output is not a well-formed turn."""


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


def _flag(data: dict[str, Any], key: str) -> bool | None:
    value = data.get(key)
    if value is None or isinstance(value, bool):
        return value
    raise ParseError(f"'{key}' must be true, false or null")


def parse_turn(data: dict[str, Any]) -> Turn:
    confidence = data.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ParseError("'confidence' must be a number") from exc
        if not 0.0 <= confidence <= 1.0:
            raise ParseError("'confidence' must be between 0 and 1")
    metadata = data.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ParseError("'metadata' must be an object")
    return Turn(
        prediction=_text(data, "prediction"),
        explanation=_text(data, "explanation"),
        confidence=confidence,
        explanation_agrees=_flag(data, "explanation_agrees"),
        prediction_matches=_flag(data, "prediction_matches"),
        changed=_flag(data, "changed"),
        rationale=str(data.get("rationale") or "").strip(),
        metadata=metadata,
    )


def parse_reflection(text: str) -> tuple[list[Turn], str]:
    """Candidate turns (possibly none) and the lesson."""
    data = extract_json(text)
    raw = data.get("candidates", [])
    if not isinstance(raw, list):
        raise ParseError("'candidates' must be a list")
    turns = []
    for item in raw:
        if not isinstance(item, dict):
            raise ParseError("each candidate must be an object")
        turns.append(parse_turn(item))
    lesson = data.get("lesson", "")
    if not isinstance(lesson, str):
        raise ParseError("'lesson' must be a string")
    return turns, lesson.strip()
