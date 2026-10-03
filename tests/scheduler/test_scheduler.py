import json
from pathlib import Path

import pytest

from ai_project.blackboard import Blackboard, BlackboardNotInitializedError, BlackboardStatus
from ai_project.deadlock import DeadlockConfig
from ai_project.protocol import PXPMessage, PXPTag
from ai_project.scheduler import (
    AgentRegistry,
    RoundRobinPolicy,
    RuleBasedMockAgent,
    Scheduler,
    SchedulerConfig,
    SchedulerError,
    SchedulingPolicy,
    Selection,
)
from ai_project.scheduler.scenarios import consensus_scenario

SRC = Path(__file__).resolve().parents[2] / "src" / "ai_project"


def new_board():
    board = Blackboard()
    board.initialize_task("Pick an option")
    return board


class RecordingAgent:
    """Always ratifies a fixed prediction and records its invocations."""

    def __init__(self, agent_id, prediction="A"):
        self.agent_id = agent_id
        self.prediction = prediction
        self.calls = 0

    def act(self, board):
        self.calls += 1
        return PXPMessage.create(
            self.agent_id, PXPTag.RATIFY, self.prediction, "fine", 0.9, board.get_iteration() + 1
        )


class FailingAgent:
    agent_id = "broken"

    def act(self, board):
        raise RuntimeError("model unavailable")


class ImpostorAgent:
    agent_id = "impostor"

    def act(self, board):
        return PXPMessage.create("someone_else", PXPTag.RATIFY, "A", "fine")


class TestConstruction:
    def test_requires_initialized_board(self):
        with pytest.raises(BlackboardNotInitializedError):
            Scheduler(Blackboard(), [RecordingAgent("a")])

    def test_requires_agents(self):
        with pytest.raises(SchedulerError):
            Scheduler(new_board(), [])

    def test_accepts_mapping_list_and_registry(self):
        a, b = RecordingAgent("a"), RecordingAgent("b")
        for agents in ({"a": a, "b": b}, [a, b], AgentRegistry([a, b])):
            assert Scheduler(new_board(), agents).registry.agent_ids == ("a", "b")

    def test_registry_key_must_match_agent_id(self):
        with pytest.raises(ValueError):
            AgentRegistry({"analyst": RecordingAgent("critic")})

    def test_registry_rejects_duplicates_and_non_agents(self):
        with pytest.raises(ValueError):
            AgentRegistry([RecordingAgent("a"), RecordingAgent("a")])
        with pytest.raises(TypeError):
            AgentRegistry([object()])

    def test_default_policy_is_round_robin(self):
        assert isinstance(Scheduler(new_board(), [RecordingAgent("a")]).policy, RoundRobinPolicy)


class TestStep:
    def test_step_invokes_selected_agent_and_publishes(self):
        a, b = RecordingAgent("a"), RecordingAgent("b")
        board = new_board()
        scheduler = Scheduler(board, [a, b])

        entry = scheduler.step()

        assert a.calls == 1 and b.calls == 0
        assert board.get_iteration() == 1
        assert board.get_history()[0].agent_id == "a"
        assert entry.kind == "agent_action"
        assert entry.agent == "a"
        assert entry.event == "RATIFY"
        assert entry.step == 1
        assert entry.reason

    def test_step_moves_board_to_running(self):
        board = new_board()
        Scheduler(board, [RecordingAgent("a"), RecordingAgent("b")]).step()
        assert board.get_state().status == BlackboardStatus.RUNNING

    def test_execution_advances_through_agents(self):
        agents = [RecordingAgent(x, prediction=x) for x in ("a", "b", "c")]
        scheduler = Scheduler(new_board(), agents)
        for _ in range(3):
            scheduler.step()
        assert [e.agent_id for e in scheduler.board.get_history()] == ["a", "b", "c"]
        assert scheduler.steps == 3

    def test_trace_records_state_changes(self):
        scheduler = Scheduler(new_board(), [RecordingAgent("a"), RecordingAgent("b")])
        entry = scheduler.step()
        assert entry.changes["iteration"] == {"before": 0, "after": 1}
        assert entry.changes["current_prediction"] == {"before": "", "after": "A"}
        assert entry.changes["status"] == {"before": "INITIALIZED", "after": "RUNNING"}

    def test_step_after_finish_returns_none(self):
        scheduler = Scheduler(new_board(), [RecordingAgent("a"), RecordingAgent("b")])
        scheduler.run()
        assert scheduler.finished
        assert scheduler.step() is None


