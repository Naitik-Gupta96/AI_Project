"""The web UI's reducer is tested against web/src/__fixtures__/session.json; keep it truthful."""

import json
from pathlib import Path

from ai_project.blackboard import Blackboard, BoardEvent

FIXTURE = Path(__file__).resolve().parents[2] / "web" / "src" / "__fixtures__" / "session.json"


def test_fixture_states_match_the_python_board():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    board = Blackboard.from_events([BoardEvent.from_dict(e) for e in data["events"]])
    assert len(data["states"]) == board.version + 1
    for version, state in enumerate(data["states"]):
        assert board.state_at(version).to_dict() == state, f"state differs at version {version}"


def test_fixture_covers_every_state_changing_event():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    kinds = {e["kind"] for e in data["events"]}
    assert {"task", "message", "status", "weight", "context_revision", "intervention",
            "activation"} <= kinds
