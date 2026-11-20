"""
Retrospective credit assignment and its effect on the live board.

When the live board deadlocks, every counterfactual-capable agent:

1. Takes an isolated snapshot of the board.
2. Reflects on each of its last ``messages_per_agent`` messages: given the
   whole session, which alternative messages (different prediction, tag or
   explanation wording) could it have sent instead? Only grammatical
   candidates are kept.
3. Replays the session in a sandbox from each candidate (``sandbox.replay``).
4. Assigns credit to each candidate:

       credit = proximity(sandbox end) - proximity(live board at the deadlock)

   where proximity is the weighted share of the largest agreeing group
   (1.0 at consensus; see ``scheduler.consensus``).

The best candidate across all capable agents (highest credit; ties go to the
later message, i.e. the smaller change to history, then to team order) is
applied to the live board if its credit is positive:

    prompt   the agent adds the reflection's lesson to its system prompt and
             revises its local context to the candidate's position
             (a ``context_revision`` event)
    weight   the agent's voting weight becomes max(min_weight, w * (1 - eta * credit)):
             the more its own message is to blame for the deadlock, the less
             its continued dissent counts
    both     both (default)

The live board then goes from DEADLOCK back to RUNNING, with the agent
scheduled to post next. Everything is recorded as one ``intervention`` event,
including every sandbox branch.
"""

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from typing import Any

from ai_project.agents.base import Agent, AgentError
from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.blackboard.models import INTERVENTION, BoardEvent
from ai_project.counterfactual.sandbox import Branch, CounterfactualError, board_before, replay
from ai_project.scheduler.arbiter import PriorityArbiter
from ai_project.scheduler.consensus import evaluate_consensus
from ai_project.scheduler.scheduler import SchedulerConfig

APPLY_MODES = ("prompt", "weight", "both")
Listener = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class CounterfactualConfig:
    """
    Attributes:
        max_interventions: Interventions allowed per session
        messages_per_agent: How many of its latest messages each agent reconsiders
        max_candidates: Alternatives per reconsidered message
        eta: Weight learning rate
        min_weight: Floor for a voting weight
        apply: "prompt", "weight" or "both"
    """

    max_interventions: int = 2
    messages_per_agent: int = 3
    max_candidates: int = 3
    eta: float = 0.5
    min_weight: float = 0.25
    apply: str = "both"

    def __post_init__(self) -> None:
        if self.apply not in APPLY_MODES:
            raise ValueError(f"apply must be one of {APPLY_MODES}")
        if not 0.0 <= self.eta <= 1.0:
            raise ValueError("eta must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Intervention:
    """What one resolution attempt did."""

    applied: bool
    agent_id: str | None
    branch: Branch | None
    branches: list[Branch] = field(default_factory=list)
    proximity_before: float = 0.0
    weight_before: float | None = None
    weight_after: float | None = None
    reflections: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "agent_id": self.agent_id,
            "chosen_branch": self.branch.branch_id if self.branch else None,
            "credit": round(self.branch.credit, 4) if self.branch else 0.0,
            "lesson": self.branch.lesson if self.branch else "",
            "proximity_before": round(self.proximity_before, 4),
            "weight_before": self.weight_before,
            "weight_after": self.weight_after,
            "branches": [b.to_dict() for b in self.branches],
            "reflections": self.reflections,
            "reason": self.reason,
        }


