import pytest

from ai_project.scheduler import ConsensusConfig, anchor_of, evaluate_consensus
from tests.helpers import msg

AGENTS = ["a1", "a2", "a3"]
EQUAL = dict.fromkeys(AGENTS, 1.0)


def flash(options_board):
    """INIT A, REFUTE B, RATIFY B: the analyst's A is opposed, two agents back B."""
    board = options_board()
    board.commit(msg("a1", "INIT", "A"))
    board.commit(msg("a2", "REFUTE", "B", judgment=(False, False, False)))
    board.commit(msg("a3", "RATIFY", "B", judgment=(True, True, False)))
    return board


def test_ratify_chain_leads_to_its_anchor(options_board):
    board = flash(options_board)
    board.revise_context("a1", "B", "fine")
    board.commit(msg("a1", "RATIFY", "B", judgment=(True, True, False)))
    messages = board.get_messages()
    by_id = {m.message_id: m for m in messages}
    assert anchor_of(messages[3], by_id).iteration == 2  # a1 -> a3 -> a2's REFUTE B
    assert anchor_of(messages[1], by_id).iteration == 2  # a non-RATIFY is its own anchor


def test_needs_every_agent_with_equal_weights(options_board):
    board = flash(options_board)
    result = evaluate_consensus(board.get_messages(), AGENTS, EQUAL)
    assert not result.reached
    assert result.supporters == ("a3",)
    assert result.share == pytest.approx(1 / 3)
    assert result.proximity == pytest.approx(1 / 3)


def test_full_agreement(options_board):
    board = flash(options_board)
    board.revise_context("a1", "B", "fine")
    board.commit(msg("a1", "RATIFY", "B", judgment=(True, True, False)))
    board.commit(msg("a2", "RATIFY", "B", judgment=(True, True, False)))
    result = evaluate_consensus(board.get_messages(), AGENTS, EQUAL)
    assert result.reached
    assert result.prediction == "B"
    assert set(result.supporters) == set(AGENTS)
    assert result.proximity == 1.0


def test_lowered_weight_lets_the_majority_decide(options_board):
    board = flash(options_board)
    board.revise_context("a1", "B", "fine")
    board.commit(msg("a1", "RATIFY", "B", judgment=(True, True, False)))
    weights = {"a1": 1.0, "a2": 0.5, "a3": 1.0}  # a2 still REFUTEs, but its weight is lowered
    result = evaluate_consensus(board.get_messages(), AGENTS, weights)
    assert result.share == pytest.approx(2 / 2.5)
    assert result.reached
    assert not evaluate_consensus(board.get_messages(), AGENTS, EQUAL).reached


def test_min_supporters(options_board):
    board = options_board(agents=["a1", "a2"])
    board.commit(msg("a1", "INIT", "A"))
    board.commit(msg("a2", "RATIFY", "A", judgment=(True, True, False)))
    weights = {"a1": 0.1, "a2": 1.0}
    assert not evaluate_consensus(board.get_messages(), ["a1", "a2"], weights,
                                  ConsensusConfig(tau=0.75, min_supporters=2)).reached
    assert evaluate_consensus(board.get_messages(), ["a1", "a2"], weights,
                              ConsensusConfig(tau=0.75, min_supporters=1)).reached


def test_no_messages():
    assert not evaluate_consensus([], AGENTS, EQUAL).reached


def test_invalid_config():
    with pytest.raises(ValueError):
        ConsensusConfig(tau=0)
