import copy
import threading
from typing import Any, Dict, List, Optional

from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.protocol.validator import PXPValidator

from ai_project.blackboard.models import (
    BlackboardState,
    BlackboardStatus,
    HistoryEvent,
    BlackboardSnapshot,
)
from ai_project.blackboard.history import History
from ai_project.blackboard.exceptions import (
    BlackboardError,
    InvalidMessageError,
    BlackboardNotInitializedError,
    InvalidStatusTransitionError,
    SnapshotError,
)


class Blackboard:
    """
    Thread-safe Blackboard for multi-agent communication via PXP protocol.

    Provides a central state store with:
    - Structured message publishing with validation
    - Append-only history log
    - Snapshot isolation for counterfactual reasoning
    - Serialization support

    Example:
        board = Blackboard()
        board.initialize_task("Choose the best option")
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason...")
        board.publish_message(msg)
        state = board.get_state()
    """

    def __init__(self) -> None:
        self._state: Optional[BlackboardState] = None
        self._history = History()
        self._lock = threading.RLock()
        self._initialized = False

    def initialize_task(self, task: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize a new task on the Blackboard.

        Args:
            task: Task description
            metadata: Optional additional metadata
        """
        with self._lock:
            self._state = BlackboardState(
                task=task,
                status=BlackboardStatus.INITIALIZED,
                iteration=0,
                metadata=metadata or {},
            )
            self._history.clear()
            self._initialized = True

    def _ensure_initialized(self) -> None:
        """Raise error if Blackboard not initialized."""
        if not self._initialized or self._state is None:
            raise BlackboardNotInitializedError("Blackboard not initialized. Call initialize_task() first.")

    def publish_message(self, message: PXPMessage) -> None:
        """
        Publish a PXP message to the Blackboard.

        Validates message before any state change.
        On success: updates state, increments iteration, appends to history.

        Args:
            message: PXPMessage to publish

        Raises:
            InvalidMessageError: If message fails validation
            BlackboardNotInitializedError: If board not initialized
        """
        # Validate FIRST - before any state mutation
        errors = PXPValidator.validate(message)
        if errors:
            error_msgs = "; ".join(f"{e.field}: {e.message}" for e in errors)
            raise InvalidMessageError(f"PXP message validation failed: {error_msgs}")

        with self._lock:
            self._ensure_initialized()

            # Ensure iteration matches expected (message.iteration should be current + 1)
            expected_iteration = self._state.iteration + 1
            if message.iteration != expected_iteration:
                # Auto-correct iteration to maintain consistency
                message.iteration = expected_iteration

            # Update state
            self._state.iteration = expected_iteration
            self._state.current_prediction = message.prediction
            self._state.current_explanation = message.explanation
            self._state.latest_message = message.to_dict()

            # Update status based on tag
            if message.tag == PXPTag.RATIFY:
                if self._state.status == BlackboardStatus.INITIALIZED:
                    self._state.status = BlackboardStatus.RUNNING
            elif message.tag in (PXPTag.REFUTE, PXPTag.REJECT):
                self._state.status = BlackboardStatus.RUNNING  # Disagreement keeps it running
            # REVISE doesn't change status

            # Record event in history
            event = HistoryEvent.from_message(message, expected_iteration)
            self._history.append(event)

    def get_state(self) -> BlackboardState:
        """
        Get current Blackboard state.

        Returns:
            Copy of current BlackboardState

        Raises:
            BlackboardNotInitializedError: If board not initialized
        """
        with self._lock:
            self._ensure_initialized()
            # Return a copy to prevent external mutation
            return BlackboardState(
                task=self._state.task,
                status=self._state.status,
                iteration=self._state.iteration,
                current_prediction=self._state.current_prediction,
                current_explanation=self._state.current_explanation,
                latest_message=self._state.latest_message,
                metadata=dict(self._state.metadata),
            )

    def get_latest_message(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest accepted message as a dictionary.

        Returns:
            Latest message dict or None if no messages yet

        Raises:
            BlackboardNotInitializedError: If board not initialized
        """
        with self._lock:
            self._ensure_initialized()
            return self._state.latest_message

    def get_history(self) -> List[HistoryEvent]:
        """
        Get the complete event history.

        Returns:
            List of HistoryEvent objects in chronological order

        Raises:
            BlackboardNotInitializedError: If board not initialized
        """
        with self._lock:
            self._ensure_initialized()
            return self._history.get_all()

    def get_iteration(self) -> int:
        """
        Get current iteration number.

        Returns:
            Current iteration (0 if no messages published)

        Raises:
            BlackboardNotInitializedError: If board not initialized
        """
        with self._lock:
            self._ensure_initialized()
            return self._state.iteration

    def set_status(self, status: BlackboardStatus) -> None:
        """
        Set the Blackboard status.

        Args:
            status: New BlackboardStatus

        Raises:
            BlackboardNotInitializedError: If board not initialized
            InvalidStatusTransitionError: If transition is invalid
        """
        with self._lock:
            self._ensure_initialized()

            # Validate transition
            current = self._state.status
            valid_transitions = {
                BlackboardStatus.INITIALIZED: [BlackboardStatus.RUNNING, BlackboardStatus.FAILED],
                BlackboardStatus.RUNNING: [BlackboardStatus.CONSENSUS, BlackboardStatus.DEADLOCK, BlackboardStatus.FAILED],
                BlackboardStatus.CONSENSUS: [BlackboardStatus.FAILED],
                BlackboardStatus.DEADLOCK: [BlackboardStatus.RUNNING, BlackboardStatus.FAILED],
                BlackboardStatus.FAILED: [],
            }

            if status not in valid_transitions.get(current, []):
                raise InvalidStatusTransitionError(
                    f"Invalid status transition: {current.value} -> {status.value}"
                )

            self._state.status = status

    def record_event(self, event: HistoryEvent) -> None:
        """
        Manually record an event in history (for scheduler/counterfactual use).

        Args:
            event: HistoryEvent to record

        Raises:
            BlackboardNotInitializedError: If board not initialized
        """
        with self._lock:
            self._ensure_initialized()
            self._history.append(event)

    def snapshot(self) -> BlackboardSnapshot:
        """
        Create an independent snapshot of current state and history.

        The snapshot is a deep copy - modifying it does not affect the live Blackboard.

        Returns:
            BlackboardSnapshot with copied state and history

        Raises:
            BlackboardNotInitializedError: If board not initialized
            SnapshotError: If snapshot creation fails
        """
        with self._lock:
            self._ensure_initialized()
            try:
                return BlackboardSnapshot(
                    state=self._state,
                    history=self._history.get_all(),
                )
            except Exception as e:
                raise SnapshotError(f"Failed to create snapshot: {e}")

    def load_snapshot(self, snapshot: BlackboardSnapshot) -> None:
        """
        Load state from a snapshot (for counterfactual replay).

        Args:
            snapshot: BlackboardSnapshot to restore from

        Raises:
            BlackboardError: If snapshot is invalid
        """
        with self._lock:
            if not isinstance(snapshot, BlackboardSnapshot):
                raise BlackboardError("Invalid snapshot object")
            self._state = copy.deepcopy(snapshot.state)
            self._history.clear()
            for event in snapshot.history:
                self._history.append(event)
            self._initialized = True

    def clear(self) -> None:
        """Reset Blackboard to uninitialized state (for testing)."""
        with self._lock:
            self._state = None
            self._history.clear()
            self._initialized = False

    def reset(self) -> None:
        """Alias for clear()."""
        self.clear()