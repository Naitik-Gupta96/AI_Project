import pytest

from ai_project.llm.parser import ParseError, extract_json, parse_act, parse_reflection
from ai_project.protocol import Judgment, PXPTag
from tests.helpers import output


def test_extracts_json_from_fences_and_prose():
    text = 'Sure!\n```json\n{"tag": "INIT", "x": {"y": 1}}\n```\nDone.'
    assert extract_json(text) == {"tag": "INIT", "x": {"y": 1}}


def test_skips_non_object_json():
    assert extract_json('[1, 2] then {"a": 1}') == {"a": 1}


def test_no_json():
    with pytest.raises(ParseError):
        extract_json("nothing")


def test_parse_act():
    import json
    out = parse_act(json.dumps(output("REVISE", "B", (False, True, True))))
    assert out.tag == PXPTag.REVISE
    assert out.judgment == Judgment(False, True, True)


@pytest.mark.parametrize("broken", [
    {"tag": "MAYBE", "prediction": "A", "explanation": "e"},
    {"tag": "INIT", "prediction": "", "explanation": "e"},
    {"tag": "INIT", "prediction": "A"},
    {"tag": "INIT", "prediction": "A", "explanation": "e", "confidence": "high"},
    {"tag": "RATIFY", "prediction": "A", "explanation": "e",
     "judgment": {"prediction_matches": "yes", "explanation_agrees": True, "changed": False}},
    {"tag": "RATIFY", "prediction": "A", "explanation": "e", "judgment": {"changed": False}},
])
def test_parse_act_rejects_bad_shapes(broken):
    import json
    with pytest.raises(ParseError):
        parse_act(json.dumps(broken))


def test_parse_reflection():
    import json
    text = json.dumps({"candidates": [{**output("INIT", "B"), "rationale": "r"}], "lesson": "L"})
    candidates, lesson = parse_reflection(text)
    assert candidates[0].output.prediction == "B" and candidates[0].rationale == "r"
    assert lesson == "L"
    assert parse_reflection('{"candidates": [], "lesson": ""}') == ([], "")
    with pytest.raises(ParseError):
        parse_reflection('{"candidates": {}}')
