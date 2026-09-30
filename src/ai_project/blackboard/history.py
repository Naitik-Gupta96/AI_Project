from typing import List, Optional
import threading

from ai_project.blackboard.models import HistoryEvent


class History:
    """
    Append-only event log for the Blackboard.

    Thread-safe implementation using RLock.
    Past events are immutable once appended.
    """

    def __init__(self) -> None:
        self._events: List[HistoryEvent] = []
        self._lock = threading.RLock()

    def append(self, event: HistoryEvent) -> None:
        """
        Append an event to the history.

        Args:
            event: The HistoryEvent to append
        """
        with self._lock:
            # Ensure we store a copy to prevent external mutation
            self._events.append(event)

    def get_all(self) -> List[HistoryEvent]:
        """
        Get all events in chronological order.

        Returns:
            Copy of the event list
        """
        with self._lock:
            return list(self._events)

    def get_by_iteration(self, iteration: int) -> List[HistoryEvent]:
        """
        Get all events for a specific iteration.

        Args:
            iteration: The iteration number to filter by

        Returns:
            List of events for that iteration
        """
        with self._lock:
            return [e for e in self._events if e.iteration == iteration]

    def get_latest(self) -> Optional[HistoryEvent]:
        """
        Get the most recent event.

        Returns:
            Latest HistoryEvent or None if empty
        """
        with self._lock:
            if not self._events:
                return None
            return self._events[-1]

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def __iter__(self):
        with self._lock:
            return iter(list(self._events))

    def clear(self) -> None:
        """Clear all events (for testing/reset)."""
        with self._lock:
            self._events.clear()