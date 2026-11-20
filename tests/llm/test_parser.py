import json

import pytest

from ai_project.llm.parser import ParseError, extract_json, parse_reflection, parse_turn
from tests.helpers import turn


def test_extracts_json_from_fences_and_prose():
    text = 'Sure!\n```json\n{"prediction": "A", "x": {"y": 1}}\n```\nDone.'
    assert extract_json(text) == {"prediction": "A", "x": {"y": 1}}


def test_skips_non_object_json():
    assert extract_json('[1, 2] then {"a": 1}') == {"a": 1}


def test_no_json():
    with pytest.raises(ParseError):
        extract_json("nothing")


def test_parse_turn():
    t = parse_turn(turn("B", agrees=True, changed=False, matches=None))
    assert (t.prediction, t.explanation_agrees, t.changed, t.prediction_matches) == \
           ("B", True, False, None)


@pytest.mark.parametrize("broken", [
    {"prediction": "", "explanation": "e"},
    {"prediction": "A"},
    {"prediction": "A", "explanation": "e", "confidence": "high"},
    {"prediction": "A", "explanation": "e", "confidence": 1.5},
    {"prediction": "A", "explanation": "e", "explanation_agrees": "yes"},
    {"prediction": "A", "explanation": "e", "metadata": []},
])
def test_parse_turn_rejects_bad_shapes(broken):
    with pytest.raises(ParseError):
        parse_turn(broken)


def test_parse_reflection():
    text = json.dumps({"candidates": [turn("B", rationale="r")], "lesson": "L"})
    candidates, lesson = parse_reflection(text)
    assert candidates[0].prediction == "B" and candidates[0].rationale == "r"
    assert lesson == "L"
    assert parse_reflection('{"candidates": [], "lesson": ""}') == ([], "")
    with pytest.raises(ParseError):
        parse_reflection('{"candidates": {}}')