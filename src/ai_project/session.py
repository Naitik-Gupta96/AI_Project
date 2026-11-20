"""
One session end to end: the only path the CLI, the server and the experiments use.

    Task -> Blackboard (task, options, team, weights)
         -> Scheduler runs the team until CONSENSUS, DEADLOCK, FAILED or the budget
         -> on DEADLOCK, if some agents are counterfactual-capable and interventions
            remain: CounterfactualResolver runs the sandboxes and, if an alternative
            earns positive credit, changes the live board and the scheduler resumes
         -> SessionResult: outcome, score, intelligibility, tokens, interventions
"""

import time
import uuid
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from typing import Any

from ai_project.agents.base import Agent
from ai_project.benchmarks.base import Benchmark, Score, Task
from ai_project.blackboard import Blackboard, BlackboardStatus, BoardStore
from ai_project.counterfactual.resolver import (
    CounterfactualConfig,
    CounterfactualResolver,
    Intervention,
)
from ai_project.llm.usage import UsageMeter
from ai_project.protocol.grammar import PXPGrammar
from ai_project.protocol.intelligibility import classify
from ai_project.scheduler.arbiter import PriorityArbiter
from ai_project.scheduler.scheduler import Scheduler, SchedulerConfig, SchedulerResult, epoch_start

Listener = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class SessionConfig:
    """
    Attributes:
        scheduler: Budget, concurrency, consensus and deadlock rules
        reject_after: k in Algorithm 1 (REJECT allowed from message k+1)
        counterfactual: Sandbox and intervention settings
    """

    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    reject_after: int = 3
    counterfactual: CounterfactualConfig = field(default_factory=CounterfactualConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheduler": self.scheduler.to_dict(),
            "reject_after": self.reject_after,
            "counterfactual": self.counterfactual.to_dict(),
        }


@dataclass
class SessionResult:
    session_id: str
    task_id: str
    benchmark: str
    cf_agents: tuple[str, ...]
    status: str
    final_prediction: str | None
    score: Score | None
    messages: int
    rounds: int
    collisions: int
    format_errors: int
    interventions: list[Intervention]
    intelligibility: dict[str, Any]
    intelligibility_after_intervention: dict[str, Any] | None
    usage: dict[str, Any]
    runtime_ms: float
    scheduler: SchedulerResult
    config: dict[str, Any]

    @property
    def consensus(self) -> bool:
        return self.status == BlackboardStatus.CONSENSUS.value

    @property
    def recovered(self) -> bool:
        """Reached consensus after at least one applied intervention."""
        return self.consensus and any(i.applied for i in self.interventions)

    @property
    def convergence_success(self) -> bool:
        """Consensus within the budget on an accurate answer."""
        return self.consensus and self.score is not None and self.score.correct

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "benchmark": self.benchmark,
            "cf_agents": list(self.cf_agents),
            "status": self.status,
            "final_prediction": self.final_prediction,
            "score": self.score.to_dict() if self.score else None,
            "consensus": self.consensus,
            "recovered": self.recovered,
            "convergence_success": self.convergence_success,
            "messages": self.messages,
            "rounds": self.rounds,
            "collisions": self.collisions,
            "format_errors": self.format_errors,
            "interventions": [i.to_dict() for i in self.interventions],
            "intelligibility": self.intelligibility,
            "intelligibility_after_intervention": self.intelligibility_after_intervention,
            "usage": self.usage,
            "runtime_ms": round(self.runtime_ms, 1),
            "scheduler": self.scheduler.to_dict(),
            "config": self.config,
        }


