"""
Write web/src/__fixtures__/session.json: the event log of one demo session and
the board state after every event, as the Python Blackboard computes them.

The web UI's tests replay the same events through its own reducer and must get
the same states; tests/server/test_ui_fixture.py checks that the committed
fixture still matches the Python side. Regenerate after changing event shapes:

    python scripts/export_ui_fixture.py
"""

import json
from pathlib import Path

from ai_project.agents import build_team
from ai_project.benchmarks import SyntheticBenchmark, architecture_task
from ai_project.llm.providers.mock import MockLLMProvider
from ai_project.session import Session

FIXTURE = Path(__file__).resolve().parents[1] / "web" / "src" / "__fixtures__" / "session.json"


def build() -> dict:
    task = architecture_task()
    session = Session(task, build_team(task, MockLLMProvider()), ["analyst"],
                      session_id="fixture", benchmark=SyntheticBenchmark())
    session.run()
    board = session.board
    return {
        "events": [e.to_dict() for e in board.get_events()],
        "states": [board.state_at(v).to_dict() for v in range(board.version + 1)],
    }


def main() -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE}")  # noqa: T201


if __name__ == "__main__":
    main()
