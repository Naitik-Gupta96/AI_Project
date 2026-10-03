"""MockLLMProvider determinism and OllamaProvider against a stubbed HTTP layer."""

import io
import json
import urllib.error

import pytest

from ai_project.agents import AgentError, AnalystAgent
from ai_project.blackboard import Blackboard
from ai_project.llm import LLMRequest, MockLLMProvider, OllamaProvider
from ai_project.llm.base import ProviderUnavailableError
from ai_project.tasks import flash_talk_task


def flash_board():
    task = flash_talk_task()
    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata())
    return task, board


def test_mock_same_context_same_text():
    task, board = flash_board()
    analyst = AnalystAgent(evidence=task.evidence_for("analyst"))
    ctx = analyst.build_context(board)
    request = LLMRequest(analyst.render_prompt(ctx), ctx)
    outputs = {MockLLMProvider().generate(request).text for _ in range(5)}
    assert len(outputs) == 1
    assert MockLLMProvider().generate(request).usage is None


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ollama_request_and_usage(monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data)
        reply = {
            "response": json.dumps({"tag": "RATIFY", "prediction": "Option A",
                                    "explanation": "highest benefit", "confidence": 0.8}),
            "prompt_eval_count": 120,
            "eval_count": 30,
        }
        return FakeResponse(json.dumps(reply).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    task, board = flash_board()
    analyst = AnalystAgent(llm_provider=OllamaProvider(model="m", seed=7),
                           evidence=task.evidence_for("analyst"))
    message = analyst.act(board)

    assert sent["url"].endswith("/api/generate")
    assert sent["body"]["model"] == "m"
    assert sent["body"]["format"] == "json"
    assert sent["body"]["options"] == {"temperature": 0.0, "seed": 7}
    assert "Option A (single in-process service" in sent["body"]["prompt"]
    assert message.prediction == "Option A"
    assert message.metadata["provider"] == "ollama"
    assert analyst.usage == {"calls": 1, "prompt_tokens": 120, "completion_tokens": 30}


def test_ollama_unreachable(monkeypatch):
    def refuse(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    provider = OllamaProvider()
    assert provider.is_available() is False
    with pytest.raises(ProviderUnavailableError):
        provider.generate(LLMRequest("p", None))
    task, board = flash_board()
    with pytest.raises(AgentError):
        AnalystAgent(llm_provider=provider, evidence=task.evidence_for("analyst")).act(board)


def test_ollama_is_not_labelled_deterministic():
    assert OllamaProvider().describe()["deterministic"] is False
