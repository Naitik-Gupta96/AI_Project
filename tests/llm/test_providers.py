import io
import json
import threading
import time
import urllib.error

import pytest

from ai_project.agents import build_team
from ai_project.benchmarks import architecture_task
from ai_project.llm.base import (
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    ProviderUnavailableError,
)
from ai_project.llm.broker import Broker
from ai_project.llm.cache import CachedProvider, ResponseCache
from ai_project.llm.factory import make_provider
from ai_project.llm.providers.hf import HFTransformersProvider
from ai_project.llm.providers.mock import MockLLMProvider
from ai_project.llm.providers.ollama import OllamaProvider
from ai_project.llm.providers.openai_compat import OpenAICompatibleProvider
from ai_project.session import run_session


class FakeHTTP:
    """Stands in for urllib.request.urlopen; records request bodies."""

    def __init__(self, reply):
        self.reply = reply
        self.bodies = []
        self.urls = []

    def __call__(self, request, timeout=None):
        self.urls.append(request.full_url)
        self.bodies.append(json.loads(request.data) if request.data else None)
        if isinstance(self.reply, Exception):
            raise self.reply
        return io.BytesIO(json.dumps(self.reply).encode())


def request(schema="turn"):
    task = architecture_task()
    agent = build_team(task, MockLLMProvider())[0]
    from ai_project.blackboard import Blackboard
    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata(), agents=["analyst"])
    ctx = agent.build_context(board)
    system, prompt = agent.render(ctx)
    return LLMRequest(prompt=prompt, context=ctx, schema=schema, system=system)


