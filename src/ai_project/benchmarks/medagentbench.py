"""
MedAgentBench: clinical tasks against a FHIR server (https://github.com/stanfordmlgroup/MedAgentBench).

Setup (``bb fetch medagentbench`` prints these steps):

1. ``docker compose up fhir`` (image ``jyxsu6/medagentbench``) serves the
   FHIR API on http://127.0.0.1:8080/fhir/.
2. The task file and function list are fetched into ``data/medagentbench``.
3. The reference grader ``refsol.py`` is distributed separately by the
   authors (a Box link in their README). Save it as
   ``data/medagentbench/refsol.py``; scoring needs it.

Agents query the server with the ``fhir_get`` tool. As in MedAgentBench,
POST requests are never sent: they are part of the answer, and the grader
reads them from the transcript. The team's prediction is therefore a JSON
object:

    {"answer": [...], "posts": [{"url": "<FHIR base>/Observation", "payload": {...}}]}

``answer`` is what the original agent would put in ``FINISH([...])``. For
grading, the agreed prediction is turned into the transcript shape the
official grader reads: one agent turn ``POST <url>\\n<json>`` followed by the
user turn "POST request accepted ..." per post, and ``result`` set to the
answer list as JSON text.
"""

import importlib.util
import json
import random
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

from ai_project.agents.tools import FhirGet
from ai_project.benchmarks.base import Score, Task

ANSWER_FORMAT = (
    'Give a JSON object {"answer": [...], "posts": [...]}. "answer" is the list of values the task '
    'asks for (e.g. ["<MRN>"], [<number>], or [] if it asks only for actions). Each post is '
    '{"url": "<FHIR base>/<Resource>", "payload": {...}} for an order or record the task asks '
    "you to create; posts are not sent, they are graded. Omit posts the task does not require."
)
POST_ACK = ("POST request accepted and executed successfully. Please call FINISH if you have got "
            "answers for all the questions and finished all the requested tasks")


def parse_prediction(prediction: str) -> tuple[list[Any], list[dict[str, Any]]]:
    """The (answer, posts) of a team prediction; tolerant of a bare list or FINISH([...])."""
    text = prediction.strip()
    if text.startswith("FINISH(") and text.endswith(")"):
        text = text[len("FINISH("):-1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        try:
            data = json.loads(text[start:end + 1]) if start != -1 else [text]
        except json.JSONDecodeError:
            data = [text]
    if isinstance(data, list):
        return data, []
    if not isinstance(data, dict):
        return [data], []
    answer = data.get("answer", [])
    posts = data.get("posts") or []
    answer = answer if isinstance(answer, list) else [answer]
    return answer, [p for p in posts if isinstance(p, dict)]


def grader_transcript(prediction: str) -> SimpleNamespace:
    """The ``results`` object the official grader expects (``.result`` and ``.history``)."""
    answer, posts = parse_prediction(prediction)
    history = []
    for post in posts:
        payload = json.dumps(post.get("payload", {}), ensure_ascii=False)
        content = f"POST {post.get('url', '')}\n{payload}"
        history.append(SimpleNamespace(role="agent", content=content))
        history.append(SimpleNamespace(role="user", content=POST_ACK))
    history.append(SimpleNamespace(role="agent", content=f"FINISH({json.dumps(answer)})"))
    return SimpleNamespace(result=json.dumps(answer), history=history)


class MedAgentBenchmark:
    """
    Args:
        data_dir: Holds test_data_v2.json, funcs_v1.json and (for scoring) refsol.py
        fhir_base: FHIR API base URL
    """

    name = "medagentbench"

    def __init__(self, data_dir: str | Path = "data/medagentbench",
                 fhir_base: str = "http://127.0.0.1:8080/fhir/") -> None:
        self.root = Path(data_dir)
        self.fhir_base = fhir_base.rstrip("/") + "/"
        self._cases: list[dict[str, Any]] | None = None
        self._refsol: ModuleType | None = None

    def _all(self) -> list[dict[str, Any]]:
        if self._cases is None:
            path = self.root / "test_data_v2.json"
            if not path.is_file():
                raise FileNotFoundError(f"{path} missing; run: bb fetch medagentbench")
            with open(path, encoding="utf-8") as f:
                self._cases = json.load(f)
        return self._cases

    def functions(self) -> list[dict[str, Any]]:
        path = self.root / "funcs_v1.json"
        if not path.is_file():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _task(self, case: dict[str, Any]) -> Task:
        question = case["instruction"]
        if case.get("context"):
            question += "\n\nContext: " + case["context"]
        return Task(
            task_id=f"medagent|{case['id']}",
            benchmark=self.name,
            question=question,
            domain="medagentbench",
            reference=case.get("sol"),
            context={"FHIR base": self.fhir_base},
            metadata={"case": case, "task_type": case["id"].split("_")[0]},
            answer_format=ANSWER_FORMAT,
        )

    def load(self, n: int | None = None, seed: int = 0) -> list[Task]:
        """``n`` cases, the same number from each of the ten task types (seeded)."""
        cases = self._all()
        by_type: dict[str, list[dict[str, Any]]] = {}
        for case in cases:
            by_type.setdefault(case["id"].split("_")[0], []).append(case)
        n = len(cases) if n is None else min(n, len(cases))
        rng = random.Random(seed)
        types = sorted(by_type, key=lambda t: int(t.removeprefix("task")))
        base, extra = divmod(n, len(types))
        chosen = []
        for i, task_type in enumerate(types):
            k = min(base + (1 if i < extra else 0), len(by_type[task_type]))
            chosen += rng.sample(by_type[task_type], k)
        return [self._task(c) for c in chosen]

    def get(self, task_id: str) -> Task:
        wanted = task_id.removeprefix("medagent|")
        for case in self._all():
            if case["id"] == wanted:
                return self._task(case)
        raise KeyError(f"Unknown MedAgentBench task '{task_id}'")

    def tools(self, task: Task, role: str) -> dict[str, Any]:
        return {"fhir_get": FhirGet(self.fhir_base, self.functions())}

    def grader(self) -> ModuleType:
        if self._refsol is None:
            path = self.root / "refsol.py"
            if not path.is_file():
                raise FileNotFoundError(
                    f"{path} missing. Download refsol.py from the link in the MedAgentBench README "
                    "and save it there; it is the official grader.")
            spec = importlib.util.spec_from_file_location("medagentbench_refsol", path)
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            self._refsol = module
        return self._refsol

    def score(self, task: Task, prediction: str | None) -> Score:
        if prediction is None:
            return Score(False, 0.0, {"task_type": task.metadata["task_type"]})
        case = task.metadata["case"]
        grade = getattr(self.grader(), task.metadata["task_type"])
        try:
            ok = grade(case, grader_transcript(prediction), self.fhir_base) is True
            detail: dict[str, Any] = {"task_type": task.metadata["task_type"]}
        except Exception as exc:  # the official grader raises on malformed answers
            ok = False
            detail = {"task_type": task.metadata["task_type"], "grader_error": str(exc)}
        return Score(ok, float(ok), detail)
