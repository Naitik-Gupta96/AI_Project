import json

import pytest

from ai_project.blackboard import BlackboardStatus
from ai_project.counterfactual import CounterfactualEngine, CounterfactualError, Intervention
from ai_project.counterfactual.scenarios import demo_intervention
from ai_project.protocol import PXPTag
from ai_project.scheduler.scenarios import OPTION_A, OPTION_B, deadlock_scenario


def board_fingerprint(board):
    """Everything observable about a board through its public API."""
    return {
        "state": board.get_state().to_dict(),
        "history": [e.to_dict() for e in board.get_history()],
    }


@pytest.fixture
def original():
    scenario = deadlock_scenario()
    board, _, result = scenario.run()
    return scenario, board, result


def replay(engine, branch, scenario):
    return engine.replay(branch, scenario.agents, scenario.policy, scenario.config)


class TestBranchCreation:
    def test_branch_has_its_own_board(self, original):
        _, board, _ = original
        branch = CounterfactualEngine().create_branch(board, demo_intervention())
        assert branch.board is not board

    def test_prefix_inherited_and_event_replaced(self, original):
        _, board, _ = original
        branch = CounterfactualEngine().create_branch(board, demo_intervention())
        history = branch.board.get_history()
        assert len(history) == 2
        assert history[0].to_dict() == board.get_history()[0].to_dict()
        assert history[1].agent_id == "critic"  # defaults to the replaced event's author
        assert history[1].explanation == demo_intervention().explanation
        assert branch.replaced_event.to_dict() == board.get_history()[1].to_dict()
        assert [e["kind"] for e in branch.get_trace()] == ["inherited", "intervention"]

    def test_intervention_metadata_reaches_branch_board(self, original):
        _, board, _ = original
        branch = CounterfactualEngine().create_branch(board, demo_intervention())
        latest = branch.board.get_latest_message()
        assert latest["metadata"]["alternative"] == OPTION_B
        assert latest["metadata"]["counterfactual"] is True

    def test_branch_records_provenance(self, original):
        _, board, _ = original
        branch = CounterfactualEngine().create_branch(board, demo_intervention())
        info = branch.board.get_state().metadata["counterfactual"]
        assert info["branch_point"] == 2
        assert info["source_status"] == "DEADLOCK"
        assert info["source_iteration"] == 3

    def test_intervention_can_change_author(self, original):
        _, board, _ = original
        intervention = Intervention(2, PXPTag.RATIFY, OPTION_A, "fine by me", agent_id="specialist")
        branch = CounterfactualEngine().create_branch(board, intervention)
        assert branch.board.get_history()[-1].agent_id == "specialist"

    def test_branch_from_snapshot(self, original):
        _, board, _ = original
        branch = CounterfactualEngine().create_branch(board.snapshot(), demo_intervention())
        assert len(branch.board.get_history()) == 2

    def test_string_tag_accepted(self):
        assert Intervention(1, "refute", "A", "no").tag == PXPTag.REFUTE

    @pytest.mark.parametrize("iteration", [0, -1])
    def test_invalid_intervention_iteration(self, iteration):
        with pytest.raises(CounterfactualError):
            Intervention(iteration, PXPTag.RATIFY, "A", "x")

    def test_intervention_beyond_history(self, original):
        _, board, _ = original
        with pytest.raises(CounterfactualError):
            CounterfactualEngine().create_branch(board, Intervention(9, PXPTag.RATIFY, "A", "x"))

    def test_pure_replay_branch_point_bounds(self, original):
        _, board, _ = original
        engine = CounterfactualEngine()
        with pytest.raises(CounterfactualError):
            engine.create_branch(board, branch_point=5)
        with pytest.raises(CounterfactualError):
            engine.create_branch(board)

    def test_conflicting_branch_point(self, original):
        _, board, _ = original
        with pytest.raises(CounterfactualError):
            CounterfactualEngine().create_branch(board, demo_intervention(), branch_point=1)

    def test_branch_ids(self, original):
        _, board, _ = original
        engine = CounterfactualEngine()
        first = engine.create_branch(board, demo_intervention())
        second = engine.create_branch(board, demo_intervention())
        assert (first.branch_id, second.branch_id) == ("cf-1", "cf-2")
        assert engine.get_branch("cf-2") is second
        with pytest.raises(CounterfactualError):
            engine.create_branch(board, demo_intervention(), branch_id="cf-1")


