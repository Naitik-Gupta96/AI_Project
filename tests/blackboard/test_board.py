import threading

import pytest

from ai_project.blackboard import (
    Blackboard,
    BlackboardError,
    BlackboardNotInitializedError,
    BlackboardStatus,
    InvalidMessageError,
    InvalidStatusTransitionError,
    VersionConflict,
)
from ai_project.blackboard.models import ACTIVATION, MESSAGE, TASK
from tests.helpers import msg


def test_requires_a_task():
    board = Blackboard()
    with pytest.raises(BlackboardNotInitializedError):
        board.commit(msg("a1", "INIT", "A"))
    with pytest.raises(BlackboardNotInitializedError):
        board.get_state()


def test_task_only_once(options_board):
    board = options_board()
    with pytest.raises(BlackboardError):
        board.initialize_task("again")


def test_task_sets_agents_and_default_weights(options_board):
    state = options_board().get_state()
    assert state.agents == ["a1", "a2", "a3"]
    assert state.weights == {"a1": 1.0, "a2": 1.0, "a3": 1.0}
    assert state.options == ("A", "B", "C")
    assert state.status == BlackboardStatus.INITIALIZED
    assert state.version == 1


def test_commit_assigns_number_reply_and_position(options_board):
    board = options_board()
    first = board.commit(msg("a1", "INIT", "A"))
    second = board.commit(msg("a2", "REFUTE", "B", judgment=(False, False, False)))
    assert (first.iteration, second.iteration) == (1, 2)
    assert first.in_reply_to is None
    assert second.in_reply_to == first.message_id
    state = board.get_state()
    assert state.status == BlackboardStatus.RUNNING
    assert state.positions["a2"]["prediction"] == "B"
    assert board.peer_message("a1").agent_id == "a2"
    assert board.peer_message("a2").agent_id == "a1"


def test_ungrammatical_message_changes_nothing(options_board):
    board = options_board()
    board.commit(msg("a1", "INIT", "A"))
    before = board.snapshot()
    with pytest.raises(InvalidMessageError) as info:
        board.commit(msg("a2", "RATIFY", "A", judgment=(False, False, False)))
    assert info.value.violations
    assert board.snapshot().events == before.events


def test_stale_write_raises_version_conflict(options_board):
    board = options_board()
    seen = board.version
    board.commit(msg("a1", "INIT", "A"))
    with pytest.raises(VersionConflict) as info:
        board.commit(msg("a2", "REFUTE", "B", judgment=(False, False, False)),
                     expected_version=seen)
    assert (info.value.expected, info.value.actual) == (seen, seen + 1)


def test_status_transitions(options_board):
    board = options_board()
    with pytest.raises(InvalidStatusTransitionError):
        board.set_status(BlackboardStatus.CONSENSUS)
    board.set_status(BlackboardStatus.RUNNING)
    board.set_status(BlackboardStatus.DEADLOCK, "stuck")
    with pytest.raises(BlackboardError):
        board.commit(msg("a1", "INIT", "A"))
    board.set_status(BlackboardStatus.RUNNING, "resumed")
    board.set_status(BlackboardStatus.CONSENSUS)
    with pytest.raises(InvalidStatusTransitionError):
        board.set_status(BlackboardStatus.RUNNING)


def test_context_revision_changes_the_grammar_reference(options_board):
    board = options_board()
    board.commit(msg("a1", "INIT", "A"))
    board.commit(msg("a2", "REFUTE", "B", judgment=(False, False, False)))
    board.revise_context("a1", "B", "B is fine after all")
    ctx = board.grammar_context("a1")
    assert ctx.own.prediction == "B"
    assert ctx.peer.prediction == "B"
    board.commit(msg("a1", "RATIFY", "B", judgment=(True, True, False)))


def test_weights(options_board):
    board = options_board()
    board.set_weight("a2", 0.5, "credit")
    assert board.get_state().weights["a2"] == 0.5
    with pytest.raises(ValueError):
        board.set_weight("a2", -1)


def test_record_only_accepts_record_kinds(options_board):
    board = options_board()
    board.record(ACTIVATION, {"round": 1})
    with pytest.raises(ValueError):
        board.record(MESSAGE, {})


def test_subscribers_see_every_event_after_it_is_applied(options_board):
    board = options_board()
    seen = []
    unsubscribe = board.subscribe(lambda e: seen.append((e.kind, board.version)))
    board.commit(msg("a1", "INIT", "A"))
    board.set_weight("a1", 0.9)
    unsubscribe()
    board.set_weight("a1", 0.8)
    assert seen == [(MESSAGE, 2), ("weight", 3)]


def test_failing_subscriber_does_not_break_the_board(options_board):
    board = options_board()

    def broken(_event):
        raise RuntimeError("socket closed")

    board.subscribe(broken)
    board.commit(msg("a1", "INIT", "A"))
    assert board.iteration == 1


def test_subscriber_may_read_the_board(options_board):
    board = options_board()
    reads = []
    board.subscribe(lambda e: reads.append(board.get_state().version))
    board.commit(msg("a1", "INIT", "A"))
    assert reads == [2]


def test_state_at_and_replay_match_live_state(options_board):
    board = options_board()
    board.commit(msg("a1", "INIT", "A"))
    board.set_weight("a3", 0.7)
    board.commit(msg("a2", "REFUTE", "B", judgment=(False, False, False)))
    assert board.state_at(1).task == "Pick one"
    assert board.state_at(2).iteration == 1
    assert board.state_at(board.version).to_dict() == board.get_state().to_dict()
    rebuilt = Blackboard.from_events(board.get_events())
    assert rebuilt.get_state().to_dict() == board.get_state().to_dict()
    assert [m.to_dict() for m in rebuilt.get_messages()] == \
           [m.to_dict() for m in board.get_messages()]


def test_snapshot_is_isolated(options_board):
    board = options_board()
    board.commit(msg("a1", "INIT", "A", metadata={"nested": {"x": 1}}))
    snap = board.snapshot()
    snap.events[1].data["message"]["metadata"]["nested"]["x"] = 99
    snap.state.weights["a1"] = 0.0
    assert board.get_messages()[0].metadata["nested"]["x"] == 1
    assert board.get_state().weights["a1"] == 1.0


def test_first_event_is_the_task(options_board):
    assert options_board().get_events()[0].kind == TASK


def test_concurrent_writers_with_versions_never_lose_updates(options_board):
    """Many threads race to post replies; each commit either lands or conflicts."""
    board = options_board(agents=[f"w{i}" for i in range(8)], options=("A",))
    board.commit(msg("w0", "INIT", "A"))
    results = []
    barrier = threading.Barrier(7, timeout=10)

    def writer(i):
        barrier.wait()
        version = board.version
        try:
            board.commit(msg(f"w{i}", "RATIFY", "A", judgment=(True, True, False)),
                         expected_version=version)
            results.append("ok")
        except (VersionConflict, InvalidMessageError):
            results.append("conflict")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(1, 8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == board.iteration - 1
    assert [m.iteration for m in board.get_messages()] == list(range(1, board.iteration + 1))
    assert board.version == len(board.get_events())
