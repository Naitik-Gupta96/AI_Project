import threading
import time

import pytest

from ai_project.agents import Agent, Draft
from ai_project.benchmarks import Task
from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.blackboard.models import ACTIVATION, COLLISION, FORMAT_ERROR, TOOL
from ai_project.scheduler import (
    STOP_CONSENSUS,
    STOP_DEADLOCK,
    STOP_FAILED,
    STOP_MAX_MESSAGES,
    STOP_STOPPED,
    Scheduler,
    SchedulerConfig,
    SchedulerError,
)
from tests.helpers import ScriptedProvider, turn


def demo_board(task, team):
    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata(), agents=[a.agent_id for a in team])
    return board


def test_demo_task_deadlocks_on_reject(demo_task, mock_team):
    team = mock_team(demo_task)
    board = demo_board(demo_task, team)
    result = Scheduler(board, team).run()
    assert result.status == "DEADLOCK"
    assert result.stop_reason == STOP_DEADLOCK
    assert result.deadlock.rule == "reject"
    assert [(m.agent_id, m.tag, m.prediction) for m in board.get_messages()] == [
        ("analyst", "INIT", "Option A"),
        ("critic", "REFUTE", "Option B"),
        ("specialist", "RATIFY", "Option B"),
        ("analyst", "REJECT", "Option A"),
    ]
    assert sum(1 for e in board.get_events() if e.kind == ACTIVATION) == 4


def test_agreeable_task_reaches_consensus(mock_team):
    task = Task("t", "synthetic", "Pick", ("Option A", "Option B"), domain="synthetic")
    team = mock_team(task)
    board = demo_board(task, team)
    result = Scheduler(board, team).run()
    assert result.stop_reason == STOP_CONSENSUS
    assert result.final_prediction == "Option A"
    assert board.status == BlackboardStatus.CONSENSUS


def test_message_budget(demo_task, mock_team):
    team = mock_team(demo_task)
    board = demo_board(demo_task, team)
    result = Scheduler(board, team, config=SchedulerConfig(max_messages=2)).run()
    assert result.stop_reason == STOP_MAX_MESSAGES
    assert result.messages == 2
    assert board.status == BlackboardStatus.RUNNING


def scripted_team(task, outputs_by_agent, **kw):
    ids = list(outputs_by_agent)
    return [Agent(a, a, task, ScriptedProvider(outs), team=ids, **kw)
            for a, outs in outputs_by_agent.items()]


TWO = Task("t2", "synthetic", "Pick", ("A", "B"), domain="synthetic")


def test_agent_that_never_produces_a_valid_message_fails_the_session():
    team = scripted_team(TWO, {"a": ["garbage"] * 10, "b": []}, max_retries=0)
    board = demo_board(TWO, team)
    result = Scheduler(board, team, config=SchedulerConfig(max_failed_turns=3)).run()
    assert result.stop_reason == STOP_FAILED
    assert board.status == BlackboardStatus.FAILED
    assert "a produced no grammatical message" in result.error
    assert sum(1 for e in board.get_events() if e.kind == FORMAT_ERROR) == 3


def test_recovered_format_error_is_recorded():
    team = scripted_team(TWO, {
        "a": [turn("Z"), turn("A")],  # first attempt is not one of the options
        "b": [turn("A", agrees=True)],
    })
    board = demo_board(TWO, team)
    result = Scheduler(board, team, config=SchedulerConfig(max_messages=2)).run()
    assert result.messages == 2
    errors = [e for e in board.get_events() if e.kind == FORMAT_ERROR]
    assert len(errors) == 1 and errors[0].data["recovered"]


class SlowAgent:
    """Drafts a valid reply after a delay; used to force concurrent drafts."""

    def __init__(self, agent_id, delay):
        self.agent_id = self.role = agent_id
        self.delay = delay

    def act(self, board):
        from tests.helpers import msg
        ctx = board.grammar_context(self.agent_id)
        time.sleep(self.delay)
        if ctx.j == 1:
            return Draft(msg(self.agent_id, "INIT", "A"))
        changed = ctx.own is not None and ctx.own.prediction != "A"
        return Draft(msg(self.agent_id, "RATIFY", "A", judgment=(True, True, changed)))


def test_parallel_drafts_collide_and_only_one_lands():
    agents = [SlowAgent("x", 0.05), SlowAgent("y", 0.0), SlowAgent("z", 0.0)]
    board = Blackboard()
    board.initialize_task("Pick", {"options": ["A"]}, agents=["x", "y", "z"])
    scheduler = Scheduler(board, agents, config=SchedulerConfig(max_concurrent_agents=3))
    result = scheduler.run()
    assert result.collisions >= 2
    assert sum(1 for e in board.get_events() if e.kind == COLLISION) == result.collisions
    assert result.status == "CONSENSUS"
    assert [m.iteration for m in board.get_messages()] == list(range(1, result.messages + 1))


def test_pause_step_and_stop(demo_task, mock_team):
    team = mock_team(demo_task)
    board = demo_board(demo_task, team)
    scheduler = Scheduler(board, team)
    scheduler.pause()
    out = {}
    thread = threading.Thread(target=lambda: out.setdefault("r", scheduler.run()))
    thread.start()
    time.sleep(0.1)
    assert board.iteration == 0
    scheduler.step()
    deadline = time.time() + 5
    while board.iteration < 1 and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.1)
    assert board.iteration == 1 and scheduler.paused
    scheduler.stop()
    thread.join(5)
    assert out["r"].stop_reason == STOP_STOPPED


def test_tool_calls_are_recorded_after_the_message():
    class Echo:
        name, description = "echo", "returns its input"

        def __call__(self, arguments):
            return str(arguments.get("text"))

    team = [
        Agent("a", "a", TWO, ScriptedProvider([{"tool": "echo", "arguments": {"text": "hi"}},
                                               turn("A")]),
              team=("a", "b"), tools={"echo": Echo()}, max_tool_calls=2),
        Agent("b", "b", TWO, ScriptedProvider([turn("A", agrees=True)]),
              team=("a", "b")),
    ]
    board = demo_board(TWO, team)
    Scheduler(board, team, config=SchedulerConfig(max_messages=2)).run()
    tools = [e for e in board.get_events() if e.kind == TOOL]
    assert len(tools) == 1
    assert tools[0].data["result"] == "hi"
    assert tools[0].data["message_id"] == board.get_messages()[0].message_id


def test_rejects_bad_configuration(demo_task, mock_team):
    team = mock_team(demo_task)
    board = demo_board(demo_task, team)
    with pytest.raises(SchedulerError):
        Scheduler(board, [])
    with pytest.raises(SchedulerError):
        Scheduler(board, [team[0], team[0]])
    with pytest.raises(ValueError):
        SchedulerConfig(max_messages=0)
