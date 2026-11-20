"""
Live sessions for the web UI.

A ``LiveSession`` runs a ``Session`` in a worker thread and fans its events
out to WebSocket subscribers:

    {"type": "board", "event": BoardEvent}        every live Blackboard event
    {"type": "cf", "kind": "cf.*", "data": {...}} counterfactual sandbox progress
    {"type": "end", "result": SessionResult}      once, when the session ends
    {"type": "error", "message": str}             if the session crashed

A late subscriber first receives everything so far (board events, the
counterfactual log, the end message), then live events, with no gaps and no
duplicates: it is registered before the backlog is read, and live board
events at or below the backlog's last sequence number are dropped.
"""

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ai_project.blackboard.models import BoardEvent
from ai_project.session import Session

logger = logging.getLogger(__name__)


@dataclass
class Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue
    after_seq: int = 0


@dataclass
class LiveSession:
    session: Session
    meta: dict[str, Any]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: str = "created"  # created | running | finished | error
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: float = 0.0
    cf_log: list[dict[str, Any]] = field(default_factory=list)
    _subscribers: list[Subscriber] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _thread: threading.Thread | None = None

    def start(self) -> None:
        self.session.board.subscribe(self._on_board)
        self.session.listener = self._on_cf
        self.state = "running"
        self.started_at = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"session-{self.id}")
        self._thread.start()

    def _run(self) -> None:
        try:
            result = self.session.run().to_dict()
        except Exception as exc:  # surface the crash to the UI instead of a silent thread death
            logger.exception("Session %s crashed", self.id)
            error = f"{type(exc).__name__}: {exc}"
            self._broadcast({"type": "error", "message": error},
                            update={"state": "error", "error": error})
            return
        self._broadcast({"type": "end", "result": result},
                        update={"state": "finished", "result": result})

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    # ------------------------------------------------------------------ fan-out

    def _on_board(self, event: BoardEvent) -> None:
        self._broadcast({"type": "board", "event": event.to_dict()}, seq=event.seq)

    def _on_cf(self, kind: str, data: dict[str, Any]) -> None:
        self._broadcast({"type": "cf", "kind": kind, "data": data}, log=True)

    def _broadcast(self, message: dict[str, Any], seq: int | None = None, log: bool = False,
                   update: dict[str, Any] | None = None) -> None:
        """
        Send ``message`` to current subscribers. Logging it (``log``) and state
        changes (``update``) happen under the same lock as reading the
        subscriber list, so a subscriber sees each message exactly once:
        either in its backlog or live.
        """
        with self._lock:
            if log:
                self.cf_log.append(message)
            for key, value in (update or {}).items():
                setattr(self, key, value)
            subscribers = list(self._subscribers)
        for sub in subscribers:
            if seq is not None and seq <= sub.after_seq:
                continue
            try:
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, message)
            except RuntimeError:  # the subscriber's loop has closed
                self.unsubscribe(sub)

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> tuple[Subscriber, list[dict]]:
        """Register a subscriber and return it with the backlog it must send first."""
        sub = Subscriber(loop=loop, queue=asyncio.Queue())
        with self._lock:
            self._subscribers.append(sub)
            cf_log = list(self.cf_log)
            events = self.session.board.get_events()
            sub.after_seq = events[-1].seq if events else 0
            # cf messages logged after this point arrive through the queue
            backlog = [{"type": "board", "event": e.to_dict()} for e in events]
            backlog += cf_log
            if self.state == "finished":
                backlog.append({"type": "end", "result": self.result})
            elif self.state == "error":
                backlog.append({"type": "error", "message": self.error})
        return sub, backlog

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            if sub in self._subscribers:
                self._subscribers.remove(sub)

    # ------------------------------------------------------------------ control

    def control(self, action: str) -> None:
        control = self.session.control
        actions = {"pause": control.pause, "resume": control.resume, "step": control.step,
                   "stop": control.stop}
        if action not in actions:
            raise ValueError(f"Unknown action '{action}'. Use one of {sorted(actions)}")
        actions[action]()

    def summary(self) -> dict[str, Any]:
        state = self.session.board.get_state()
        return {
            "id": self.id,
            "state": self.state,
            "paused": self.session.control.paused,
            "status": state.status.value,
            "messages": state.iteration,
            "version": state.version,
            "started_at": self.started_at,
            "error": self.error,
            **self.meta,
        }


class SessionManager:
    def __init__(self, max_sessions: int = 50) -> None:
        self.max_sessions = max_sessions
        self._sessions: dict[str, LiveSession] = {}
        self._lock = threading.Lock()

    def add(self, live: LiveSession) -> LiveSession:
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                finished = [s for s in self._sessions.values() if s.state != "running"]
                for old in sorted(finished, key=lambda s: s.started_at)[: len(finished) // 2 + 1]:
                    del self._sessions[old.id]
            self._sessions[live.id] = live
        return live

    def get(self, session_id: str) -> LiveSession:
        with self._lock:
            return self._sessions[session_id]

    def all(self) -> list[LiveSession]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda s: s.started_at, reverse=True)
