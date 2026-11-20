import pytest

from ai_project.agents import Agent, AgentError
from ai_project.benchmarks import Task
from ai_project.blackboard import Blackboard
from ai_project.llm.base import ProviderUnavailableError
from tests.helpers import ScriptedProvider, msg, output

TASK = Task("t", "synthetic", "Pick one", ("A", "B"), domain="synthetic",
            reference="SECRET-REFERENCE")


def board_with(*messages):
    board = Blackboard()
    board.initialize_task(TASK.question, TASK.board_metadata(), agents=["a", "b"])
    for m in messages:
        board.commit(m)
    return board


def agent(outputs, **kw):
    return Agent("b", "critic", TASK, ScriptedProvider(outputs), team=("a", "b"), **kw)


def test_valid_output_becomes_a_draft():
    board = board_with(msg("a", "INIT", "A"))
    draft = agent([output("REFUTE", "B", (False, False, False))]).act(board)
    assert draft.message is not None and draft.rejected == []
    assert draft.message.metadata["role"] == "critic"
    board.commit(draft.message)


def test_grammar_error_is_fed_back_and_retried():
    board = board_with(msg("a", "INIT", "A"))
    provider = ScriptedProvider([output("RATIFY", "B", (False, False, False)),
                                 output("REFUTE", "B", (False, False, False))])
    draft = Agent("b", "critic", TASK, provider, team=("a", "b")).act(board)
    assert draft.message.tag.value == "REFUTE"
    assert len(draft.rejected) == 1
    assert "requires REFUTE" in provider.requests[1].prompt


def test_unparseable_output_is_retried_then_given_up():
    board = board_with(msg("a", "INIT", "A"))
    draft = agent(["no json here", '{"tag": "RATIFY"}'], max_retries=1).act(board)
    assert draft.message is None
    assert len(draft.rejected) == 2
    assert "no grammatical message" in draft.error


def test_provider_failure_ends_the_turn():
    class Down(ScriptedProvider):
        def generate(self, request):
            raise ProviderUnavailableError("offline")

    board = board_with(msg("a", "INIT", "A"))
    draft = Agent("b", "critic", TASK, Down(), team=("a", "b")).act(board)
    assert draft.message is None and "offline" in draft.error


def test_prompt_contains_the_board_but_never_the_reference():
    board = board_with(msg("a", "INIT", "A", explanation="A is cheapest"))
    provider = ScriptedProvider([output("REFUTE", "B", (False, False, False))])
    a = Agent("b", "critic", TASK, provider, persona="Role: critic.", team=("a", "b"))
    a.lessons.append("Name an alternative when you object.")
    a.act(board)
    request = provider.requests[0]
    assert "A is cheapest" in request.prompt
    assert "Role: critic." in request.system
    assert "Name an alternative" in request.system
    assert "SECRET-REFERENCE" not in request.prompt + request.system
    assert request.schema == "pxp_message"


def test_usage_is_counted_per_phase():
    board = board_with(msg("a", "INIT", "A"))
    a = Agent("b", "critic", TASK, ScriptedProvider(
        [output("REFUTE", "B", (False, False, False))] * 2,
        usage={"prompt_tokens": 10, "completion_tokens": 3}), team=("a", "b"))
    a.act(board)
    a.clone("sandbox").act(board)
    usage = a.usage.to_dict()
    assert usage["live"]["calls"] == 1 and usage["sandbox"]["calls"] == 1
    assert usage["total"]["prompt_tokens"] == 20


def test_reflection_keeps_only_grammatical_new_candidates():
    board = board_with(msg("a", "INIT", "A"), msg("b", "REFUTE", "B",
                                                  judgment=(False, False, False)))
    target = board.get_messages()[1]
    past = Blackboard.from_events(board.get_events()[:2])  # task + INIT
    reflection_output = {
        "candidates": [
            {**output("RATIFY", "A", (True, True, False)), "rationale": "agree"},  # valid
            {**output("RATIFY", "B", (True, True, False)), "rationale": "bad"},  # not aligned
            {**output("REFUTE", "B", (False, False, False)), "rationale": "same"},  # unchanged
        ],
        "lesson": "Check the analyst's numbers first.",
    }
    a = Agent("b", "critic", TASK, ScriptedProvider([reflection_output]), team=("a", "b"))
    a.max_retries = 0
    target_same = target
    reflection, rejected = a.reflect(past, target_same, board.get_messages())
    predictions = [c.output.prediction for c in reflection.candidates]
    assert predictions == ["A"]
    assert len(rejected) == 1
    assert reflection.lesson.startswith("Check")


def test_reflection_only_on_own_messages():
    board = board_with(msg("a", "INIT", "A"))
    with pytest.raises(AgentError):
        agent([]).reflect(board, board.get_messages()[0], board.get_messages())