def test_openai_compatible_sends_schema_and_reads_usage(monkeypatch):
    fake = FakeHTTP({"choices": [{"message": {"content": '{"tag": "INIT"}'},
                                  "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 120, "completion_tokens": 30}})
    monkeypatch.setattr("urllib.request.urlopen", fake)
    provider = OpenAICompatibleProvider("Qwen/Qwen2.5-7B-Instruct", "http://gpu:8000/v1")
    response = provider.generate(request())
    body = fake.bodies[0]
    assert fake.urls[0] == "http://gpu:8000/v1/chat/completions"
    assert body["messages"][0]["role"] == "system" and body["temperature"] == 0.0
    assert body["response_format"]["json_schema"]["schema"]["title"] == "turn"
    assert response.usage == {"prompt_tokens": 120, "completion_tokens": 30}
    assert response.text == '{"tag": "INIT"}'


def test_ollama_sends_schema_as_format(monkeypatch):
    fake = FakeHTTP({"message": {"content": "{}"}, "prompt_eval_count": 50, "eval_count": 9,
                     "total_duration": 2_000_000})
    monkeypatch.setattr("urllib.request.urlopen", fake)
    response = OllamaProvider("qwen2.5:7b-instruct").generate(request("reflection"))
    body = fake.bodies[0]
    assert fake.urls[0].endswith("/api/chat")
    assert body["format"]["title"] == "reflection"
    assert body["think"] is False and body["options"]["seed"] == 0
    assert response.usage == {"prompt_tokens": 50, "completion_tokens": 9}


def test_http_errors_are_classified(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", FakeHTTP(urllib.error.URLError("refused")))
    with pytest.raises(ProviderUnavailableError):
        OllamaProvider().generate(request())
    busy = urllib.error.HTTPError("u", 503, "busy", {}, io.BytesIO(b"overloaded"))
    monkeypatch.setattr("urllib.request.urlopen", FakeHTTP(busy))
    with pytest.raises(ProviderUnavailableError):
        OpenAICompatibleProvider("m").generate(request())
    bad = urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b"no such model"))
    monkeypatch.setattr("urllib.request.urlopen", FakeHTTP(bad))
    with pytest.raises(LLMProviderError, match="no such model"):
        OpenAICompatibleProvider("m").generate(request())


class Counting(LLMProvider):
    name = "counting"

    def __init__(self, fail_first=0, delay=0.0):
        self.calls = 0
        self.fail_first = fail_first
        self.delay = delay
        self.active = 0
        self.peak = 0
        self.lock = threading.Lock()

    def generate(self, req):
        with self.lock:
            self.calls += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
            fail = self.calls <= self.fail_first
        time.sleep(self.delay)
        with self.lock:
            self.active -= 1
        if fail:
            raise ProviderUnavailableError("warming up")
        return LLMResponse(text=f"answer to {len(req.prompt)}",
                           usage={"prompt_tokens": 3, "completion_tokens": 1})


def test_cache_serves_repeated_requests(tmp_path):
    inner = Counting()
    cached = CachedProvider(inner, ResponseCache(tmp_path / "c.sqlite"))
    first = cached.generate(request())
    second = cached.generate(request())
    assert inner.calls == 1 and (cached.hits, cached.misses) == (1, 1)
    assert second.cached and not first.cached
    assert second.text == first.text and second.usage == first.usage
    # survives a restart
    again = CachedProvider(Counting(), ResponseCache(tmp_path / "c.sqlite"))
    assert again.generate(request()).cached


def test_cache_key_ignores_host_but_not_the_model():
    a = OllamaProvider("m1", host="http://a:1")
    b = OllamaProvider("m1", host="http://b:2")
    c = OllamaProvider("m2")
    cache = ResponseCache(":memory:")
    req = request()
    assert CachedProvider(a, cache).key(req) == CachedProvider(b, cache).key(req)
    assert CachedProvider(a, cache).key(req) != CachedProvider(c, cache).key(req)


def test_broker_retries_then_succeeds():
    inner = Counting(fail_first=2)
    broker = Broker(inner, retries=3, backoff=0.001)
    assert broker.generate(request()).text.startswith("answer")
    assert broker.stats["retries"] == 2 and broker.stats["failures"] == 0


def test_broker_gives_up():
    broker = Broker(Counting(fail_first=10), retries=1, backoff=0.001)
    with pytest.raises(ProviderUnavailableError):
        broker.generate(request())
    assert broker.stats["failures"] == 1


def test_broker_bounds_concurrency():
    inner = Counting(delay=0.05)
    broker = Broker(inner, max_in_flight=2)
    threads = [threading.Thread(target=broker.generate, args=(request(),)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert inner.peak <= 2 and broker.stats["peak_in_flight"] <= 2
    assert broker.stats["requests"] == 6


def test_hf_provider_batches_concurrent_requests(monkeypatch):
    provider = HFTransformersProvider(batch_size=4, batch_wait=0.2, model=object(),
                                      tokenizer=object())

    def fake_run(requests):
        time.sleep(0.01)
        return [LLMResponse(text=f"r{i}") for i, _ in enumerate(requests)]

    monkeypatch.setattr(provider, "_run", fake_run)
    results = []
    threads = [threading.Thread(target=lambda: results.append(provider.generate(request())))
               for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert len(results) == 8
    assert max(provider.batches) > 1 and sum(provider.batches) == 8


def test_hf_failure_reaches_every_caller(monkeypatch):
    provider = HFTransformersProvider(model=object(), tokenizer=object(), batch_wait=0.01)
    monkeypatch.setattr(provider, "_run", lambda reqs: (_ for _ in ()).throw(RuntimeError("OOM")))
    with pytest.raises(LLMProviderError, match="OOM"):
        provider.generate(request())


def test_factory(tmp_path):
    assert isinstance(make_provider("mock"), MockLLMProvider)
    p = make_provider("vllm:Qwen/Qwen2.5-7B-Instruct@http://gpu:8000/v1",
                      cache=tmp_path / "c.sqlite", max_in_flight=16)
    assert isinstance(p, Broker) and p.max_in_flight == 16
    assert isinstance(p.inner, CachedProvider)
    assert p.describe()["base_url"] == "http://gpu:8000/v1"
    assert make_provider("ollama:qwen3:4b").describe()["model"] == "qwen3:4b"
    with pytest.raises(ValueError):
        make_provider("gpt5")


def test_session_with_a_cached_brokered_mock_is_unchanged(tmp_path):
    task = architecture_task()
    plain = run_session(task, build_team(task, MockLLMProvider()), ["analyst"])
    wrapped_provider = Broker(CachedProvider(MockLLMProvider(),
                                             ResponseCache(tmp_path / "c.sqlite")))
    wrapped = run_session(task, build_team(task, wrapped_provider), ["analyst"])
    assert (plain.status, plain.final_prediction, plain.messages) == \
           (wrapped.status, wrapped.final_prediction, wrapped.messages)
