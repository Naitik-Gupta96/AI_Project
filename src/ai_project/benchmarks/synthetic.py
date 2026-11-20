"""
Synthetic decision tasks with role-partitioned evidence.

These are generated test inputs, not a benchmark: they exercise the protocol,
the scheduler and the counterfactual layer with the deterministic mock agents,
where the ground truth is known exactly.

Each task offers a few options. The analyst holds benefit scores (and rules
out options below a minimum benefit); the critic and the specialist each rule
out some options for a stated reason. An option is *feasible* if no role
rules it out; the reference answer is the feasible option with the highest
benefit score (None if there is none, in which case a deadlock is correct).
"""

import random

from ai_project.benchmarks.base import Evidence, Score, Task

ROLES = ("analyst", "critic", "specialist")

_CRITIC_REASONS = (
    "it violates constraint C3 (runs must be reproducible)",
    "it needs a data-retention exception the policy does not allow",
    "it has no audit trail for decisions",
    "its licence is incompatible with the project",
)
_SPECIALIST_REASONS = (
    "it cannot meet the latency budget at peak load",
    "its memory footprint exceeds the deployment target",
    "it does not support the required data format",
    "it fails under concurrent writes",
)


def feasible_options(task: Task) -> tuple[str, ...]:
    return tuple(o for o in task.options
                 if not any(o in e.objections for e in task.evidence.values()))


def best_feasible(task: Task) -> str | None:
    scores = task.evidence_for("analyst").scores
    feasible = feasible_options(task)
    if not feasible:
        return None
    return max(feasible, key=lambda o: (scores.get(o, 0.0), -task.options.index(o)))


def architecture_task() -> Task:
    """
    The hand-written demo task.

    The analyst ranks Option A highest, but the critic and the specialist each
    know a reason to rule it out. Option B is acceptable to everyone.
    """
    evidence = {
        "analyst": Evidence(scores={"Option A": 0.82, "Option B": 0.71}),
        "critic": Evidence(objections={
            "Option A": "the shared cache makes runs depend on request order, which violates "
                        "constraint C3 (runs must be reproducible)",
        }),
        "specialist": Evidence(objections={
            "Option A": "it cannot meet the 200 ms latency budget at peak load",
        }),
    }
    task = Task(
        task_id="architecture",
        benchmark="synthetic",
        question=(
            "Choose the architecture for the reasoning service: Option A (single in-process "
            "service with a shared cache) or Option B (queue-backed worker pool)."
        ),
        options=("Option A", "Option B"),
        domain="synthetic",
        evidence=evidence,
    )
    return Task(**{**task.__dict__, "reference": best_feasible(task)})


class SyntheticBenchmark:
    """
    Args:
        n_options: Options per task (2-26)
        objection_rate: Probability that the critic / specialist rules out an option
        min_benefit: The analyst rules out options scored below this
    """

    name = "synthetic"

    def __init__(self, n_options: int = 3, objection_rate: float = 0.3,
                 min_benefit: float = 0.4) -> None:
        if not 2 <= n_options <= 26:
            raise ValueError("n_options must be between 2 and 26")
        self.n_options = n_options
        self.objection_rate = objection_rate
        self.min_benefit = min_benefit

    def load(self, n: int | None = None, seed: int = 0) -> list[Task]:
        n = 100 if n is None else n
        rng = random.Random(seed)
        options = tuple(f"Option {chr(ord('A') + i)}" for i in range(self.n_options))
        tasks = []
        for i in range(n):
            scores = {o: round(rng.uniform(0.2, 0.95), 2) for o in options}
            analyst_obj = {
                o: f"its estimated benefit ({s:.2f}) is below the {self.min_benefit:.2f} minimum"
                for o, s in scores.items() if s < self.min_benefit
            }
            critic_obj = {o: rng.choice(_CRITIC_REASONS) for o in options
                          if rng.random() < self.objection_rate}
            spec_obj = {o: rng.choice(_SPECIALIST_REASONS) for o in options
                        if rng.random() < self.objection_rate}
            task = Task(
                task_id=f"syn-s{seed}-{i:03d}",
                benchmark=self.name,
                question=f"Select one of {', '.join(options)} for synthetic scenario {i}.",
                options=options,
                domain="synthetic",
                evidence={
                    "analyst": Evidence(scores=scores, objections=analyst_obj),
                    "critic": Evidence(objections=critic_obj),
                    "specialist": Evidence(objections=spec_obj),
                },
            )
            tasks.append(Task(**{**task.__dict__, "reference": best_feasible(task)}))
        return tasks

    def score(self, task: Task, prediction: str | None) -> Score:
        reference = task.reference
        correct = prediction is not None and prediction == reference
        return Score(correct=correct, value=1.0 if correct else 0.0,
                     detail={"reference": reference, "feasible": list(feasible_options(task))})
