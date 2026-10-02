import json

import pytest

from ai_project.blackboard import BlackboardStatus, HistoryEvent
from ai_project.deadlock import (
    RULE_REPEATED_DISAGREEMENT,
    RULE_STAGNATION,
    DeadlockConfig,
    DeadlockDetector,
    current_proposal,
    detect_deadlock,
    last_novel_proposal_index,
    latest_stances,
    objections_in_epoch,
    proposal_epoch,
)
from ai_project.scheduler.scenarios import alternating_deadlock_scenario, deadlock_scenario


def history(*events):
    """Build history from (agent_id, tag, prediction) tuples."""
    return [
        HistoryEvent(
            iteration=i,
            agent_id=agent,
            tag=tag,
            timestamp="t",
            prediction=prediction,
            explanation=f"{agent} {tag} {prediction}",
        )
        for i, (agent, tag, prediction) in enumerate(events, start=1)
    ]


NO_STAGNATION = DeadlockConfig(max_disagreement_cycles=2, max_stagnant_steps=None)


class TestStances:
    def test_no_proposal_in_empty_history(self):
        assert current_proposal([]) is None
        assert proposal_epoch([]).start_index is None

    def test_objections_do_not_change_proposal(self):
        h = history(("a", "RATIFY", "A"), ("b", "REFUTE", "A"), ("c", "REJECT", "N/A"))
        assert current_proposal(h) == "A"
        assert proposal_epoch(h).start_index == 0

    def test_revise_with_new_prediction_starts_new_epoch(self):
        h = history(("a", "RATIFY", "A"), ("b", "REFUTE", "A"), ("c", "REVISE", "B"))
        epoch = proposal_epoch(h)
        assert epoch.proposal == "B"
        assert epoch.start_index == 2
        assert objections_in_epoch(h) == []

    def test_latest_stances_keep_first_seen_order(self):
        h = history(("a", "RATIFY", "A"), ("b", "REFUTE", "A"), ("a", "RATIFY", "B"))
        stances = latest_stances(h)
        assert list(stances) == ["a", "b"]
        assert stances["a"].prediction == "B"


class TestRepeatedDisagreement:
    def test_alternating_refutations_detected(self):
        h = history(
            ("analyst", "RATIFY", "A"),
            ("critic", "REFUTE", "A"),
            ("analyst", "RATIFY", "A"),
            ("critic", "REFUTE", "A"),
        )
        report = detect_deadlock(h, NO_STAGNATION)
        assert report.deadlocked
        assert report.rule == RULE_REPEATED_DISAGREEMENT
        assert report.disagreement_cycles == 2
        assert report.contested_prediction == "A"
        assert report.objecting_agents == ("critic",)

    def test_does_not_fire_too_early(self):
        h = history(
            ("analyst", "RATIFY", "A"), ("critic", "REFUTE", "A"), ("analyst", "RATIFY", "A")
        )
        report = detect_deadlock(h, NO_STAGNATION)
        assert not report.deadlocked
        assert report.disagreement_cycles == 1

    def test_threshold_is_respected(self):
        events = []
        for _ in range(3):
            events += [("analyst", "RATIFY", "A"), ("critic", "REFUTE", "A")]
        config = DeadlockConfig(max_disagreement_cycles=3, max_stagnant_steps=None)
        assert not detect_deadlock(history(*events[:4]), config).deadlocked
        assert not detect_deadlock(history(*events[:5]), config).deadlocked
        assert detect_deadlock(history(*events), config).deadlocked

    def test_two_agents_refuting_same_proposal(self):
        h = history(
            ("analyst", "RATIFY", "A"), ("critic", "REFUTE", "A"), ("specialist", "REFUTE", "A")
        )
        report = detect_deadlock(h, NO_STAGNATION)
        assert report.deadlocked
        assert report.objecting_agents == ("critic", "specialist")

    def test_reject_counts_as_objection(self):
        h = history(
            ("analyst", "RATIFY", "A"), ("critic", "REJECT", "task"), ("specialist", "REFUTE", "A")
        )
        assert detect_deadlock(h, NO_STAGNATION).deadlocked

    def test_refuting_a_different_prediction_is_not_a_cycle(self):
        h = history(
            ("analyst", "RATIFY", "A"), ("critic", "REFUTE", "Z"), ("specialist", "REFUTE", "Z")
        )
        report = detect_deadlock(h, NO_STAGNATION)
        assert report.disagreement_cycles == 0
        assert not report.deadlocked

    def test_new_proposal_resets_cycles(self):
        h = history(
            ("analyst", "RATIFY", "A"),
            ("critic", "REFUTE", "A"),
            ("specialist", "REVISE", "B"),
            ("critic", "REFUTE", "B"),
        )
        report = detect_deadlock(h, NO_STAGNATION)
        assert report.contested_prediction == "B"
        assert report.disagreement_cycles == 1
        assert not report.deadlocked

    def test_resolved_objections_do_not_deadlock(self):
        # Both objectors later ratify A: the cycles happened but nobody still objects
        h = history(
            ("analyst", "RATIFY", "A"),
            ("critic", "REFUTE", "A"),
            ("specialist", "REFUTE", "A"),
            ("critic", "RATIFY", "A"),
            ("specialist", "RATIFY", "A"),
        )
        report = detect_deadlock(h, NO_STAGNATION)
        assert report.disagreement_cycles == 2
        assert report.objecting_agents == ()
        assert not report.deadlocked


