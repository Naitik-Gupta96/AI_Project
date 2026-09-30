import pytest

from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.blackboard.exceptions import (
    InvalidMessageError,
    BlackboardNotInitializedError,
    InvalidStatusTransitionError,
)


class TestBlackboardInitialization:
    """Tests for task initialization."""

    def test_task_initialization(self) -> None:
        board = Blackboard()
        board.initialize_task("Select the best approach")
        state = board.get_state()
        assert state.task == "Select the best approach"
        assert state.status == BlackboardStatus.INITIALIZED
        assert state.iteration == 0

    def test_task_initialization_with_metadata(self) -> None:
        board = Blackboard()
        board.initialize_task("Task", metadata={"source": "test", "priority": 1})
        state = board.get_state()
        assert state.metadata["source"] == "test"
        assert state.metadata["priority"] == 1

    def test_operations_before_init_fail(self) -> None:
        board = Blackboard()
        with pytest.raises(BlackboardNotInitializedError):
            board.get_state()
        with pytest.raises(BlackboardNotInitializedError):
            board.get_iteration()
        with pytest.raises(BlackboardNotInitializedError):
            board.get_history()
        with pytest.raises(BlackboardNotInitializedError):
            board.publish_message(PXPMessage.create("A", PXPTag.RATIFY, "B", "Reason"))


class TestBlackboardPublishMessage:
    """Tests for publishing messages."""

    def setup_method(self) -> None:
        self.board = Blackboard()
        self.board.initialize_task("Test task")

    def test_publish_valid_message(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.8, 1)
        self.board.publish_message(msg)
        assert self.board.get_iteration() == 1

    def test_latest_message_updated(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.8, 1)
        self.board.publish_message(msg)
        latest = self.board.get_latest_message()
        assert latest is not None
        assert latest["agent_id"] == "agent_A"
        assert latest["tag"] == "RATIFY"
        assert latest["prediction"] == "Option B"

    def test_current_prediction_updated(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.8, 1)
        self.board.publish_message(msg)
        state = self.board.get_state()
        assert state.current_prediction == "Option B"

    def test_current_explanation_updated(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.8, 1)
        self.board.publish_message(msg)
        state = self.board.get_state()
        assert state.current_explanation == "Good choice"

    def test_iteration_increments(self) -> None:
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason 1", 0.8, 1)
        self.board.publish_message(msg1)
        assert self.board.get_iteration() == 1

        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "Option B", "Reason 2", 0.7, 2)
        self.board.publish_message(msg2)
        assert self.board.get_iteration() == 2

    def test_history_entry_added(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.8, 1)
        self.board.publish_message(msg)
        history = self.board.get_history()
        assert len(history) == 1
        assert history[0].agent_id == "agent_A"
        assert history[0].tag == "RATIFY"
        assert history[0].iteration == 1

    def test_status_update_on_ratify(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.8, 1)
        self.board.publish_message(msg)
        state = self.board.get_state()
        assert state.status == BlackboardStatus.RUNNING

    def test_status_stays_running_on_refute(self) -> None:
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason 1", 0.8, 1)
        self.board.publish_message(msg1)
        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "Option B", "Reason 2", 0.7, 2)
        self.board.publish_message(msg2)
        state = self.board.get_state()
        assert state.status == BlackboardStatus.RUNNING

    def test_ordering_preserved(self) -> None:
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason 1", 0.8, 1)
        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "Option B", "Reason 2", 0.7, 2)
        msg3 = PXPMessage.create("agent_C", PXPTag.REVISE, "Option C", "Reason 3", 0.9, 3)
        self.board.publish_message(msg1)
        self.board.publish_message(msg2)
        self.board.publish_message(msg3)
        history = self.board.get_history()
        assert len(history) == 3
        assert history[0].agent_id == "agent_A"
        assert history[1].agent_id == "agent_B"
        assert history[2].agent_id == "agent_C"

    def test_invalid_message_does_not_mutate_state(self) -> None:
        # Publish valid message first
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason 1", 0.8, 1)
        self.board.publish_message(msg1)
        initial_iteration = self.board.get_iteration()
        initial_history_len = len(self.board.get_history())

        # Try to publish invalid message (missing explanation)
        msg_invalid = PXPMessage(
            message_id="msg_invalid",
            agent_id="agent_B",
            tag=PXPTag.REFUTE,
            prediction="Option B",
            explanation="",
            iteration=2,
        )
        with pytest.raises(InvalidMessageError):
            self.board.publish_message(msg_invalid)

        # State should be unchanged
        assert self.board.get_iteration() == initial_iteration
        assert len(self.board.get_history()) == initial_history_len
        state = self.board.get_state()
        assert state.current_prediction == "Option B"
        assert state.current_explanation == "Reason 1"

    def test_invalid_confidence_rejected(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "Reason", 1.5, 1)
        with pytest.raises(InvalidMessageError):
            self.board.publish_message(msg)

    def test_missing_prediction_rejected(self) -> None:
        msg = PXPMessage(
            message_id="msg_1",
            agent_id="agent_A",
            tag=PXPTag.RATIFY,
            prediction="",
            explanation="Reason",
            iteration=1,
        )
        with pytest.raises(InvalidMessageError):
            self.board.publish_message(msg)


class TestBlackboardStatus:
    """Tests for status management."""

    def setup_method(self) -> None:
        self.board = Blackboard()
        self.board.initialize_task("Test task")

    def test_set_status_valid(self) -> None:
        self.board.set_status(BlackboardStatus.RUNNING)
        assert self.board.get_state().status == BlackboardStatus.RUNNING

    def test_set_status_invalid_transition(self) -> None:
        # INITIALIZED -> CONSENSUS is invalid
        with pytest.raises(InvalidStatusTransitionError):
            self.board.set_status(BlackboardStatus.CONSENSUS)

    def test_set_status_valid_transitions(self) -> None:
        # INITIALIZED -> RUNNING
        self.board.set_status(BlackboardStatus.RUNNING)
        # RUNNING -> CONSENSUS
        self.board.set_status(BlackboardStatus.CONSENSUS)
        assert self.board.get_state().status == BlackboardStatus.CONSENSUS

    def test_set_status_deadlock_to_running(self) -> None:
        self.board.set_status(BlackboardStatus.RUNNING)
        self.board.set_status(BlackboardStatus.DEADLOCK)
        self.board.set_status(BlackboardStatus.RUNNING)
        assert self.board.get_state().status == BlackboardStatus.RUNNING


class TestBlackboardClear:
    """Tests for clear/reset."""

    def test_clear_resets_board(self) -> None:
        board = Blackboard()
        board.initialize_task("Task")
        board.publish_message(PXPMessage.create("A", PXPTag.RATIFY, "B", "Reason"))
        board.clear()
        with pytest.raises(BlackboardNotInitializedError):
            board.get_state()

    def test_reset_alias(self) -> None:
        board = Blackboard()
        board.initialize_task("Task")
        board.reset()
        with pytest.raises(BlackboardNotInitializedError):
            board.get_state()