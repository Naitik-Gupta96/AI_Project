import dataclasses
import pytest

from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import BlackboardSnapshot


class TestSnapshot:
    """Tests for snapshot functionality."""

    def setup_method(self) -> None:
        self.board = Blackboard()
        self.board.initialize_task("Test task")
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason 1", 0.8, 1)
        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "Option B", "Reason 2", 0.7, 2)
        self.board.publish_message(msg1)
        self.board.publish_message(msg2)

    def test_snapshot_contains_expected_state(self) -> None:
        snapshot = self.board.snapshot()
        assert snapshot.state.task == "Test task"
        assert snapshot.state.iteration == 2
        assert snapshot.state.current_prediction == "Option B"
        assert snapshot.state.current_explanation == "Reason 2"
        assert len(snapshot.history) == 2

    def test_snapshot_is_independent(self) -> None:
        snapshot = self.board.snapshot()
        # Modify snapshot
        snapshot.state.current_prediction = "Modified"
        snapshot.state.iteration = 999
        snapshot.history[0] = dataclasses.replace(snapshot.history[0], agent_id="MODIFIED")
        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.history[1].agent_id = "MODIFIED"

        # Live board should be unchanged
        live_state = self.board.get_state()
        assert live_state.current_prediction == "Option B"
        assert live_state.iteration == 2
        assert self.board.get_history()[0].agent_id == "agent_A"

    def test_modifying_snapshot_does_not_affect_live_board(self) -> None:
        snapshot = self.board.snapshot()
        original_prediction = self.board.get_state().current_prediction

        # Mutate snapshot deeply
        snapshot.state.current_prediction = "Changed"
        snapshot.state.metadata["test"] = "mutated"
        snapshot.history.append(type("Event", (), {"agent_id": "fake"})())

        # Live board unchanged
        assert self.board.get_state().current_prediction == original_prediction
        assert "test" not in self.board.get_state().metadata
        assert len(self.board.get_history()) == 2

    def test_live_board_continues_after_snapshot(self) -> None:
        snapshot = self.board.snapshot()

        # Continue using live board
        msg3 = PXPMessage.create("agent_C", PXPTag.REVISE, "Option C", "Reason 3", 0.9, 3)
        self.board.publish_message(msg3)

        # Live board advanced
        assert self.board.get_iteration() == 3
        assert self.board.get_state().current_prediction == "Option C"

        # Snapshot unchanged
        assert snapshot.state.iteration == 2
        assert snapshot.state.current_prediction == "Option B"

    def test_snapshot_serialization(self) -> None:
        snapshot = self.board.snapshot()
        d = snapshot.to_dict()
        assert d["state"]["task"] == "Test task"
        assert d["state"]["iteration"] == 2
        assert len(d["history"]) == 2

        # Deserialize
        snapshot2 = BlackboardSnapshot.from_dict(d)
        assert snapshot2.state.task == "Test task"
        assert snapshot2.state.iteration == 2
        assert len(snapshot2.history) == 2

    def test_snapshot_timestamp(self) -> None:
        snapshot = self.board.snapshot()
        assert snapshot.timestamp.endswith("Z")