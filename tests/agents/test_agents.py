"""Agents: the provider pipeline, the mock role rules, PXP normalization and reflection."""

import json
import re

import pytest

from ai_project.agents import (
    AgentError,
    AnalystAgent,
    CriticAgent,
    SpecialistAgent,
    build_team,
)
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import HistoryEvent
from ai_project.deadlock import current_proposal
from ai_project.llm import LLMProvider, LLMRequest, LLMResponse, MockLLMProvider
from ai_project.llm.base import ProviderUnavailableError
from ai_project.pipeline import run_task
from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.tasks import DecisionTask, Evidence, flash_talk_task, generate_tasks

A, B, C = "Option A", "Option B", "Option C"


class ScriptedProvider(LLMProvider):
    """Returns fixed outputs and records requests (stands in for a model)."""

    name = "scripted"

    def __init__(self, *outputs: str) -> None:
        self.outputs = list(outputs)
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(self.outputs.pop(0), usage={"prompt_tokens": 10, "completion_tokens": 5})


class FailingProvider(LLMProvider):
    name = "failing"

    def generate(self, request: LLMRequest) -> LLMResponse:
        raise ProviderUnavailableError("down")


def board_with(task: DecisionTask, *messages: tuple[str, str, str, dict]) -> Blackboard:
    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata())
    for agent_id, tag, prediction, metadata in messages:
        board.publish_message(
            PXPMessage.create(agent_id, PXPTag.from_string(tag), prediction, "x", 0.8,
                              board.get_iteration() + 1, metadata)
        )
    return board


def output(tag: str, prediction: str, **metadata) -> str:
    return json.dumps({"tag": tag, "prediction": prediction, "explanation": "model says so",
                       "confidence": 0.7, "metadata": metadata})


TASK = DecisionTask(
    task_id="t",
    question="Pick one",
    options=(A, B, C),
    evidence={
        "analyst": Evidence(scores={A: 0.9, B: 0.6, C: 0.3}, objections={C: "too little benefit"}),
        "critic": Evidence(objections={A: "breaks C3"}),
        "specialist": Evidence(objections={B: "too slow"}),
    },
)


def agent(cls, provider=None):
    return cls(llm_provider=provider, evidence=TASK.evidence_for(cls.role))


class TestPipeline:
    def test_act_goes_through_provider_with_rendered_prompt(self):
        provider = ScriptedProvider(output("RATIFY", A))
        message = agent(AnalystAgent, provider).act(board_with(TASK))
        request = provider.requests[0]
        assert request.context.role == "analyst"
        assert "Pick one" in request.prompt
        assert "benefit estimate for Option A: 0.90" in request.prompt
        assert message.tag == PXPTag.RATIFY and message.prediction == A
        assert message.iteration == 1
        assert message.metadata["provider"] == "scripted"

    def test_private_evidence_stays_private(self):
        provider = ScriptedProvider(output("RATIFY", A))
        agent(CriticAgent, provider).act(board_with(TASK))
        prompt = provider.requests[0].prompt
        assert "breaks C3" in prompt
        assert "too slow" not in prompt and "0.90" not in prompt

    def test_usage_is_accumulated(self):
        provider = ScriptedProvider(output("RATIFY", A), output("RATIFY", A))
        analyst = agent(AnalystAgent, provider)
        board = board_with(TASK)
        analyst.act(board)
        analyst.act(board)
        assert analyst.usage == {"calls": 2, "prompt_tokens": 20, "completion_tokens": 10}

    def test_mock_reports_no_tokens(self):
        analyst = agent(AnalystAgent)
        analyst.act(board_with(TASK))
        assert analyst.usage == {"calls": 1, "prompt_tokens": None, "completion_tokens": None}

    @pytest.mark.parametrize("template", ["act.md", "reflect.md"])
    def test_prompts_have_no_unfilled_placeholders(self, template):
        board = board_with(TASK, ("analyst", "RATIFY", A, {}))
        a = agent(CriticAgent)
        ctx = a.build_context(board)
        if template == "reflect.md":
            from dataclasses import replace
            ctx = replace(ctx, reflect_on=board.get_history()[0])
        prompt = a.render_prompt(ctx, template)
        assert not re.search(r"\$[a-z_]+", prompt)

    def test_provider_error_becomes_agent_error(self):
        with pytest.raises(AgentError, match="provider error"):
            agent(AnalystAgent, FailingProvider()).act(board_with(TASK))

    def test_unparseable_output_becomes_agent_error(self):
        with pytest.raises(AgentError, match="unparseable"):
            agent(AnalystAgent, ScriptedProvider("I think A")).act(board_with(TASK))


class TestNormalization:
    """Model output is held to PXP semantics (the mock already follows them)."""

    def test_refute_of_other_option_becomes_refute_of_proposal(self):
        board = board_with(TASK, ("analyst", "RATIFY", A, {}))
        msg = agent(CriticAgent, ScriptedProvider(output("REFUTE", B))).act(board)
        assert (msg.tag, msg.prediction, msg.metadata["alternative"]) == (PXPTag.REFUTE, A, B)
        assert msg.metadata["normalized"]

    def test_ratify_of_other_option_becomes_revise(self):
        board = board_with(TASK, ("analyst", "RATIFY", A, {}))
        msg = agent(SpecialistAgent, ScriptedProvider(output("RATIFY", B))).act(board)
        assert (msg.tag, msg.prediction) == (PXPTag.REVISE, B)

    def test_prediction_mapped_to_option_name(self):
        msg = agent(AnalystAgent, ScriptedProvider(output("RATIFY", "option b (queue)"))).act(
            board_with(TASK))
        # "option b" does not contain "Option B" case-sensitively but matches case-insensitively
        assert msg.prediction == B

    def test_unknown_prediction_rejected(self):
        with pytest.raises(AgentError, match="not one of"):
            agent(AnalystAgent, ScriptedProvider(output("RATIFY", "Option Z"))).act(board_with(TASK))

    def test_invalid_alternative_dropped(self):
        board = board_with(TASK, ("analyst", "RATIFY", A, {}))
        msg = agent(CriticAgent, ScriptedProvider(output("REFUTE", A, alternative="Option Z"))).act(
            board)
        assert "alternative" not in msg.metadata


