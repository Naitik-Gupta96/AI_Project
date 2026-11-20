import pytest

from ai_project.deadlock import (
    RULE_REFUTE_LOOP,
    RULE_REJECT,
    RULE_STAGNATION,
    DeadlockConfig,
    DeadlockDetector,
)
from tests.helpers import msg


def messages(options_board, *items, agents=("a1", "a2", "a3")):
    board = options_board(agents=agents)
    for m in items:
        board.commit(m)
    return board.get_messages()


def test_reject_is_a_deadlock(options_board):
    ms = messages(options_board, msg("a1", "INIT", "A"),
                  msg("a2", "REFUTE", "B", judgment=(False, False, False)),
                  msg("a3", "RATIFY", "B", judgment=(True, True, False)),
                  msg("a1", "REJECT", "A", judgment=(False, False, False)))
    report = DeadlockDetector().detect(ms)
    assert report.deadlocked and report.rule == RULE_REJECT
    assert "a1" in report.objectors


def test_reject_before_the_epoch_is_ignored(options_board):
    ms = messages(options_board, msg("a1", "INIT", "A"),
                  msg("a2", "REFUTE", "B", judgment=(False, False, False)),
                  msg("a3", "RATIFY", "B", judgment=(True, True, False)),
                  msg("a1", "REJECT", "A", judgment=(False, False, False)))
    assert not DeadlockDetector().detect(ms, epoch_start=4).deadlocked


def test_refute_loop(options_board):
    ms = messages(options_board, msg("a1", "INIT", "A"),
                  msg("a2", "REFUTE", "B", judgment=(False, True, False)),
                  msg("a1", "REFUTE", "A", judgment=(False, True, False)),
                  msg("a2", "REFUTE", "B", judgment=(False, True, False)),
                  agents=("a1", "a2"))
    report = DeadlockDetector(DeadlockConfig(refute_streak=3)).detect(ms)
    assert report.rule == RULE_REFUTE_LOOP
    assert not DeadlockDetector(DeadlockConfig(refute_streak=4)).detect(ms).deadlocked


def test_stagnation(options_board):
    ms = messages(options_board, msg("a1", "INIT", "A"),
                  msg("a2", "REFUTE", "B", judgment=(False, True, False)),
                  msg("a1", "REVISE", "B", judgment=(False, True, True)),
                  msg("a2", "RATIFY", "B", judgment=(True, True, False)),
                  agents=("a1", "a2"))
    # B first appeared at message 2; the last 2 messages add nothing new
    config = DeadlockConfig(refute_streak=9, stagnation=2)
    assert DeadlockDetector(config).detect(ms).rule == RULE_STAGNATION
    assert not DeadlockDetector(DeadlockConfig(stagnation=None)).detect(ms).deadlocked


def test_invalid_config():
    with pytest.raises(ValueError):
        DeadlockConfig(refute_streak=0)
    with pytest.raises(ValueError):
        DeadlockConfig(stagnation=0)
