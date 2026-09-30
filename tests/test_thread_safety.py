import threading
import time
import pytest

from ai_project.protocol.pxp import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import BlackboardStatus
from ai_project.blackboard.exceptions import InvalidStatusTransitionError


class TestThreadSafety:
    """Tests for thread-safe Blackboard operations."""

    def setup_method(self) -> None:
        self.board = Blackboard()
        self.board.initialize_task("Concurrent test task")

    def test_concurrent_publish_messages(self) -> None:
        num_threads = 10
        messages_per_thread = 5
        errors = []

        def publish_messages(agent_id: str) -> None:
            try:
                for i in range(messages_per_thread):
                    msg = PXPMessage.create(
                        agent_id=agent_id,
                        tag=PXPTag.RATIFY if i % 2 == 0 else PXPTag.REVISE,
                        prediction=f"Option {i}",
                        explanation=f"Reason {i}",
                        confidence=0.8,
                        iteration=0,  # Will be auto-corrected
                    )
                    self.board.publish_message(msg)
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=publish_messages, args=(f"agent_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify final state
        final_iteration = self.board.get_iteration()
        expected_iterations = num_threads * messages_per_thread
        assert final_iteration == expected_iterations, f"Expected {expected_iterations}, got {final_iteration}"

        # Verify history length matches
        history_len = len(self.board.get_history())
        assert history_len == expected_iterations, f"History length {history_len} != {expected_iterations}"

    def test_no_history_entries_lost(self) -> None:
        num_threads = 5
        messages_per_thread = 10
        errors = []

        def publish_messages(agent_id: str) -> None:
            try:
                for i in range(messages_per_thread):
                    msg = PXPMessage.create(
                        agent_id=agent_id,
                        tag=PXPTag.RATIFY,
                        prediction=f"Option {i}",
                        explanation=f"Reason {i}",
                        confidence=0.8,
                        iteration=0,
                    )
                    self.board.publish_message(msg)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publish_messages, args=(f"agent_{i}",)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        history = self.board.get_history()
        assert len(history) == num_threads * messages_per_thread

        # Check all iterations are present and unique
        iterations = [e.iteration for e in history]
        assert len(set(iterations)) == len(iterations), "Duplicate iterations found"
        assert min(iterations) == 1
        assert max(iterations) == num_threads * messages_per_thread

    def test_concurrent_state_reads(self) -> None:
        num_readers = 20
        num_writers = 5
        messages_per_writer = 3
        read_results = []
        errors = []

        def writer(agent_id: str) -> None:
            try:
                for i in range(messages_per_writer):
                    msg = PXPMessage.create(
                        agent_id=agent_id,
                        tag=PXPTag.RATIFY,
                        prediction=f"Option {i}",
                        explanation=f"Reason {i}",
                        confidence=0.8,
                        iteration=0,
                    )
                    self.board.publish_message(msg)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader(reader_id: int) -> None:
            try:
                for _ in range(10):
                    state = self.board.get_state()
                    history = self.board.get_history()
                    iteration = self.board.get_iteration()
                    read_results.append((reader_id, iteration, len(history)))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(num_writers):
            t = threading.Thread(target=writer, args=(f"writer_{i}",))
            threads.append(t)
        for i in range(num_readers):
            t = threading.Thread(target=reader, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(read_results) > 0

    def test_concurrent_snapshot_and_publish(self) -> None:
        errors = []
        snapshots = []

        def publisher() -> None:
            try:
                for i in range(10):
                    msg = PXPMessage.create(
                        agent_id="publisher",
                        tag=PXPTag.RATIFY,
                        prediction=f"Option {i}",
                        explanation=f"Reason {i}",
                        confidence=0.8,
                        iteration=0,
                    )
                    self.board.publish_message(msg)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def snapshoter() -> None:
            try:
                for _ in range(5):
                    snap = self.board.snapshot()
                    snapshots.append(snap)
                    time.sleep(0.002)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=publisher)
        t2 = threading.Thread(target=snapshoter)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(snapshots) == 5

        # Verify snapshots are valid
        for snap in snapshots:
            assert snap.state.iteration >= 0
            assert len(snap.history) == snap.state.iteration

    def test_concurrent_set_status(self) -> None:
        self.board.set_status(BlackboardStatus.RUNNING)
        errors = []

        def status_changer() -> None:
            try:
                for status in [BlackboardStatus.DEADLOCK, BlackboardStatus.RUNNING, BlackboardStatus.DEADLOCK]:
                    self.board.set_status(status)
                    time.sleep(0.001)
            except InvalidStatusTransitionError:
                # Expected when multiple threads try invalid transitions concurrently
                pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=status_changer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not crash with unexpected errors
        assert len(errors) == 0
        final_status = self.board.get_state().status
        assert final_status in [BlackboardStatus.RUNNING, BlackboardStatus.DEADLOCK]