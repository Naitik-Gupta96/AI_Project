import json

import pytest

from ai_project.blackboard import Blackboard
from ai_project.protocol import PXPMessage, PXPTag
from ai_project.scheduler import ConsensusConfig, detect_consensus


def board_with(*messages):
    """Board after publishing (agent_id, tag, prediction) messages."""
    board = Blackboard()
    board.initialize_task("Pick an option")
    for agent, tag, prediction in messages:
        board.publish_message(PXPMessage.create(agent, tag, prediction, f"{agent} says {tag}"))
    return board


def check(board, **kwargs):
    return detect_consensus(board.get_state(), board.get_history(), **kwargs)


class TestConsensus:
    def test_clear_agreement(self):
        board = board_with(("a", PXPTag.RATIFY, "B"), ("b", PXPTag.RATIFY, "B"))
        result = check(board)
        assert result.reached
        assert result.prediction == "B"
        assert result.supporters == ("a", "b")
        assert result.blockers == ()

    def test_revise_counts_as_support(self):
        board = board_with(("a", PXPTag.REVISE, "B"), ("b", PXPTag.RATIFY, "B"))
        assert check(board).reached

    def test_unresolved_refute_prevents_consensus(self):
        board = board_with(
            ("a", PXPTag.RATIFY, "A"), ("b", PXPTag.RATIFY, "A"), ("c", PXPTag.REFUTE, "A")
        )
        result = check(board)
        assert not result.reached
        assert result.blockers == ("c",)

    def test_earlier_refute_resolved_by_later_ratify(self):
        board = board_with(
            ("a", PXPTag.RATIFY, "A"),
            ("b", PXPTag.REFUTE, "A"),
            ("b", PXPTag.RATIFY, "A"),
        )
        assert check(board).reached

    def test_reject_prevents_consensus(self):
        board = board_with(
            ("a", PXPTag.RATIFY, "A"), ("b", PXPTag.REJECT, "task"), ("c", PXPTag.RATIFY, "A")
        )
        result = check(board)
        assert not result.reached
        assert "b" in result.blockers

    def test_support_for_different_prediction_prevents_consensus(self):
        board = board_with(("a", PXPTag.RATIFY, "A"), ("b", PXPTag.RATIFY, "B"))
        assert not check(board).reached

    def test_single_supporter_below_minimum(self):
        board = board_with(("a", PXPTag.RATIFY, "A"))
        assert not check(board).reached
        assert check(board, config=ConsensusConfig(min_supporters=1)).reached

    def test_silent_registered_agent_blocks(self):
        board = board_with(("a", PXPTag.RATIFY, "A"), ("b", PXPTag.RATIFY, "A"))
        result = check(board, agent_ids=["a", "b", "c"])
        assert not result.reached
        assert result.blockers == ("c",)
        assert "silent" in result.reason

    def test_empty_board(self):
        board = board_with()
        result = check(board)
        assert not result.reached
        assert result.prediction is None

    def test_result_is_json_serializable(self):
        board = board_with(("a", PXPTag.RATIFY, "B"), ("b", PXPTag.RATIFY, "B"))
        assert json.loads(json.dumps(check(board).to_dict()))["reached"] is True

    def test_invalid_config(self):
        with pytest.raises(ValueError):
            ConsensusConfig(min_supporters=0)
