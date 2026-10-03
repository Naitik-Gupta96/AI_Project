"""Counterfactual resolution: reflection -> intervention -> branch -> replay -> outcome."""

import pytest

from ai_project.agents import build_team
from ai_project.blackboard import Blackboard
from ai_project.counterfactual import CounterfactualError
from ai_project.counterfactual.resolver import CounterfactualResolver
from ai_project.llm import LLMRequest, LLMResponse, MockLLMProvider
from ai_project.pipeline import RunConfig, default_policy, run_task
from ai_project.scheduler import Scheduler
from ai_project.tasks import DecisionTask, Evidence, flash_talk_task

ALL = ("analyst", "critic", "specialist")


def fingerprint(board):
    return board.get_state().to_dict(), [e.to_dict() for e in board.get_history()]


def test_no_cf_agents_means_no_recovery():
    run = run_task(flash_talk_task(), ())
    assert run.original.deadlocked
    assert run.resolution.reflections == [] and not run.recovered
    assert run.final is run.original


def test_critic_reflection_recovers_and_replay_is_real():
    run = run_task(flash_talk_task(), ("critic",))
    (reflection,) = run.resolution.reflections
    assert (reflection.agent_id, reflection.iteration) == ("critic", 2)
    assert reflection.revised["metadata"]["alternative"] == "Option B"
    result = reflection.outcome.result
    assert [(e["agent_id"], e["tag"], e["prediction"]) for e in result.history] == [
        ("analyst", "RATIFY", "Option A"),
        ("critic", "REFUTE", "Option A"),
        ("specialist", "REVISE", "Option B"),
        ("critic", "RATIFY", "Option B"),
        ("analyst", "RATIFY", "Option B"),
    ]
    # Only steps 1-2 are set up; steps 3-5 come from the scheduler running the agents
    kinds = [t.kind for t in reflection.outcome.branch.get_trace_entries()]
    assert kinds[:2] == ["inherited", "intervention"]
    assert kinds[2:5] == ["agent_action"] * 3
    assert result.consensus_reached
    assert reflection.outcome.comparison.divergence_iteration == 2


def test_candidates_are_tried_latest_first():
    run = run_task(flash_talk_task(), ALL)
    assert [(r.agent_id, r.iteration) for r in run.resolution.reflections] == [("specialist", 3)]
    assert run.recovered


def test_original_board_is_never_modified():
    task = flash_talk_task()
    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata())
    agents = build_team(task)
    config = RunConfig().scheduler_config()
    original = Scheduler(board, agents, default_policy(), config).run()
    before = fingerprint(board)
    CounterfactualResolver().resolve(board, original, agents, ALL, default_policy(), config)
    assert fingerprint(board) == before


def test_infeasible_task_is_not_recovered():
    task = DecisionTask("t", "q", ("Option A", "Option B"), {
        "analyst": Evidence(scores={"Option A": 0.9, "Option B": 0.5}),
        "critic": Evidence(objections={"Option A": "no"}),
        "specialist": Evidence(objections={"Option A": "no", "Option B": "no"}),
    })
    run = run_task(task, ALL)
    assert run.original.deadlocked and not run.recovered
    assert run.final.status == "DEADLOCK"


def test_requires_a_deadlocked_run():
    task = DecisionTask("t", "q", ("Option A",), {"analyst": Evidence(scores={"Option A": 0.9})})
    run = run_task(task, ALL)
    assert run.original.consensus_reached and run.resolution is None
    with pytest.raises(CounterfactualError):
        CounterfactualResolver().resolve(run.board, run.original, run.agents, ALL)


def test_unknown_cf_agent_rejected():
    run = run_task(flash_talk_task())
    with pytest.raises(CounterfactualError):
        CounterfactualResolver().resolve(run.board, run.original, run.agents, ["nobody"])


class BreaksDuringReplay(MockLLMProvider):
    """Normal for the original run and reflection; returns garbage inside a branch."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        ctx = request.context
        if not ctx.is_reflection and any(e.metadata.get("counterfactual") for e in ctx.history):
            return LLMResponse("not json")
        return super().generate(request)


def test_replay_failure_is_recorded_not_raised():
    run = run_task(flash_talk_task(), ("critic",), provider=BreaksDuringReplay())
    (reflection,) = run.resolution.reflections
    assert reflection.outcome.result.status == "FAILED"
    assert "unparseable" in reflection.outcome.result.error
    assert not run.recovered and run.final.status == "DEADLOCK"
