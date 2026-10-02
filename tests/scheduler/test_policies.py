import pytest

from ai_project.blackboard import Blackboard
from ai_project.protocol import PXPMessage, PXPTag
from ai_project.scheduler import (
    PriorityPolicy,
    RoundRobinPolicy,
    RuleBasedMockAgent,
    Scheduler,
    SchedulingContext,
    SchedulingPolicy,
    Selection,
)

AGENTS = ("analyst", "critic", "specialist")


def context(*messages, agent_ids=AGENTS):
    """SchedulingContext after publishing (agent_id, tag, prediction) messages."""
    board = Blackboard()
    board.initialize_task("Pick an option")
    for agent, tag, prediction in messages:
        board.publish_message(PXPMessage.create(agent, tag, prediction, "because"))
    return SchedulingContext(
        board.get_state(), tuple(board.get_history()), tuple(agent_ids), len(messages)
    )


@pytest.fixture
def priority():
    return PriorityPolicy(proposer="analyst", critic="critic", resolver="specialist")


class TestRoundRobin:
    def test_first_turn_goes_to_first_agent(self):
        assert RoundRobinPolicy().select(context()).agent_id == "analyst"

    def test_follows_last_speaker_and_wraps(self):
        policy = RoundRobinPolicy()
        assert policy.select(context(("analyst", PXPTag.RATIFY, "A"))).agent_id == "critic"
        assert policy.select(context(("specialist", PXPTag.RATIFY, "A"))).agent_id == "analyst"

    def test_unknown_last_speaker_restarts(self):
        assert (
            RoundRobinPolicy().select(context(("outsider", PXPTag.RATIFY, "A"))).agent_id
            == "analyst"
        )


class TestPriority:
    def test_no_proposal_selects_proposer(self, priority):
        selection = priority.select(context())
        assert (selection.agent_id, selection.rule) == ("analyst", "no_proposal")

    def test_new_proposal_selects_critic(self, priority):
        selection = priority.select(context(("analyst", PXPTag.RATIFY, "A")))
        assert (selection.agent_id, selection.rule) == ("critic", "after_new_proposal")

    def test_disagreement_selects_resolver(self, priority):
        selection = priority.select(
            context(("analyst", PXPTag.RATIFY, "A"), ("critic", PXPTag.REFUTE, "A"))
        )
        assert (selection.agent_id, selection.rule) == ("specialist", "after_disagreement")

    def test_pending_agreement_selects_first_non_supporter(self, priority):
        selection = priority.select(
            context(
                ("analyst", PXPTag.RATIFY, "A"),
                ("critic", PXPTag.REFUTE, "A"),
                ("specialist", PXPTag.REVISE, "B"),
                ("critic", PXPTag.RATIFY, "B"),
            )
        )
        assert (selection.agent_id, selection.rule) == ("analyst", "pending_agreement")

    def test_silent_agent_is_pending(self, priority):
        selection = priority.select(
            context(("analyst", PXPTag.RATIFY, "A"), ("critic", PXPTag.RATIFY, "A"))
        )
        assert (selection.agent_id, selection.rule) == ("specialist", "pending_agreement")

    def test_never_selects_last_speaker_twice(self, priority):
        # Resolver just objected; the after_disagreement rule must not pick it again
        selection = priority.select(
            context(("analyst", PXPTag.RATIFY, "A"), ("specialist", PXPTag.REFUTE, "A"))
        )
        assert selection.agent_id != "specialist"

    def test_unregistered_roles_are_skipped(self, priority):
        ctx = context(
            ("analyst", PXPTag.RATIFY, "A"),
            ("critic", PXPTag.REFUTE, "A"),
            agent_ids=("analyst", "critic"),
        )
        assert priority.select(ctx).agent_id == "analyst"

    def test_fallback_round_robin(self, priority):
        ctx = context(
            ("analyst", PXPTag.RATIFY, "A"),
            ("critic", PXPTag.RATIFY, "A"),
            ("specialist", PXPTag.RATIFY, "A"),
        )
        selection = priority.select(ctx)
        assert (selection.agent_id, selection.rule) == ("analyst", "fallback")

    def test_describe(self, priority):
        assert priority.describe() == {
            "name": "priority",
            "proposer": "analyst",
            "critic": "critic",
            "resolver": "specialist",
        }


class TestReplaceablePolicy:
    def test_custom_policy_drives_scheduler(self):
        class AlwaysCritic(SchedulingPolicy):
            name = "always_critic"

            def select(self, context):
                return Selection("critic", "fixed", "critic always speaks")

        board = Blackboard()
        board.initialize_task("Pick an option")
        agents = [
            RuleBasedMockAgent("analyst", preferred="A"),
            RuleBasedMockAgent("critic", preferred="B"),
        ]
        scheduler = Scheduler(board, agents, policy=AlwaysCritic())
        scheduler.step()
        scheduler.step()
        assert [e.agent_id for e in board.get_history()] == ["critic", "critic"]
        assert scheduler.get_trace()[0]["policy"] == "always_critic"
