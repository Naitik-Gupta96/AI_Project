"""
Retrospective sandbox: replay a session from one of its past messages with
that message replaced.

    live board --snapshot()--> events (deep copy)
        -> sandbox board: events up to just before the target message, replayed
           into a private MemoryStore (the live board is never written to)
        -> commit the candidate message in place of the target (grammar-checked)
        -> a Scheduler drives cloned agents forward on the sandbox board
        -> result + every sandbox event, for credit assignment and the UI
"""

import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ai_project.agents.base import Agent
from ai_project.agents.models import Candidate
from ai_project.blackboard import Blackboard, BlackboardSnapshot, MemoryStore
from ai_project.blackboard.models import MESSAGE, BoardEvent, MessageRecord
from ai_project.protocol.grammar import PXPGrammar
from ai_project.scheduler.arbiter import PriorityArbiter
from ai_project.scheduler.scheduler import Scheduler, SchedulerConfig, SchedulerResult


class CounterfactualError(Exception):
    """Invalid target or candidate."""


def events_before(snapshot: BlackboardSnapshot, target: MessageRecord) -> list[BoardEvent]:
    """The live events that precede ``target``'s commit."""
    for i, event in enumerate(snapshot.events):
        if event.kind == MESSAGE and event.data["message"]["message_id"] == target.message_id:
            return snapshot.events[:i]
    raise CounterfactualError(f"Message {target.message_id} is not in the snapshot")


def board_before(snapshot: BlackboardSnapshot, target: MessageRecord,
                 grammar: PXPGrammar, session_id: str = "sandbox") -> Blackboard:
    """An isolated board in the state the live board had just before ``target``."""
    return Blackboard.from_events(events_before(snapshot, target), store=MemoryStore(),
                                  session_id=session_id, grammar=grammar, persist=True)


@dataclass
class Branch:
    """
    One replayed alternative timeline.

    Attributes:
        branch_id: Unique within one resolution
        agent_id: Agent whose message was replaced
        target: The replaced message
        candidate: The replacement
        lesson: The lesson the agent drew in that reflection
        result: Outcome of the replay
        proximity: Consensus proximity at the end of the replay (1.0 at consensus)
        credit: proximity - the live board's proximity at the deadlock
        messages: Sandbox messages from the branch point on
        events: Every sandbox event from the branch point on
    """

    branch_id: str
    agent_id: str
    target: MessageRecord
    candidate: Candidate
    lesson: str
    result: SchedulerResult
    proximity: float
    credit: float = 0.0
    messages: list[MessageRecord] = field(default_factory=list)
    events: list[BoardEvent] = field(default_factory=list)

    def to_dict(self, include_events: bool = False) -> dict[str, Any]:
        data = {
            "branch_id": self.branch_id,
            "agent_id": self.agent_id,
            "target": self.target.to_dict(),
            "candidate": self.candidate.to_dict(),
            "lesson": self.lesson,
            "status": self.result.status,
            "final_prediction": self.result.final_prediction,
            "proximity": round(self.proximity, 4),
            "credit": round(self.credit, 4),
            "messages": [m.to_dict() for m in self.messages],
        }
        if include_events:
            data["events"] = [e.to_dict() for e in self.events]
        return data


def replay(
    branch_id: str,
    snapshot: BlackboardSnapshot,
    target: MessageRecord,
    candidate: Candidate,
    lesson: str,
    agents: Sequence[Agent],
    grammar: PXPGrammar,
    config: SchedulerConfig,
    arbiter: PriorityArbiter | None = None,
    on_event: Callable[[BoardEvent], None] | None = None,
) -> Branch:
    """
    Replace ``target`` with ``candidate`` and run the rest of the session in a sandbox.

    ``agents`` are the live agents; the sandbox uses clones, so the live agents'
    lessons are untouched and their provider calls count as sandbox usage.
    """
    board = board_before(snapshot, target, grammar, session_id=branch_id)
    start = board.version
    if on_event is not None:
        board.subscribe(on_event)
    message = copy.deepcopy(candidate.message)
    message.metadata = {**message.metadata, "counterfactual": True, "replaces": target.message_id}
    board.commit(message)
    clones = [a.clone("sandbox") for a in agents]
    result = Scheduler(board, clones, arbiter, config).run()
    events = board.get_events(since=start)
    messages = [m for m in board.get_messages() if m.iteration >= target.iteration]
    return Branch(
        branch_id=branch_id,
        agent_id=target.agent_id,
        target=target,
        candidate=candidate,
        lesson=lesson,
        result=result,
        proximity=result.consensus.proximity,
        messages=messages,
        events=events,
    )