class Session:
    """
    A runnable session. ``scheduler`` is the live scheduler while ``run`` is
    active, so a UI can pause, step or stop it.

    Args:
        task: The task
        agents: The team (share one UsageMeter to get session totals)
        cf_agents: Ids of counterfactual-capable agents
        config: Session configuration
        store: Where the board's events go (default: in memory)
        session_id: Board session id (default: generated)
        benchmark: Scores the final answer (optional)
        listener: Receives ("cf.*", data) progress from the counterfactual sandboxes
    """

    def __init__(
        self,
        task: Task,
        agents: Sequence[Agent],
        cf_agents: Collection[str] = (),
        config: SessionConfig | None = None,
        store: BoardStore | None = None,
        session_id: str | None = None,
        benchmark: Benchmark | None = None,
        listener: Listener | None = None,
    ) -> None:
        self.task = task
        self.agents = list(agents)
        ids = [a.agent_id for a in self.agents]
        unknown = set(cf_agents) - set(ids)
        if unknown:
            raise ValueError(f"Unknown counterfactual agents: {sorted(unknown)}")
        self.cf_agents = tuple(a for a in ids if a in set(cf_agents))
        self.config = config or SessionConfig()
        self.benchmark = benchmark
        self.listener = listener
        self.board = Blackboard(
            store=store,
            session_id=session_id or f"{task.task_id}-{uuid.uuid4().hex[:8]}",
            grammar=PXPGrammar(self.config.reject_after),
        )
        self.board.initialize_task(task.question, task.board_metadata(), agents=ids)
        self.arbiter = PriorityArbiter()
        self.scheduler: Scheduler | None = None
        self.interventions: list[Intervention] = []
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True
        if self.scheduler is not None:
            self.scheduler.stop()

    def run(self) -> SessionResult:
        start = time.perf_counter()
        resolver = CounterfactualResolver(self.config.counterfactual, self.config.scheduler,
                                          self.arbiter, self.listener)
        pending: set[str] = set()
        rounds = collisions = 0
        while True:
            self.scheduler = Scheduler(self.board, self.agents, self.arbiter,
                                       self.config.scheduler, pending)
            result = self.scheduler.run()
            rounds += result.rounds
            collisions += result.collisions
            applied = sum(1 for i in self.interventions if i.applied)
            if (self._stopped or not result.deadlocked or not self.cf_agents
                    or applied >= self.config.counterfactual.max_interventions):
                break
            intervention = resolver.intervene(self.board, self.agents, self.cf_agents)
            self.interventions.append(intervention)
            if not intervention.applied:
                break
            pending = {intervention.agent_id}
        return self._result(result, rounds, collisions, (time.perf_counter() - start) * 1000)

    def _result(self, result: SchedulerResult, rounds: int, collisions: int,
                runtime_ms: float) -> SessionResult:
        messages = self.board.get_messages()
        events = self.board.get_events()
        whole = classify([(m.agent_id, m.tag) for m in messages]).to_dict()
        after = None
        if any(i.applied for i in self.interventions):
            start = epoch_start(events)
            after = classify([(m.agent_id, m.tag) for m in messages
                              if m.iteration > start]).to_dict()
        score = self.benchmark.score(self.task, result.final_prediction) if self.benchmark else None
        usage = UsageMeter()
        for meter in {id(a.usage): a.usage for a in self.agents}.values():
            usage.merge(meter)
        self.board.store.write_meta(self.board.session_id, {
            "task": self.task.to_dict(),
            "cf_agents": list(self.cf_agents),
            "config": self.config.to_dict(),
            "status": result.status,
            "final_prediction": result.final_prediction,
            "score": score.to_dict() if score else None,
        })
        return SessionResult(
            session_id=self.board.session_id,
            task_id=self.task.task_id,
            benchmark=self.task.benchmark,
            cf_agents=self.cf_agents,
            status=result.status,
            final_prediction=result.final_prediction,
            score=score,
            messages=len(messages),
            rounds=rounds,
            collisions=collisions,
            format_errors=sum(1 for e in events if e.kind == "format_error"),
            interventions=self.interventions,
            intelligibility=whole,
            intelligibility_after_intervention=after,
            usage=usage.to_dict(),
            runtime_ms=runtime_ms,
            scheduler=result,
            config=self.config.to_dict(),
        )


def run_session(task: Task, agents: Sequence[Agent], cf_agents: Collection[str] = (),
                config: SessionConfig | None = None, **kwargs: Any) -> SessionResult:
    return Session(task, agents, cf_agents, config, **kwargs).run()
