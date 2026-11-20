import pytest

from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.blackboard.models import CONTEXT_REVISION, INTERVENTION, MESSAGE, WEIGHT
from ai_project.counterfactual import (
    CounterfactualConfig,
    CounterfactualError,
    CounterfactualResolver,
    board_before,
)
from ai_project.scheduler import Scheduler


def deadlocked(task, team):
    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata(), agents=[a.agent_id for a in team])
    Scheduler(board, team).run()
    assert board.status == BlackboardStatus.DEADLOCK
    return board


def message_fingerprint(board):
    return [(m.iteration, m.agent_id, m.tag, m.prediction, m.explanation)
            for m in board.get_messages()]


def test_needs_a_deadlocked_board(demo_task, mock_team):
    board = Blackboard()
    board.initialize_task("t", {})
    with pytest.raises(CounterfactualError):
        CounterfactualResolver().intervene(board, mock_team(demo_task), ["analyst"])


def test_unknown_agent(demo_task, mock_team):
    team = mock_team(demo_task)
    with pytest.raises(CounterfactualError):
        CounterfactualResolver().intervene(deadlocked(demo_task, team), team, ["nobody"])


def test_board_before_rebuilds_the_past(demo_task, mock_team):
    team = mock_team(demo_task)
    board = deadlocked(demo_task, team)
    target = board.get_messages()[1]
    past = board_before(board.snapshot(), target, board.grammar)
    assert past.iteration == 1
    assert past.grammar_context("critic").j == 2
    assert past.store is not board.store


def test_analyst_intervention_breaks_the_deadlock(demo_task, mock_team):
    team = mock_team(demo_task)
    board = deadlocked(demo_task, team)
    before = message_fingerprint(board)
    result = CounterfactualResolver().intervene(board, team, ["analyst"])

    assert result.applied and result.agent_id == "analyst"
    assert result.branch.target.iteration == 1  # the INIT
    assert result.branch.candidate.message.prediction == "Option B"
    assert result.branch.result.status == "CONSENSUS"
    assert result.proximity_before == pytest.approx(1 / 3)
    assert result.branch.credit == pytest.approx(2 / 3)
    # the live board's past is untouched; the change is recorded as new events
    assert message_fingerprint(board) == before
    kinds = [e.kind for e in board.get_events()[-4:]]
    assert kinds == [INTERVENTION, CONTEXT_REVISION, WEIGHT, "status"]
    state = board.get_state()
    assert state.status == BlackboardStatus.RUNNING
    assert state.positions["analyst"]["prediction"] == "Option B"
    assert state.weights["analyst"] == pytest.approx(1 - 0.5 * 2 / 3, abs=1e-4)
    assert team[0].lessons and "Option B" in team[0].lessons[0]


def test_sandbox_messages_never_reach_the_live_board(demo_task, mock_team):
    team = mock_team(demo_task)
    board = deadlocked(demo_task, team)
    live_messages = len(board.get_messages())
    result = CounterfactualResolver().intervene(board, team, ["analyst"])
    assert len(board.get_messages()) == live_messages
    assert len(result.branch.messages) > 1
    assert all(m.message_id not in {x.message_id for x in board.get_messages()}
               for m in result.branch.messages)


def test_agents_without_useful_alternatives_change_nothing(demo_task, mock_team):
    team = mock_team(demo_task)
    board = deadlocked(demo_task, team)
    version = board.version
    result = CounterfactualResolver().intervene(board, team, ["critic", "specialist"])
    assert not result.applied
    assert board.status == BlackboardStatus.DEADLOCK
    assert [e.kind for e in board.get_events(since=version)] == [INTERVENTION]
    assert all(not a.lessons for a in team)


@pytest.mark.parametrize(("mode", "revised", "reweighted"), [
    ("prompt", True, False), ("weight", False, True), ("both", True, True),
])
def test_apply_modes(demo_task, mock_team, mode, revised, reweighted):
    team = mock_team(demo_task)
    board = deadlocked(demo_task, team)
    CounterfactualResolver(CounterfactualConfig(apply=mode)).intervene(board, team, ["analyst"])
    kinds = {e.kind for e in board.get_events()}
    assert (CONTEXT_REVISION in kinds) == revised
    assert (WEIGHT in kinds) == reweighted
    assert bool(team[0].lessons) == revised


def test_listener_sees_the_sandbox(demo_task, mock_team):
    team = mock_team(demo_task)
    board = deadlocked(demo_task, team)
    seen = []
    CounterfactualResolver(listener=lambda kind, data: seen.append(kind)).intervene(
        board, team, ["analyst"])
    assert seen[0] == "cf.start" and seen[-1] == "cf.applied"
    assert "cf.branch_start" in seen and "cf.branch_end" in seen
    assert seen.count("cf.branch_event") > 3


def test_resolution_is_deterministic(demo_task, mock_team):
    def run():
        team = mock_team(demo_task)
        board = deadlocked(demo_task, team)
        r = CounterfactualResolver().intervene(board, team, ["analyst"])
        return [(b.target.iteration, b.candidate.message.prediction, round(b.credit, 6),
                 [(m.agent_id, m.tag, m.prediction) for m in b.messages]) for b in r.branches]

    assert run() == run()


def test_branch_events_start_at_the_branch_point(demo_task, mock_team):
    team = mock_team(demo_task)
    board = deadlocked(demo_task, team)
    branch = CounterfactualResolver().intervene(board, team, ["analyst"]).branch
    first_message = next(e for e in branch.events if e.kind == MESSAGE)
    assert first_message.data["message"]["iteration"] == branch.target.iteration
    assert first_message.data["message"]["metadata"]["counterfactual"] is True
