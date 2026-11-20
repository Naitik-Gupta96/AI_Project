"""The three benchmark loaders against small fixtures in their real on-disk layout."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ai_project.agents.tools import FhirGet, ListFiles, PythonSandbox
from ai_project.benchmarks.kramabench import KramaBenchmark
from ai_project.benchmarks.medagentbench import (
    MedAgentBenchmark,
    grader_transcript,
    parse_prediction,
)
from ai_project.benchmarks.mscore import MSCoReBenchmark
from ai_project.llm import prompts


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- MSCoRe


@pytest.fixture
def mscore_dir(tmp_path):
    root = tmp_path / "mscore"
    rec = lambda i: {"instruction": f"问题{i}：如何降低电池成本？", "input": "", "output": f"答案{i}：优化材料与工艺。"}  # noqa: E731
    write(root / "Automotive Value Chain" / "Medium" / "Design", [rec(i) for i in range(10)])
    write(root / "Automotive Value Chain" / "Hard" / "Sales", [rec(i) for i in range(10, 16)])
    write(root / "Automotive-Energy Chain" / "Electricity Storage", [rec(i) for i in range(20, 28)])
    return root


def test_mscore_stratified_sample_and_round_trip(mscore_dir):
    bench = MSCoReBenchmark(mscore_dir)
    tasks = bench.load(8, seed=1)
    assert len(tasks) == 8
    chains = [t.metadata["chain"] for t in tasks]
    assert chains.count("automotive") == 4 and chains.count("automotive_energy") == 4
    levels = [t.metadata["difficulty"] for t in tasks if t.metadata["chain"] == "automotive"]
    assert sorted(levels) == ["hard", "hard", "medium", "medium"]
    for t in tasks:
        assert bench.get(t.task_id).reference == t.reference
        assert t.domain in prompts.domains()
    assert [t.task_id for t in bench.load(8, seed=1)] == [t.task_id for t in tasks]


def test_mscore_scoring(mscore_dir):
    bench = MSCoReBenchmark(mscore_dir, threshold=0.5)
    task = bench.load(1)[0]
    assert bench.score(task, task.reference).correct
    assert not bench.score(task, "完全无关的内容").correct
    assert bench.score(task, None).value == 0.0


def test_mscore_missing_data(tmp_path):
    with pytest.raises(FileNotFoundError, match="bb fetch mscore"):
        MSCoReBenchmark(tmp_path / "nothing").load(1)


# ---------------------------------------------------------------- KramaBench


@pytest.fixture
def krama_dir(tmp_path):
    root = tmp_path / "kramabench"
    write(root / "workload" / "legal.json", [
        {"id": "legal-easy-1", "query": "How many rows?", "answer": 3, "answer_type": "numeric_exact",
         "data_sources": ["cases.csv"]},
        {"id": "legal-easy-2", "query": "Which courts?", "answer": ["A", "B"], "answer_type": "list_exact"},
        {"id": "legal-easy-3", "query": "Mean fine?", "answer": 100.0, "answer_type": "numeric_approximate"},
        {"id": "legal-easy-4", "query": "Main issue?", "answer": "late filing", "answer_type": "string_approximate"},
    ])
    lake = root / "data" / "legal"
    lake.mkdir(parents=True)
    (lake / "cases.csv").write_text("court,fine\nA,90\nB,110\nA,100\n", encoding="utf-8")
    return root


def test_kramabench_load_and_scores(krama_dir):
    bench = KramaBenchmark(krama_dir, sandbox="local")
    tasks = {t.metadata["id"]: t for t in bench.load()}
    assert len(tasks) == 4
    assert "cases.csv" not in json.dumps(tasks["legal-easy-1"].context)  # sources stay hidden
    assert bench.score(tasks["legal-easy-1"], "3").correct
    assert not bench.score(tasks["legal-easy-1"], "4").correct
    assert bench.score(tasks["legal-easy-2"], '["b", "a"]').correct
    approx = bench.score(tasks["legal-easy-3"], "105")
    assert approx.value == pytest.approx(1 / 1.05) and approx.correct
    fallback = bench.score(tasks["legal-easy-4"], "late filing of the brief")
    assert fallback.detail["judge"].startswith("rouge-1")
    assert bench.get("krama|legal-easy-2").reference == ["A", "B"]


def test_kramabench_tools_run_in_the_lake(krama_dir):
    bench = KramaBenchmark(krama_dir, sandbox="local")
    task = bench.get("krama|legal-easy-1")
    tools = bench.tools(task, "analyst")
    assert "cases.csv" in tools["list_files"]({})
    out = tools["python"]({"code": "print(len(open('cases.csv').read().splitlines()) - 1)"})
    assert out.strip() == "3"


def test_python_sandbox_reports_errors_and_timeouts(tmp_path):
    sandbox = PythonSandbox(tmp_path, mode="local", timeout=2)
    assert "exit code 1" in sandbox({"code": "raise ValueError('boom')"})
    assert "timed out" in sandbox({"code": "import time; time.sleep(5)"})
    assert sandbox({"code": ""}).startswith("error")
    long = sandbox({"code": "print('x' * 10000)"})
    assert "truncated" in long


def test_docker_sandbox_command_is_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/docker")
    command = PythonSandbox(tmp_path, mode="docker").command("print(1)")
    assert command[:2] == ["docker", "run"]
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert any(part.endswith(":/data:ro") for part in command)


def test_list_files_filters(tmp_path):
    (tmp_path / "a.csv").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    assert ListFiles(tmp_path)({"contains": "csv"}).startswith("a.csv")
    assert ListFiles(tmp_path)({"contains": "zzz"}) == "no matching files"


# ---------------------------------------------------------------- MedAgentBench


@pytest.fixture
def medagent_dir(tmp_path):
    root = tmp_path / "medagentbench"
    cases = [{"id": f"task{t}_{i}", "instruction": f"Task {t}.{i}", "context": "",
              "sol": [f"S{t}{i}"], "eval_MRN": f"S{t}{i}"} for t in (1, 2) for i in range(1, 6)]
    write(root / "test_data_v2.json", cases)
    write(root / "funcs_v1.json", [{"name": "GET {api_base}/Patient", "description": "search",
                                    "parameters": {"properties": {"name": {}, "birthdate": {}}}}])
    (root / "refsol.py").write_text(
        "import json\n"
        "def task1(case, results, base):\n"
        "    return json.loads(results.result) == case['sol']\n"
        "def task2(case, results, base):\n"
        "    posts = [h for h in results.history if h.role == 'agent' and h.content.startswith('POST')]\n"
        "    return len(posts) == 1 and 'accepted' in results.history[1].content\n",
        encoding="utf-8")
    return root


def test_medagentbench_balanced_sample_and_grading(medagent_dir):
    bench = MedAgentBenchmark(medagent_dir)
    tasks = bench.load(4, seed=0)
    assert sorted(t.metadata["task_type"] for t in tasks) == ["task1", "task1", "task2", "task2"]
    t1 = bench.get("medagent|task1_3")
    assert bench.score(t1, '{"answer": ["S13"], "posts": []}').correct
    assert bench.score(t1, 'FINISH(["S13"])').correct
    assert not bench.score(t1, '{"answer": ["S99"]}').correct
    t2 = bench.get("medagent|task2_1")
    post = '{"answer": [], "posts": [{"url": "http://x/fhir/Observation", "payload": {"a": 1}}]}'
    assert bench.score(t2, post).correct
    assert not bench.score(t2, '{"answer": []}').correct


def test_medagentbench_needs_the_official_grader(medagent_dir):
    (medagent_dir / "refsol.py").unlink()
    bench = MedAgentBenchmark(medagent_dir)
    with pytest.raises(FileNotFoundError, match="refsol.py"):
        bench.score(bench.get("medagent|task1_1"), '{"answer": ["S11"]}')


def test_prediction_parsing_and_transcript():
    assert parse_prediction('["a"]') == (["a"], [])
    assert parse_prediction("text before {\"answer\": 5} after") == ([5], [])
    t = grader_transcript('{"answer": [1], "posts": [{"url": "u", "payload": {"k": 2}}]}')
    assert t.result == "[1]"
    assert t.history[0].content == 'POST u\n{"k": 2}'
    assert t.history[1].role == "user" and "accepted" in t.history[1].content
    assert t.history[-1].content == "FINISH([1])"


class _Fhir(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps({"resourceType": "Bundle", "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_fhir_get_tool_against_a_local_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Fhir)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        tool = FhirGet(f"http://127.0.0.1:{server.server_port}/fhir/",
                       [{"name": "GET {api_base}/Patient", "parameters": {"properties": {"name": {}}}}])
        out = json.loads(tool({"path": "Patient?name=Peter"}))
        assert out["path"] == "/fhir/Patient?name=Peter&_format=json"
        assert "Patient" in tool.description
        assert tool({"path": "http://evil.example/x"}).startswith("error")
    finally:
        server.shutdown()