class TestStagnation:
    def test_novel_proposal_index_ignores_revisited_predictions(self):
        h = history(("a", "RATIFY", "A"), ("b", "REVISE", "B"), ("a", "REVISE", "A"))
        assert last_novel_proposal_index(h) == 1
        assert last_novel_proposal_index([]) is None

    def test_oscillating_proposals_are_stagnation(self):
        # Every message changes the proposal, but only between A and B: no progress
        events = [("a", "REVISE", "A"), ("b", "REVISE", "B")] * 4
        config = DeadlockConfig(max_disagreement_cycles=5, max_stagnant_steps=6)
        assert not detect_deadlock(history(*events[:7]), config).deadlocked
        report = detect_deadlock(history(*events), config)
        assert report.deadlocked
        assert report.rule == RULE_STAGNATION
        assert report.stagnant_steps == 6
        assert report.dissenting_agents == ("a",)

    def test_novel_proposal_resets_stagnation(self):
        events = [("a", "REVISE", "A"), ("b", "REVISE", "B")] * 3 + [("a", "REVISE", "C")]
        config = DeadlockConfig(max_disagreement_cycles=5, max_stagnant_steps=3)
        report = detect_deadlock(history(*events), config)
        assert report.stagnant_steps == 0
        assert not report.deadlocked

    def test_fires_without_new_proposal_while_dissent_remains(self):
        # One objection only, so the cycle rule cannot fire; analyst and critic disagree on A vs B
        h = history(
            ("analyst", "RATIFY", "A"),
            ("critic", "REFUTE", "A"),
            ("analyst", "RATIFY", "A"),
            ("analyst", "RATIFY", "A"),
        )
        config = DeadlockConfig(max_disagreement_cycles=5, max_stagnant_steps=3)
        report = detect_deadlock(h, config)
        assert report.deadlocked
        assert report.rule == RULE_STAGNATION
        assert report.stagnant_steps == 3

    def test_disabled_with_none(self):
        h = history(
            ("analyst", "RATIFY", "A"),
            ("critic", "REFUTE", "A"),
            *[("analyst", "RATIFY", "A")] * 10,
        )
        config = DeadlockConfig(max_disagreement_cycles=5, max_stagnant_steps=None)
        assert not detect_deadlock(h, config).deadlocked

    def test_agreement_is_not_stagnation(self):
        h = history(*[("a", "RATIFY", "A"), ("b", "RATIFY", "A")] * 5)
        assert not detect_deadlock(h, DeadlockConfig(max_stagnant_steps=2)).deadlocked

    def test_no_proposal_ever_is_stagnation(self):
        h = history(*[("a", "REJECT", "task")] * 3)
        report = detect_deadlock(h, DeadlockConfig(max_stagnant_steps=3))
        assert report.deadlocked
        assert report.rule == RULE_STAGNATION
        assert report.contested_prediction is None


class TestConfigAndReport:
    @pytest.mark.parametrize("kwargs", [{"max_disagreement_cycles": 0}, {"max_stagnant_steps": 0}])
    def test_invalid_config_rejected(self, kwargs):
        with pytest.raises(ValueError):
            DeadlockConfig(**kwargs)

    def test_report_is_json_serializable(self):
        report = DeadlockDetector().detect(history(("a", "RATIFY", "A"), ("b", "REFUTE", "A")))
        data = json.loads(json.dumps(report.to_dict()))
        assert data["contested_prediction"] == "A"
        assert data["deadlocked"] is False

    def test_empty_history(self):
        report = detect_deadlock([])
        assert not report.deadlocked
        assert report.contested_prediction is None


class TestSchedulerDeadlock:
    def test_scheduler_status_becomes_deadlock(self):
        board, scheduler, result = deadlock_scenario().run()
        assert board.get_state().status == BlackboardStatus.DEADLOCK
        assert result.deadlocked
        assert result.stop_reason == "deadlock"
        assert result.iterations == 3
        assert scheduler.get_trace()[-1]["kind"] == "deadlock"

    def test_deadlock_is_reproducible(self):
        traces = [deadlock_scenario().run()[2].to_dict()["trace"] for _ in range(3)]
        assert traces[0] == traces[1] == traces[2]

    @pytest.mark.parametrize("cycles", [1, 2, 3, 4])
    def test_alternating_deadlock_at_threshold(self, cycles):
        _, _, result = alternating_deadlock_scenario(cycles).run()
        assert result.deadlocked
        assert result.deadlock.disagreement_cycles == cycles
        assert result.iterations == 2 * cycles
