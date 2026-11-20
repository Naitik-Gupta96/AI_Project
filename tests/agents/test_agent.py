import pytest

from ai_project.agents import Agent, AgentError
from ai_project.benchmarks import Task
from ai_project.blackboard import Blackboard
from ai_project.llm.base import ProviderUnavailableError
from tests.helpers import ScriptedProvider, msg, turn

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


def test_turn_becomes_a_tagged_draft():
    board = board_with(msg("a", "INIT", "A"))
    draft = agent([turn("B", agrees=False, changed=False)]).act(board)
    assert draft.message is not None and draft.rejected == []
    assert draft.message.tag.value == "REFUTE"
    assert draft.message.judgment.prediction_matches is False
    assert draft.message.metadata["role"] == "critic"
    board.commit(draft.message)


def test_errors_are_fed_back_and_retried():
    board = board_with(msg("a", "INIT", "A"))
    provider = ScriptedProvider([turn("B"),  # no explanation_agrees
                                 turn("B", agrees=False)])
    draft = Agent("b", "critic", TASK, provider, team=("a", "b")).act(board)
    assert draft.message.tag.value == "REFUTE"
    assert len(draft.rejected) == 1
    assert "explanation_agrees is required" in provider.requests[1].prompt


def test_unparseable_output_is_retried_then_given_up():
    board = board_with(msg("a", "INIT", "A"))
    draft = agent(["no json here", '{"prediction": "B"}'], max_retries=1).act(board)
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


def test_request_carries_prompts_and_a_constrained_schema_but_never_the_reference():
    board = board_with(msg("a", "INIT", "A", explanation="A is cheapest"))
    provider = ScriptedProvider([turn("B", agrees=False)])
    a = Agent("b", "critic", TASK, provider, persona="Role: critic.", team=("a", "b"))
    a.lessons.append("Name an alternative when you object.")
    a.act(board)
    request = provider.requests[0]
    assert "A is cheapest" in request.prompt
    assert "Role: critic." in request.system
    assert "Name an alternative" in request.system
    assert "SECRET-REFERENCE" not in request.prompt + request.system
    assert request.schema == "turn"
    assert request.json_schema["properties"]["prediction"]["enum"] == ["A", "B"]
    assert "prediction_matches" not in request.json_schema["properties"]


def test_usage_is_counted_per_phase():
    board = board_with(msg("a", "INIT", "A"))
    a = Agent("b", "critic", TASK, ScriptedProvider(
        [turn("B", agrees=False)] * 2, usage={"prompt_tokens": 10, "completion_tokens": 3}),
        team=("a", "b"))
    a.act(board)
    a.clone("sandbox").act(board)
    usage = a.usage.to_dict()
    assert usage["live"]["calls"] == 1 and usage["sandbox"]["calls"] == 1
    assert usage["total"]["prompt_tokens"] == 20


def test_reflection_keeps_only_new_valid_candidates():
    board = board_with(msg("a", "INIT", "A"),
                       msg("b", "REFUTE", "B", judgment=(False, False, False)))
    target = board.get_messages()[1]
    past = Blackboard.from_events(board.get_events()[:2])  # task + INIT
    reflection_output = {
        "candidates": [
            turn("A", agrees=True, rationale="agree with the analyst"),  # RATIFY A: new
            turn("B", agrees=False, rationale="same as before"),  # REFUTE B: unchanged
            turn("A", rationale="no judgment"),  # missing explanation_agrees
        ],
        "lesson": "Check the analyst's numbers first.",
    }
    a = Agent("b", "critic", TASK, ScriptedProvider([reflection_output]), team=("a", "b"))
    reflection, rejected = a.reflect(past, target, board.get_messages())
    assert [(c.message.tag.value, c.message.prediction) for c in reflection.candidates] == [
        ("RATIFY", "A")]
    assert reflection.candidates[0].rationale == "agree with the analyst"
    assert len(rejected) == 1 and "explanation_agrees" in rejected[0]["errors"][0]
    assert reflection.lesson.startswith("Check")


def test_reflection_only_on_own_messages():
    board = board_with(msg("a", "INIT", "A"))
    with pytest.raises(AgentError):
        agent([]).reflect(board, board.get_messages()[0], board.get_messages())


def test_tool_schema_allows_a_tool_call():
    class Echo:
        name, description = "echo", "returns its input"

        def __call__(self, arguments):
            return "echoed"

    board = board_with(msg("a", "INIT", "A"))
    provider = ScriptedProvider([{"tool": "echo", "arguments": {}}, turn("B", agrees=False)])
    a = Agent("b", "critic", TASK, provider, team=("a", "b"), tools={"echo": Echo()},
              max_tool_calls=1)
    draft = a.act(board)
    assert "anyOf" in provider.requests[0].json_schema
    assert "anyOf" not in provider.requests[1].json_schema  # no tool calls left
    assert "echoed" in provider.requests[1].prompt
    assert draft.tool_calls[0]["result"] == "echoed"
