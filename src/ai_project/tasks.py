"""
Decision tasks: what the agents reason about.

A ``DecisionTask`` is a question with a fixed set of options. The *evidence*
about those options is partitioned by role, the way a blackboard system
partitions expertise: the analyst holds benefit estimates, the critic knows
which options break hard constraints, the specialist knows domain limits.
Only the question and the option names are published on the Blackboard;
each agent receives its own role's evidence privately.

Because the evidence is explicit, a task also has a ground truth: an option
is *feasible* if no role objects to it, and the best feasible option is the
feasible one with the highest analyst score. Experiments use this to check
whether a consensus is actually a good decision.

``generate_tasks`` builds synthetic tasks from a seed. They are procedurally
generated test inputs, not a benchmark.
"""

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

ROLES = ("analyst", "critic", "specialist")


@dataclass(frozen=True)
class Evidence:
    """
    One role's private knowledge about the options.

    Attributes:
        scores: Preference score per option (higher is better); roles without
            scores fall back to option order
        objections: {option: reason} for options this role rules out
    """

    scores: Mapping[str, float] = field(default_factory=dict)
    objections: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"scores": dict(self.scores), "objections": dict(self.objections)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Evidence":
        return cls(scores=dict(data.get("scores", {})), objections=dict(data.get("objections", {})))


@dataclass(frozen=True)
class DecisionTask:
    """A question, its options, and the role-partitioned evidence about them."""

    task_id: str
    question: str
    options: tuple[str, ...]
    evidence: Mapping[str, Evidence]

    def evidence_for(self, role: str) -> Evidence:
        """Evidence held by ``role`` (empty if the role has none)."""
        return self.evidence.get(role, Evidence())

    def feasible_options(self) -> tuple[str, ...]:
        """Options that no role objects to."""
        return tuple(
            o for o in self.options if not any(o in e.objections for e in self.evidence.values())
        )

    def best_feasible(self) -> str | None:
        """Feasible option with the highest analyst score (ties: option order)."""
        scores = self.evidence_for("analyst").scores
        feasible = self.feasible_options()
        if not feasible:
            return None
        return max(feasible, key=lambda o: (scores.get(o, 0.0), -self.options.index(o)))

    def board_metadata(self) -> dict[str, Any]:
        """Public task information published on the Blackboard."""
        return {"task_id": self.task_id, "options": list(self.options)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "question": self.question,
            "options": list(self.options),
            "evidence": {role: e.to_dict() for role, e in self.evidence.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DecisionTask":
        return cls(
            task_id=data["task_id"],
            question=data["question"],
            options=tuple(data["options"]),
            evidence={r: Evidence.from_dict(e) for r, e in data["evidence"].items()},
        )


def flash_talk_task() -> DecisionTask:
    """
    The hand-written task used by the Flash Talk demo.

    The analyst ranks Option A highest, but the critic and the specialist each
    know a reason to rule it out. Option B is acceptable to everyone, yet in
    the forward run nobody puts it on the table, so the run deadlocks.
    """
    return DecisionTask(
        task_id="flash-talk",
        question=(
            "Choose the architecture for the reasoning service: "
            "Option A (single in-process service with a shared cache) or "
            "Option B (queue-backed worker pool)."
        ),
        options=("Option A", "Option B"),
        evidence={
            "analyst": Evidence(scores={"Option A": 0.82, "Option B": 0.71}),
            "critic": Evidence(
                objections={
                    "Option A": "the shared cache makes runs depend on request order, "
                    "which violates constraint C3 (runs must be reproducible)"
                }
            ),
            "specialist": Evidence(
                objections={"Option A": "it cannot meet the 200 ms latency budget at peak load"}
            ),
        },
    )


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


def generate_tasks(
    n: int,
    seed: int,
    n_options: int = 3,
    objection_rate: float = 0.3,
    min_benefit: float = 0.4,
) -> list[DecisionTask]:
    """
    Generate ``n`` synthetic decision tasks deterministically from ``seed``.

    Per option: the analyst's benefit score is uniform in [0.2, 0.95] and the
    analyst objects below ``min_benefit``; the critic and the specialist each
    object independently with probability ``objection_rate``.
    """
    if not 2 <= n_options <= 26:
        raise ValueError("n_options must be between 2 and 26")
    rng = random.Random(seed)
    options = tuple(f"Option {chr(ord('A') + i)}" for i in range(n_options))
    tasks = []
    for i in range(n):
        scores = {o: round(rng.uniform(0.2, 0.95), 2) for o in options}
        analyst_obj = {
            o: f"its estimated benefit ({s:.2f}) is below the {min_benefit:.2f} minimum"
            for o, s in scores.items()
            if s < min_benefit
        }
        critic_obj = {o: rng.choice(_CRITIC_REASONS) for o in options if rng.random() < objection_rate}
        spec_obj = {
            o: rng.choice(_SPECIALIST_REASONS) for o in options if rng.random() < objection_rate
        }
        tasks.append(
            DecisionTask(
                task_id=f"s{seed}-t{i:03d}",
                question=f"Synthetic task {i}: select one of {', '.join(options)}.",
                options=options,
                evidence={
                    "analyst": Evidence(scores=scores, objections=analyst_obj),
                    "critic": Evidence(objections=critic_obj),
                    "specialist": Evidence(objections=spec_obj),
                },
            )
        )
    return tasks
