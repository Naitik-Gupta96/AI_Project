"""
Ablation runner: the same tasks under each share of counterfactual-capable agents.

A configuration (TOML, see ``experiments/configs``) names the provider, the
benchmarks with their sample sizes, the groups (fractions of the team that are
counterfactual-capable) and the session settings. Every task runs once per
group, so groups are paired on tasks.

With three agents a fraction of 1/3 or 2/3 has three possible teams. Which
agents are capable rotates with the trial index, so every role is capable
equally often within a group.

Trials run in parallel threads (``workers``); the provider's broker bounds the
requests in flight. Each finished trial is appended to ``trials.jsonl``
immediately, so an interrupted run resumes where it stopped. With the response
cache on, the sessions of different groups share their model calls up to the
first deadlock (a counterfactual agent only acts after one), and those calls
are made once.
"""

import json
import threading
import time
import tomllib
import traceback
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_project import __version__
from ai_project.agents import build_team
from ai_project.benchmarks import registry
from ai_project.benchmarks.base import Benchmark, Task
from ai_project.blackboard import JsonStore
from ai_project.counterfactual import CounterfactualConfig
from ai_project.llm import prompts
from ai_project.llm.base import LLMProvider
from ai_project.llm.factory import make_provider
from ai_project.scheduler import ConsensusConfig, SchedulerConfig
from ai_project.session import Session, SessionConfig, SessionResult


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    n: int
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    provider: str
    benchmarks: tuple[BenchmarkSpec, ...]
    fractions: tuple[float, ...] = (0.0, 1 / 3, 2 / 3, 1.0)
    seed: int = 0
    workers: int = 8
    max_in_flight: int = 16
    cache: bool = True
    keep_sessions: bool = True
    session: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "ExperimentConfig":
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        return cls(
            name=raw["name"],
            provider=raw["provider"],
            benchmarks=tuple(BenchmarkSpec(b["name"], int(b["n"]), dict(b.get("options", {})))
                             for b in raw["benchmarks"]),
            fractions=tuple(raw.get("groups", {}).get("fractions", (0.0, 1 / 3, 2 / 3, 1.0))),
            seed=int(raw.get("seed", 0)),
            workers=int(raw.get("workers", 8)),
            max_in_flight=int(raw.get("max_in_flight", 16)),
            cache=bool(raw.get("cache", True)),
            keep_sessions=bool(raw.get("keep_sessions", True)),
            session=dict(raw.get("session", {})),
        )

    def session_config(self) -> SessionConfig:
        s = self.session
        return SessionConfig(
            scheduler=SchedulerConfig(
                max_messages=int(s.get("max_messages", 12)),
                max_concurrent_agents=int(s.get("max_concurrent_agents", 1)),
                consensus=ConsensusConfig(tau=float(s.get("tau", 0.75))),
            ),
            reject_after=int(s.get("reject_after", 3)),
            counterfactual=CounterfactualConfig(
                max_interventions=int(s.get("max_interventions", 2)),
                messages_per_agent=int(s.get("messages_per_agent", 3)),
                max_candidates=int(s.get("max_candidates", 3)),
                apply=str(s.get("apply", "both")),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "provider": self.provider, "seed": self.seed,
            "fractions": list(self.fractions), "workers": self.workers,
            "max_in_flight": self.max_in_flight, "cache": self.cache,
            "benchmarks": [{"name": b.name, "n": b.n, "options": b.options}
                           for b in self.benchmarks],
            "session": dict(self.session),
        }


def group_label(fraction: float) -> str:
    return f"cf{round(fraction * 100)}"


def capable_agents(roles: Sequence[str], fraction: float, index: int) -> tuple[str, ...]:
    """The counterfactual-capable agents for trial ``index``: ``fraction`` of the team, rotated."""
    k = round(fraction * len(roles))
    start = index % len(roles)
    chosen = {roles[(start + i) % len(roles)] for i in range(k)}
    return tuple(r for r in roles if r in chosen)


@dataclass(frozen=True)
class Trial:
    group: str
    fraction: float
    benchmark: str
    task: Task
    index: int

    @property
    def trial_id(self) -> str:
        return f"{self.group}|{self.task.task_id}"


def plan(config: ExperimentConfig, benchmarks: dict[str, Benchmark]) -> list[Trial]:
    trials = []
    for spec in config.benchmarks:
        tasks = benchmarks[spec.name].load(spec.n, seed=config.seed)
        for fraction in config.fractions:
            for index, task in enumerate(tasks):
                trials.append(Trial(group_label(fraction), fraction, spec.name, task, index))
    return trials


def record(trial: Trial, result: SessionResult) -> dict[str, Any]:
    """One line of trials.jsonl."""
    data = result.to_dict()
    interventions = data["interventions"]
    return {
        "trial_id": trial.trial_id,
        "group": trial.group,
        "cf_fraction": round(trial.fraction, 4),
        "cf_agents": data["cf_agents"],
        "benchmark": trial.benchmark,
        "task_id": trial.task.task_id,
        "domain": trial.task.domain,
        "task_meta": {k: v for k, v in trial.task.metadata.items() if k != "case"},
        "session_id": data["session_id"],
        "status": data["status"],
        "consensus": data["consensus"],
        "final_prediction": data["final_prediction"],
        "score": data["score"],
        "convergence_success": data["convergence_success"],
        "deadlocked": bool(interventions) or data["status"] == "DEADLOCK",
        "recovered": data["recovered"],
        "interventions_applied": sum(1 for i in interventions if i["applied"]),
        "branches": sum(len(i["branches"]) for i in interventions),
        "messages": data["messages"],
        "rounds": data["rounds"],
        "collisions": data["collisions"],
        "format_errors": data["format_errors"],
        "intelligibility": data["intelligibility"],
        "intelligibility_after_intervention": data["intelligibility_after_intervention"],
        "usage": data["usage"],
        "runtime_ms": data["runtime_ms"],
        "stop_reason": data["scheduler"]["stop_reason"],
        "error": data["scheduler"]["error"],
    }


class ExperimentRunner:
    """
    Args:
        config: The experiment
        out_root: Results go to ``out_root/<config.name>/``
        provider: Override the configured provider (tests)
        progress: Called with (done, total, record) after each trial
    """

    def __init__(self, config: ExperimentConfig, out_root: str | Path = "runs/experiments",
                 provider: LLMProvider | None = None,
                 progress: Callable[[int, int, dict[str, Any]], None] | None = None) -> None:
        self.config = config
        self.out = Path(out_root) / config.name
        self.out.mkdir(parents=True, exist_ok=True)
        cache = self.out / "cache.sqlite" if config.cache and config.provider != "mock" else None
        self.provider = provider or make_provider(config.provider, cache=cache,
                                                  max_in_flight=config.max_in_flight)
        self.progress = progress
        self.benchmarks = {b.name: registry.get_benchmark(b.name, **b.options)
                           for b in config.benchmarks}
        self.store = JsonStore(self.out / "sessions", fsync=False) if config.keep_sessions else None
        self._lock = threading.Lock()

    @property
    def trials_path(self) -> Path:
        return self.out / "trials.jsonl"

    def done(self) -> set[str]:
        if not self.trials_path.is_file():
            return set()
        ids = set()
        with open(self.trials_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        ids.add(json.loads(line)["trial_id"])
                    except (json.JSONDecodeError, KeyError):
                        continue  # torn last line from an interrupted run
        return ids

    def _repair(self) -> None:
        """Cut a torn last line left by an interrupted run, so new records start on a fresh line."""
        if not self.trials_path.is_file():
            return
        data = self.trials_path.read_bytes()
        if data and not data.endswith(b"\n"):
            self.trials_path.write_bytes(data[: data.rfind(b"\n") + 1])

    def run(self, resume: bool = True) -> Path:
        if not resume and self.trials_path.exists():
            self.trials_path.unlink()
        self._repair()
        trials = plan(self.config, self.benchmarks)
        finished = self.done()
        todo = [t for t in trials if t.trial_id not in finished]
        self._write_meta(len(trials))
        total, count = len(trials), len(trials) - len(todo)
        with ThreadPoolExecutor(max_workers=self.config.workers) as pool:
            futures = [pool.submit(self.run_trial, t) for t in todo]
            for future in as_completed(futures):
                line = future.result()
                with self._lock, open(self.trials_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
                count += 1
                if self.progress:
                    self.progress(count, total, line)
        return self.trials_path

    def run_trial(self, trial: Trial) -> dict[str, Any]:
        bench = self.benchmarks[trial.benchmark]
        roles = [r.role for r in prompts.roles(trial.task.domain)]
        cf = capable_agents(roles, trial.fraction, trial.index)
        if self.store is not None:
            # A trial that runs again (after --restart, or one cut off by an interruption) starts
            # a fresh log; appending would replay both sessions as one.
            self.store.discard(_safe(trial.trial_id))
        try:
            tools = registry.tool_factory(bench)
            team = build_team(trial.task, self.provider, tools=tools,
                              max_tool_calls=int(self.config.session.get("max_tool_calls", 4)))
            session = Session(trial.task, team, cf, self.config.session_config(), store=self.store,
                              session_id=_safe(trial.trial_id), benchmark=bench)
            return record(trial, session.run())
        except Exception as exc:  # one broken trial must not stop a 2,000-trial run
            return {"trial_id": trial.trial_id, "group": trial.group, "failed": True,
                    "cf_fraction": round(trial.fraction, 4), "cf_agents": list(cf),
                    "benchmark": trial.benchmark, "task_id": trial.task.task_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=5)}

    def _write_meta(self, total: int) -> None:
        meta = {
            "config": self.config.to_dict(),
            "provider": self.provider.describe(),
            "trials": total,
            "version": __version__,
            "git_commit": _git_commit(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        with open(self.out / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)


def _safe(trial_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in trial_id)[:150]


def _git_commit() -> str | None:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None
