"""
MSCoRe (Multi-Stage Collaborative Reasoning), the open-ended value-chain part.

Data: https://huggingface.co/datasets/032564yn/MSCoRe (CC-BY-4.0), fetched by
``bb fetch mscore`` into ``data/mscore``. Each file under a value chain is a
JSON list of Alpaca records ``{"instruction", "input", "output"}`` written in
Chinese; ``output`` is the reference answer.

    <chain>/<difficulty>/<stage>      Automotive, Pharmaceutical, E-Commerce
    <chain>/<stage>                   Automotive-Energy (no difficulty levels)

Sampling is stratified: the requested number of items is split evenly across
the four chains, then evenly across each chain's difficulty levels, then
drawn uniformly (seeded) from all stage files of that level.

Scoring follows the MSCoRe evaluation script: ROUGE-L between the answer and
the reference over jieba tokens (character tokens without jieba). An answer
counts as accurate when its ROUGE-L F1 reaches ``threshold``; experiments
report the F1 itself and the accuracy at several thresholds.
"""

import json
import random
from pathlib import Path

from ai_project.benchmarks.base import Score, Task
from ai_project.benchmarks.scoring import rouge_l

CHAINS = {
    "automotive": "Automotive Value Chain",
    "pharmaceutical": "Pharmaceytical Value Chain",  # spelled this way in the dataset
    "ecommerce": "Electronic Commerce Value Chain",
    "automotive_energy": "Automotive-Energy Chain",
}

ANSWER_FORMAT = ("Answer in the language of the question (Chinese), covering the stages the "
                 "question involves, in at most about 500 characters.")


def _stage_files(root: Path, chain: str) -> dict[str, list[Path]]:
    """{difficulty: [stage files]}; difficulty "mixed" when the chain has no levels."""
    base = root / CHAINS[chain]
    if not base.is_dir():
        return {}
    levels: dict[str, list[Path]] = {}
    for path in sorted(base.iterdir()):
        if path.is_dir():
            files = sorted(p for p in path.iterdir() if p.is_file())
            if files:
                levels[path.name.lower()] = files
        elif path.is_file():
            levels.setdefault("mixed", []).append(path)
    return levels


class MSCoReBenchmark:
    """
    Args:
        data_dir: Where ``bb fetch mscore`` put the dataset
        threshold: ROUGE-L F1 at which an answer counts as accurate
    """

    name = "mscore"

    def __init__(self, data_dir: str | Path = "data/mscore", threshold: float = 0.3) -> None:
        self.root = Path(data_dir)
        self.threshold = threshold
        self._counts: dict[str, int] = {}

    # Stage files reach 30 MB, so only record counts are kept between calls and each file is
    # parsed again when its sampled records are extracted.
    def _count(self, path: Path) -> int:
        key = str(path)
        if key not in self._counts:
            self._counts[key] = len(_read(path))
        return self._counts[key]

    def _tasks(self, chain: str, difficulty: str, path: Path, indices: list[int]) -> list[Task]:
        records = _read(path)
        return [self._task(chain, difficulty, path, i, records[i]) for i in indices]

    def _task(self, chain: str, difficulty: str, path: Path, index: int, record: dict) -> Task:
        question = record["instruction"].strip()
        if record.get("input"):
            question += "\n\n" + str(record["input"]).strip()
        stage = path.name.strip()
        return Task(
            task_id=f"mscore|{chain}|{difficulty}|{stage}|{index}",
            benchmark=self.name,
            question=question,
            domain=f"mscore-{chain}",
            reference=record["output"],
            context={"value chain": CHAINS[chain], "stage": stage},
            metadata={"chain": chain, "difficulty": difficulty, "stage": stage},
            answer_format=ANSWER_FORMAT,
        )

    def load(self, n: int | None = None, seed: int = 0) -> list[Task]:
        if not self.root.is_dir():
            raise FileNotFoundError(f"MSCoRe data not found in {self.root}; run: bb fetch mscore")
        n = 300 if n is None else n
        rng = random.Random(seed)
        chains = [c for c in CHAINS if _stage_files(self.root, c)]
        if not chains:
            raise FileNotFoundError(f"No MSCoRe value-chain files in {self.root}")
        tasks: list[Task] = []
        per_chain = _split(n, len(chains))
        for chain, quota in zip(chains, per_chain, strict=True):
            levels = _stage_files(self.root, chain)
            for (difficulty, files), k in zip(levels.items(), _split(quota, len(levels)),
                                              strict=True):
                pool = [(path, i) for path in files for i in range(self._count(path))]
                chosen = rng.sample(pool, min(k, len(pool)))
                for path in files:
                    indices = [i for p, i in chosen if p == path]
                    if indices:
                        tasks.extend(self._tasks(chain, difficulty, path, indices))
        return tasks

    def get(self, task_id: str) -> Task:
        try:
            _, chain, difficulty, stage, index = task_id.split("|")
        except ValueError:
            raise KeyError(f"Unknown MSCoRe task '{task_id}'") from None
        base = self.root / CHAINS.get(chain, "?")
        level = "" if difficulty == "mixed" else _level_dir(base, difficulty)
        path = base / level / stage
        if not path.is_file():
            raise KeyError(f"Unknown MSCoRe task '{task_id}'")
        return self._tasks(chain, difficulty, path, [int(index)])[0]

    def score(self, task: Task, prediction: str | None) -> Score:
        if not prediction:
            return Score(False, 0.0, {"rouge_l": None})
        r = rouge_l(prediction, str(task.reference))
        return Score(r["f1"] >= self.threshold, r["f1"],
                     {"rouge_l": r, "threshold": self.threshold})


def _read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # "Automotive Value Chain/Easy/Supply Chain" on Hugging Face stops after the comma that
        # follows its last record, without the closing bracket. Every record in it is complete.
        trimmed = text.rstrip().removesuffix(",")
        if trimmed.startswith("[") and not trimmed.endswith("]"):
            return json.loads(trimmed + "]")
        raise


def _level_dir(base: Path, difficulty: str) -> str:
    for path in base.iterdir():
        if path.is_dir() and path.name.lower() == difficulty:
            return path.name
    return difficulty


def _split(total: int, parts: int) -> list[int]:
    """``total`` split into ``parts`` near-equal integers (earlier parts get the remainder)."""
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]