class TestMockRoleRules:
    def test_analyst_opens_with_best_acceptable_option(self):
        msg = agent(AnalystAgent).act(board_with(TASK))
        assert (msg.tag, msg.prediction) == (PXPTag.RATIFY, A)
        assert msg.metadata["rule"] == "open"

    def test_analyst_refutes_what_its_evidence_rules_out(self):
        board = board_with(TASK, ("specialist", "RATIFY", C, {}))
        msg = agent(AnalystAgent).act(board)
        assert (msg.tag, msg.prediction) == (PXPTag.REFUTE, C)
        assert "too little benefit" in msg.explanation

    def test_critic_refutes_with_reason_and_no_alternative(self):
        msg = agent(CriticAgent).act(board_with(TASK, ("analyst", "RATIFY", A, {})))
        assert (msg.tag, msg.prediction) == (PXPTag.REFUTE, A)
        assert "breaks C3" in msg.explanation
        assert "alternative" not in msg.metadata

    def test_critic_ratifies_acceptable_proposal(self):
        msg = agent(CriticAgent).act(board_with(TASK, ("analyst", "RATIFY", B, {})))
        assert (msg.tag, msg.prediction) == (PXPTag.RATIFY, B)

    def test_specialist_adopts_acceptable_alternative(self):
        board = board_with(TASK, ("analyst", "RATIFY", A, {}),
                           ("critic", "REFUTE", A, {"alternative": C}))
        msg = agent(SpecialistAgent).act(board)
        assert (msg.tag, msg.prediction) == (PXPTag.REVISE, C)
        assert msg.metadata["adopted_from"] == "critic"

    def test_specialist_ignores_alternative_it_rules_out(self):
        board = board_with(TASK, ("analyst", "RATIFY", A, {}),
                           ("critic", "REFUTE", A, {"alternative": B}))
        msg = agent(SpecialistAgent).act(board)
        assert (msg.tag, msg.prediction) == (PXPTag.RATIFY, A)  # A is fine for the specialist

    def test_reject_when_nothing_is_acceptable(self):
        task = DecisionTask("t", "q", (A,), {"analyst": Evidence(objections={A: "no"})})
        msg = AnalystAgent(evidence=task.evidence_for("analyst")).act(board_with(task))
        assert msg.tag == PXPTag.REJECT

    def test_same_board_same_message(self):
        board = board_with(TASK, ("analyst", "RATIFY", A, {}))
        first = agent(CriticAgent).act(board)
        second = agent(CriticAgent).act(board)
        assert (first.tag, first.prediction, first.explanation) == (
            second.tag, second.prediction, second.explanation)

    def test_refute_always_names_the_standing_proposal(self):
        for task in generate_tasks(40, seed=3):
            run = run_task(task, ("analyst", "critic", "specialist"))
            histories = [run.original.history] + [
                r.outcome.result.history for r in (run.resolution.attempts if run.resolution else [])
            ]
            for history in histories:
                events = [HistoryEvent.from_dict(e) for e in history]
                for i, e in enumerate(events):
                    if e.tag == "REFUTE":
                        assert e.prediction == current_proposal(events[:i]), task.task_id


class TestReflection:
    def deadlocked(self):
        task = flash_talk_task()
        board = Blackboard()
        board.initialize_task(task.question, task.board_metadata())
        team = build_team(task)
        for a in team:
            board.publish_message(a.act(board))
        return task, team, board.get_history()

    def test_critic_names_the_alternative_in_hindsight(self):
        task, (_, critic, _), history = self.deadlocked()
        decision = critic.reflect(task.question, task.options, history, history[1])
        assert (decision.tag, decision.prediction, decision.alternative) == (
            PXPTag.REFUTE, A, B)
        assert decision.metadata["reflection_of"] == 2

    def test_specialist_proposes_in_hindsight(self):
        task, (_, _, specialist), history = self.deadlocked()
        decision = specialist.reflect(task.question, task.options, history, history[2])
        assert (decision.tag, decision.prediction) == (PXPTag.REVISE, B)

    def test_analyst_reopens_in_hindsight(self):
        task, (analyst, _, _), history = self.deadlocked()
        decision = analyst.reflect(task.question, task.options, history, history[0])
        assert (decision.tag, decision.prediction) == (PXPTag.RATIFY, B)

    def test_no_change_when_nothing_unrefuted_is_acceptable(self):
        task = DecisionTask("t", "q", (A,), {"critic": Evidence(objections={A: "bad"})})
        critic = CriticAgent(evidence=task.evidence_for("critic"))
        history = [HistoryEvent(1, "analyst", "RATIFY", "t", A, "x", 0.8),
                   HistoryEvent(2, "critic", "REFUTE", "t", A, "bad", 0.8)]
        assert critic.reflect("q", (A,), history, history[1]) is None

    def test_cannot_reflect_on_another_agents_message(self):
        task, (analyst, critic, _), history = self.deadlocked()
        with pytest.raises(AgentError):
            critic.reflect(task.question, task.options, history, history[0])

    def test_mock_provider_is_marked_deterministic(self):
        assert MockLLMProvider().describe() == {"name": "deterministic-mock", "deterministic": True}
