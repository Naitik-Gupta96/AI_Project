import pytest

from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import HistoryEvent


class TestHistory:
    """Tests for History functionality."""

    def setup_method(self) -> None:
        self.board = Blackboard()
        self.board.initialize_task("Test task")

    def test_history_append_and_retrieve(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason", 0.8, 1)
        self.board.publish_message(msg)
        history = self.board.get_history()
        assert len(history) == 1
        assert history[0].agent_id == "agent_A"
        assert history[0].tag == "RATIFY"

    def test_history_ordering(self) -> None:
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "R1", 0.8, 1)
        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "B", "R2", 0.7, 2)
        msg3 = PXPMessage.create("agent_C", PXPTag.REVISE, "C", "R3", 0.9, 3)
        self.board.publish_message(msg1)
        self.board.publish_message(msg2)
        self.board.publish_message(msg3)
        history = self.board.get_history()
        assert history[0].agent_id == "agent_A"
        assert history[1].agent_id == "agent_B"
        assert history[2].agent_id == "agent_C"

    def test_history_immutable_past_events(self) -> None:
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "R1", 0.8, 1)
        self.board.publish_message(msg1)
        history = self.board.get_history()
        first_event = history[0]

        # Publish another message
        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "B", "R2", 0.7, 2)
        self.board.publish_message(msg2)

        # Original event should be unchanged
        assert first_event.agent_id == "agent_A"
        assert first_event.tag == "RATIFY"
        assert first_event.iteration == 1

    def test_history_get_by_iteration(self) -> None:
        # Note: Blackboard auto-corrects iteration to be sequential
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "R1", 0.8, 1)
        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "B", "R2", 0.7, 2)
        msg3 = PXPMessage.create("agent_A", PXPTag.REVISE, "C", "R3", 0.9, 3)
        self.board.publish_message(msg1)
        self.board.publish_message(msg2)
        self.board.publish_message(msg3)

        iter1 = self.board.get_history()  # All history
        # Filter by iteration
        from ai_project.blackboard.history import History
        hist = History()
        for e in iter1:
            hist.append(e)

        events_iter1 = hist.get_by_iteration(1)
        events_iter2 = hist.get_by_iteration(2)
        events_iter3 = hist.get_by_iteration(3)
        assert len(events_iter1) == 1
        assert len(events_iter2) == 1
        assert len(events_iter3) == 1

    def test_history_get_latest(self) -> None:
        msg1 = PXPMessage.create("agent_A", PXPTag.RATIFY, "B", "R1", 0.8, 1)
        self.board.publish_message(msg1)
        latest = self.board.get_history()[-1]
        assert latest.agent_id == "agent_A"

        msg2 = PXPMessage.create("agent_B", PXPTag.REFUTE, "B", "R2", 0.7, 2)
        self.board.publish_message(msg2)
        latest = self.board.get_history()[-1]
        assert latest.agent_id == "agent_B"

    def test_history_from_message(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.82, 3)
        event = HistoryEvent.from_message(msg, 3)
        assert event.iteration == 3
        assert event.agent_id == "agent_A"
        assert event.tag == "RATIFY"
        assert event.prediction == "Option B"
        assert event.explanation == "Good choice"
        assert event.confidence == 0.82
        assert event.message_id == msg.message_id

    def test_history_event_serialization(self) -> None:
        msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Good choice", 0.82, 3)
        event = HistoryEvent.from_message(msg, 3)
        d = event.to_dict()
        assert d["iteration"] == 3
        assert d["agent_id"] == "agent_A"
        assert d["tag"] == "RATIFY"
        assert d["confidence"] == 0.82

        event2 = HistoryEvent.from_dict(d)
        assert event2.iteration == event.iteration
        assert event2.agent_id == event.agent_id
        assert event2.confidence == event.confidence