class TestRun:
    def test_stops_on_consensus(self):
        a, b = RecordingAgent("a"), RecordingAgent("b")
        scheduler = Scheduler(new_board(), [a, b], config=SchedulerConfig(max_steps=10))
        result = scheduler.run()
        assert result.status == "CONSENSUS"
        assert result.stop_reason == "consensus"
        assert result.final_prediction == "A"
        assert result.steps == 2
        assert a.calls == 1 and b.calls == 1
        assert scheduler.get_trace()[-1]["kind"] == "consensus"

    def test_stops_on_max_steps(self):
        agents = [RecordingAgent("a", "A"), RecordingAgent("b", "B")]  # never agree
        config = SchedulerConfig(max_steps=4, deadlock=DeadlockConfig(max_stagnant_steps=None))
        scheduler = Scheduler(new_board(), agents, config=config)
        result = scheduler.run()
        assert result.steps == 4
        assert result.stop_reason == "max_steps"
        assert result.status == "RUNNING"
        assert not scheduler.finished
        assert scheduler.get_trace()[-1]["kind"] == "max_steps"

    def test_run_can_continue_after_budget(self):
        agents = [RecordingAgent("a", "A"), RecordingAgent("b", "B")]
        scheduler = Scheduler(new_board(), agents)
        scheduler.run(max_steps=2)
        scheduler.run(max_steps=3)
        assert scheduler.steps == 5
        assert scheduler.board.get_iteration() == 5

    def test_scenario_a_reaches_consensus(self):
        board, scheduler, result = consensus_scenario().run()
        assert result.consensus_reached
        assert result.final_prediction == "Option B"
        assert board.get_state().status == BlackboardStatus.CONSENSUS


class TestErrors:
    def test_agent_error_sets_failed(self):
        board = new_board()
        scheduler = Scheduler(board, [FailingAgent()])
        result = scheduler.run()
        assert result.status == "FAILED"
        assert result.stop_reason == "error"
        assert "model unavailable" in result.error
        assert scheduler.get_trace()[-1]["kind"] == "error"
        assert board.get_iteration() == 0

    def test_agent_error_can_propagate(self):
        scheduler = Scheduler(
            new_board(), [FailingAgent()], config=SchedulerConfig(raise_on_agent_error=True)
        )
        with pytest.raises(RuntimeError):
            scheduler.step()

    def test_message_signed_by_other_agent_is_refused(self):
        board = new_board()
        result = Scheduler(board, [ImpostorAgent()]).run()
        assert result.status == "FAILED"
        assert "someone_else" in result.error
        assert board.get_history() == []

    def test_policy_selecting_unknown_agent(self):
        class BadPolicy(SchedulingPolicy):
            name = "bad"

            def select(self, context):
                return Selection("ghost", "bad", "no such agent")

        with pytest.raises(SchedulerError):
            Scheduler(new_board(), [RecordingAgent("a")], policy=BadPolicy()).step()


class TestReporting:
    def test_status_trace_and_result_are_json_serializable(self):
        _, scheduler, result = consensus_scenario().run()
        json.dumps(scheduler.get_status())
        json.dumps(scheduler.get_trace())
        data = json.loads(json.dumps(result.to_dict()))
        assert data["status"] == "CONSENSUS"
        assert data["config"]["max_steps"] == 10
        assert data["policy"]["name"] == "priority"
        assert len(data["history"]) == data["iterations"]

    def test_get_status_fields(self):
        _, scheduler, _ = consensus_scenario().run()
        status = scheduler.get_status()
        assert status["finished"] is True
        assert status["current_proposal"] == "Option B"
        assert status["agents"] == ["analyst", "critic", "specialist"]
        assert status["consensus"]["reached"] is True

    def test_mock_agent_is_deterministic(self):
        board = new_board()
        agent = RuleBasedMockAgent("analyst", preferred="Option A")
        first, second = agent.act(board), agent.act(board)
        assert first.to_dict() | {"timestamp": None} == second.to_dict() | {"timestamp": None}


@pytest.mark.parametrize(
    "package", ["scheduler", "deadlock", "counterfactual", "agents", "llm", "ui", "."]
)
def test_only_public_blackboard_api_is_used(package):
    for path in (SRC / package).glob("*.py"):
        source = path.read_text()
        for private in ("._state", "._history", "._lock", "._initialized"):
            assert private not in source.replace("self._", "self-"), f"{path.name} uses {private}"
