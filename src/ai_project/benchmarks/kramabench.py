"""
KramaBench: data-to-insight tasks over data lakes (https://github.com/mitdbg/Kramabench).

``bb fetch kramabench`` puts the workloads in ``data/kramabench/workload`` and
the six data lakes in ``data/kramabench/data/<domain>``. Each task has a
query, a typed answer and the files a solution needs (``data_sources``). The
agents are not told which files those are: discovering them is part of the
task. They get two tools on their domain's lake: ``list_files`` and a sandboxed
``python``.

Scoring ports KramaBench's metric per answer type (benchmark/metrics.py):

    numeric_exact, string_exact   success: numbers within a rounding tolerance,
                                  strings equal ignoring case and surrounding space
    numeric_approximate           rae_score = 1 / (1 + relative absolute error)
    list_exact                    F1 with exact items (numbers within 1e-6 relative)
    list_approximate              F1 with numbers within 1% relative error
    string_approximate            KramaBench uses an LLM paraphrase judge; pass
                                  ``judge`` (an LLMProvider) to do the same,
                                  otherwise ROUGE-1 F1 is used and reported as such

An answer counts as accurate when its score reaches ``accurate_at`` (default
1.0 for exact types, 0.9 for approximate ones).
"""

import json
import random
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ai_project.agents.tools import ListFiles, PythonSandbox
from ai_project.benchmarks.base import Score, Task
from ai_project.benchmarks.scoring import list_f1, numbers_match, parse_number, rouge_1
from ai_project.llm.base import LLMProvider, LLMProviderError, LLMRequest

DOMAINS = ("archeology", "astronomy", "biomedical", "environment", "legal", "wildfire")

ANSWER_FORMATS = {
    "numeric_exact": "Give only the number, rounded as the question asks.",
    "numeric_approximate": "Give only the number.",
    "string_exact": "Give only the exact value (a name, code or word), no sentence.",
    "string_approximate": "Give a short phrase.",
    "list_exact": 'Give a JSON list, e.g. ["a", "b"] or [1, 2].',
    "list_approximate": "Give a JSON list of numbers.",
}

ACCURATE_AT = {"numeric_approximate": 0.9, "list_approximate": 0.9, "string_approximate": 0.5}


class KramaBenchmark:
    """
    Args:
        data_dir: Where ``bb fetch kramabench`` put workloads and data lakes
        sandbox: "docker" (default) or "local" for the python tool
        judge: Optional provider used as the paraphrase judge for string_approximate
    """

    name = "kramabench"

    def __init__(self, data_dir: str | Path = "data/kramabench", sandbox: str = "docker",
                 judge: LLMProvider | None = None) -> None:
        self.root = Path(data_dir)
        self.sandbox = sandbox
        self.judge = judge
        self._all: list[dict[str, Any]] | None = None

    def _workload(self) -> list[dict[str, Any]]:
        if self._all is None:
            folder = self.root / "workload"
            if not folder.is_dir():
                raise FileNotFoundError(
                    f"KramaBench workloads not found in {folder}; run: bb fetch kramabench")
            tasks = []
            for domain in DOMAINS:
                path = folder / f"{domain}.json"
                if path.is_file():
                    with open(path, encoding="utf-8") as f:
                        tasks += [{**t, "domain": domain} for t in json.load(f)]
            self._all = tasks
        return self._all

    def _task(self, raw: Mapping[str, Any]) -> Task:
        answer_type = raw["answer_type"]
        return Task(
            task_id=f"krama|{raw['id']}",
            benchmark=self.name,
            question=raw["query"],
            domain="kramabench",
            reference=raw["answer"],
            context={"data lake": raw["domain"], "answer type": answer_type},
            metadata={"lake": raw["domain"], "answer_type": answer_type,
                      "data_sources": raw.get("data_sources", []), "id": raw["id"]},
            answer_format=ANSWER_FORMATS.get(answer_type, ""),
        )

    def load(self, n: int | None = None, seed: int = 0) -> list[Task]:
        raw = self._workload()
        n = len(raw) if n is None else min(n, len(raw))
        chosen = sorted(random.Random(seed).sample(range(len(raw)), n))
        return [self._task(raw[i]) for i in chosen]

    def get(self, task_id: str) -> Task:
        wanted = task_id.removeprefix("krama|")
        for raw in self._workload():
            if raw["id"] == wanted:
                return self._task(raw)
        raise KeyError(f"Unknown KramaBench task '{task_id}'")

    def tools(self, task: Task, role: str) -> dict[str, Any]:
        lake = self.root / "data" / task.metadata["lake"]
        if not lake.is_dir():
            raise FileNotFoundError(f"Data lake {lake} missing; run: bb fetch kramabench")
        return {"list_files": ListFiles(lake), "python": PythonSandbox(lake, mode=self.sandbox)}

    def score(self, task: Task, prediction: str | None) -> Score:
        answer_type = task.metadata["answer_type"]
        target = task.reference
        if prediction is None:
            return Score(False, 0.0, {"answer_type": answer_type})
        detail: dict[str, Any] = {"answer_type": answer_type}
        if answer_type == "numeric_exact":
            value = float(numbers_match(prediction, target))
        elif answer_type == "string_exact":
            value = float(prediction.strip().strip('"').lower() == str(target).strip().lower())
        elif answer_type == "numeric_approximate":
            p, t = parse_number(prediction), parse_number(target)
            if p is None or t is None or t == 0:
                value = float(p == t)
            else:
                value = 1 / (1 + abs(p - t) / abs(t))
        elif answer_type == "list_exact":
            value = list_f1(prediction, target if isinstance(target, list) else [target])
        elif answer_type == "list_approximate":
            value = list_f1(prediction, target if isinstance(target, list) else [target], rel=0.01)
        elif answer_type == "string_approximate":
            value, detail["judge"] = self._paraphrase(task, prediction)
        else:
            raise ValueError(f"Unknown answer type '{answer_type}'")
        return Score(value >= ACCURATE_AT.get(answer_type, 1.0) - 1e-9, value, detail)

    def _paraphrase(self, task: Task, prediction: str) -> tuple[float, str]:
        if self.judge is None:
            return rouge_1(prediction, str(task.reference)), "rouge-1 (no judge configured)"
        prompt = (f"Question: {task.question}\nReference answer: {task.reference}\n"
                  f"Candidate answer: {prediction}\nDoes the candidate express the same answer as "
                  'the reference? Reply with JSON {"same": true} or {"same": false}.')
        try:
            text = self.judge.generate(LLMRequest(prompt=prompt, context=None,  # type: ignore[arg-type]
                                                  schema="judge", system="You grade answers.",
                                                  json_schema=_JUDGE_SCHEMA)).text
            same = bool(json.loads(text[text.find("{"): text.rfind("}") + 1]).get("same"))
        except (LLMProviderError, ValueError):
            return rouge_1(prediction, str(task.reference)), "rouge-1 (judge failed)"
        return float(same), "llm paraphrase"


_JUDGE_SCHEMA = {
    "type": "object",
    "required": ["same"],
    "properties": {"same": {"type": "boolean"}},
}