class CounterfactualResolver:
    def __init__(
        self,
        config: CounterfactualConfig | None = None,
        scheduler_config: SchedulerConfig | None = None,
        arbiter: PriorityArbiter | None = None,
        listener: Listener | None = None,
    ) -> None:
        self.config = config or CounterfactualConfig()
        self.scheduler_config = scheduler_config or SchedulerConfig()
        self.arbiter = arbiter
        self.listener = listener
        self._branch_counter = 0

    def intervene(
        self, board: Blackboard, agents: Sequence[Agent], cf_agents: Collection[str]
    ) -> Intervention:
        """Run the sandboxes for a deadlocked board and apply the best positive-credit change."""
        if board.status != BlackboardStatus.DEADLOCK:
            raise CounterfactualError("Counterfactual resolution needs a deadlocked board")
        by_id = {a.agent_id: a for a in agents}
        unknown = set(cf_agents) - set(by_id)
        if unknown:
            raise CounterfactualError(f"Unknown counterfactual agents: {sorted(unknown)}")

        snapshot = board.snapshot()
        state = snapshot.state
        messages = snapshot.messages
        before = evaluate_consensus(messages, state.agents or list(by_id), state.weights,
                                    self.scheduler_config.consensus).proximity
        self._emit("cf.start", {"cf_agents": list(cf_agents), "proximity": before,
                                "at_iteration": state.iteration})

        branches: list[Branch] = []
        reflections: list[dict[str, Any]] = []
        for agent in agents:
            if agent.agent_id not in cf_agents:
                continue
            own = [m for m in messages if m.agent_id == agent.agent_id]
            for target in reversed(own[-self.config.messages_per_agent:]):
                at_target = board_before(snapshot, target, board.grammar)
                try:
                    reflection, rejected = agent.clone("sandbox").reflect(
                        at_target, target, messages, self.config.max_candidates)
                except AgentError as exc:
                    reflections.append({"agent_id": agent.agent_id,
                                        "target": target.iteration, "error": str(exc)})
                    continue
                reflections.append({
                    "agent_id": agent.agent_id,
                    "target": target.iteration,
                    "candidates": len(reflection.candidates),
                    "rejected": rejected,
                    "lesson": reflection.lesson,
                })
                for candidate in reflection.candidates:
                    self._branch_counter += 1
                    branch_id = f"{board.session_id}-cf{self._branch_counter}"
                    self._emit("cf.branch_start", {
                        "branch_id": branch_id, "agent_id": agent.agent_id,
                        "target": target.to_dict(), "candidate": candidate.to_dict(),
                    })
                    branch = replay(
                        branch_id, snapshot, target, candidate, reflection.lesson, agents,
                        board.grammar, self.scheduler_config, self.arbiter,
                        on_event=self._forward(branch_id),
                    )
                    branch.credit = branch.proximity - before
                    branches.append(branch)
                    self._emit("cf.branch_end", branch.to_dict())

        order = {a.agent_id: i for i, a in enumerate(agents)}
        best = max(branches, key=lambda b: (b.credit, b.target.iteration, -order[b.agent_id]),
                   default=None)
        if best is None or best.credit <= 0:
            reason = ("No counterfactual-capable agent proposed an alternative" if best is None
                      else f"No alternative improved consensus proximity (best credit "
                           f"{best.credit:+.2f})")
            result = Intervention(False, None, None, branches, before, reflections=reflections,
                                  reason=reason)
            board.record(INTERVENTION, {**result.to_dict(), "at_iteration": state.iteration})
            self._emit("cf.none", result.to_dict())
            return result

        result = self._apply(board, by_id[best.agent_id], best, branches, before, reflections)
        self._emit("cf.applied", result.to_dict())
        return result

    def _apply(self, board: Blackboard, agent: Agent, best: Branch, branches: list[Branch],
               before: float, reflections: list[dict[str, Any]]) -> Intervention:
        mode = self.config.apply
        weight_before = board.get_state().weights.get(agent.agent_id, 1.0)
        weight_after = weight_before
        if mode in ("weight", "both"):
            weight_after = max(self.config.min_weight,
                               weight_before * (1 - self.config.eta * best.credit))
        result = Intervention(
            applied=True,
            agent_id=agent.agent_id,
            branch=best,
            branches=branches,
            proximity_before=before,
            weight_before=weight_before,
            weight_after=round(weight_after, 4),
            reflections=reflections,
            reason=(f"{agent.agent_id}'s message {best.target.iteration} "
                    f"({best.target.tag} {best.target.prediction}) gets credit {best.credit:+.2f}: "
                    f"{best.candidate.output.tag.value} {best.candidate.output.prediction} "
                    f"would have ended {best.result.status}"),
        )
        board.record(INTERVENTION, {**result.to_dict(), "apply": mode,
                                    "at_iteration": board.iteration})
        if mode in ("prompt", "both"):
            if best.lesson:
                agent.lessons.append(best.lesson)
            board.revise_context(agent.agent_id, best.candidate.output.prediction,
                                 best.candidate.output.explanation,
                                 reason=f"counterfactual intervention ({best.branch_id})")
        if weight_after != weight_before:
            board.set_weight(agent.agent_id, round(weight_after, 4),
                             reason=f"credit {best.credit:+.2f} from {best.branch_id}")
        board.set_status(BlackboardStatus.RUNNING, f"resumed after {agent.agent_id}'s intervention")
        return result

    def _emit(self, kind: str, data: dict[str, Any]) -> None:
        if self.listener is not None:
            self.listener(kind, data)

    def _forward(self, branch_id: str) -> Callable[[BoardEvent], None] | None:
        if self.listener is None:
            return None
        listener = self.listener

        def forward(event: BoardEvent) -> None:
            listener("cf.branch_event", {"branch_id": branch_id, "event": event.to_dict()})

        return forward