class TestIsolation:
    def test_original_unaffected_by_branch_and_replay(self, original):
        scenario, board, _ = original
        before = board_fingerprint(board)
        engine = CounterfactualEngine()
        branch = engine.create_branch(board, demo_intervention())
        replay(engine, branch, scenario)
        assert board_fingerprint(board) == before
        assert board.get_state().status == BlackboardStatus.DEADLOCK

    def test_branches_are_isolated_from_each_other(self, original):
        scenario, board, _ = original
        engine = CounterfactualEngine()
        first = engine.create_branch(board, demo_intervention())
        second = engine.create_branch(board, demo_intervention())
        untouched = board_fingerprint(second.board)
        replay(engine, first, scenario)
        assert board_fingerprint(second.board) == untouched

    def test_source_snapshot_is_isolated(self, original):
        _, board, _ = original
        branch = CounterfactualEngine().create_branch(board, demo_intervention())
        branch.source_snapshot.history[0].agent_id = "MUTATED"
        branch.source_snapshot.state.current_prediction = "MUTATED"
        assert board.get_history()[0].agent_id == "analyst"
        assert board.get_state().current_prediction == OPTION_A


class TestReplay:
    def test_replay_reaches_consensus(self, original):
        scenario, board, _ = original
        engine = CounterfactualEngine()
        branch = engine.create_branch(board, demo_intervention())
        result = replay(engine, branch, scenario)
        assert result.status == "CONSENSUS"
        assert result.final_prediction == OPTION_B
        assert [e["agent_id"] for e in result.history] == [
            "analyst",
            "critic",
            "specialist",
            "critic",
            "analyst",
        ]
        assert result.history[2]["tag"] == "REVISE"

    def test_branch_can_only_be_replayed_once(self, original):
        scenario, board, _ = original
        engine = CounterfactualEngine()
        branch = engine.create_branch(board, demo_intervention())
        replay(engine, branch, scenario)
        with pytest.raises(CounterfactualError):
            replay(engine, branch, scenario)

    def test_pure_replay_reproduces_original(self, original):
        scenario, board, result = original
        engine = CounterfactualEngine()
        branch = engine.create_branch(board, branch_point=2)
        replay(engine, branch, scenario)
        comparison = engine.compare(result, branch)
        assert comparison.counterfactual_status == "DEADLOCK"
        assert not comparison.status_changed
        assert not comparison.prediction_changed
        assert comparison.divergence_iteration is None
        assert comparison.shared_prefix == 3

    def test_replay_is_deterministic(self):
        def run_once():
            scenario = deadlock_scenario()
            board, _, original_result = scenario.run()
            engine = CounterfactualEngine()
            outcome = engine.run_counterfactual(
                board,
                original_result,
                scenario.agents,
                demo_intervention(),
                policy=scenario.policy,
                config=scenario.config,
            )
            return outcome.branch.get_trace(), outcome.comparison.to_dict()

        first, second = run_once(), run_once()
        assert first == second

    def test_replay_record_is_json_serializable(self, original):
        scenario, board, result = original
        outcome = CounterfactualEngine().run_counterfactual(
            board,
            result,
            scenario.agents,
            demo_intervention(),
            policy=scenario.policy,
            config=scenario.config,
        )
        record = json.loads(json.dumps(outcome.to_dict()))
        branch = record["branch"]
        assert branch["config"]["deadlock"]["max_disagreement_cycles"] == 2
        assert branch["initial_state"]["iteration"] == 2
        assert branch["result"]["status"] == "CONSENSUS"
        assert [t["kind"] for t in branch["trace"]][:2] == ["inherited", "intervention"]
        assert branch["trace"][-1]["kind"] == "consensus"


class TestComparison:
    def test_compare_fields(self, original):
        scenario, board, result = original
        engine = CounterfactualEngine()
        branch = engine.create_branch(board, demo_intervention())
        replay(engine, branch, scenario)
        c = engine.compare(result, branch)
        assert (c.original_status, c.counterfactual_status) == ("DEADLOCK", "CONSENSUS")
        assert (c.original_prediction, c.counterfactual_prediction) == (OPTION_A, OPTION_B)
        assert (c.original_iterations, c.counterfactual_iterations) == (3, 5)
        assert (c.original_deadlocked, c.counterfactual_deadlocked) == (True, False)
        assert (c.original_consensus, c.counterfactual_consensus) == (False, True)
        assert c.status_changed and c.prediction_changed
        assert c.shared_prefix == 1
        assert c.divergence_iteration == 2
        assert "DEADLOCK" in c.summary and "CONSENSUS" in c.summary

    def test_compare_requires_replay(self, original):
        _, board, result = original
        engine = CounterfactualEngine()
        branch = engine.create_branch(board, demo_intervention())
        with pytest.raises(CounterfactualError):
            engine.compare(result, branch)
