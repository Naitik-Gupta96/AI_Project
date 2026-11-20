import pytest

from ai_project.agents import build_team
from ai_project.benchmarks import SyntheticBenchmark
from ai_project.blackboard import Blackboard, JsonStore
from ai_project.counterfactual import CounterfactualConfig
from ai_project.llm.providers.mock import MockLLMProvider
from ai_project.session import Session, SessionConfig, run_session


def test_without_counterfactual_agents_the_demo_deadlocks(demo_task, mock_team, synthetic):
    result = run_session(demo_task, mock_team(demo_task), benchmark=synthetic)
    assert result.status == "DEADLOCK"
    assert result.final_prediction is None
    assert not result.score.correct
    assert result.interventions == []
    assert result.intelligibility["session"] == "None"


def test_counterfactual_analyst_recovers_the_demo(demo_task, mock_team, synthetic):
    result = run_session(demo_task, mock_team(demo_task), ["analyst"], benchmark=synthetic)
    assert result.status == "CONSENSUS"
    assert result.final_prediction == "Option B" == demo_task.reference
    assert result.recovered and result.convergence_success
    assert len(result.interventions) == 1
    assert result.intelligibility_after_intervention["session"] == "Strong"
    assert result.usage["live"]["calls"] > 0 and result.usage["sandbox"]["calls"] > 0


def test_max_interventions_zero_disables_recovery(demo_task, mock_team):
    config = SessionConfig(counterfactual=CounterfactualConfig(max_interventions=0))
    result = run_session(demo_task, mock_team(demo_task), ["analyst"], config)
    assert result.status == "DEADLOCK" and result.interventions == []


def test_sessions_are_deterministic(mock_team):
    tasks = SyntheticBenchmark().load(15, seed=3)

    def outcomes():
        out = []
        for task in tasks:
            r = run_session(task, mock_team(task), ["analyst", "specialist"])
            out.append((r.status, r.final_prediction, r.messages,
                        [i.to_dict()["credit"] for i in r.interventions]))
        return out

    assert outcomes() == outcomes()


def test_counterfactual_agents_do_not_change_the_run_before_the_first_deadlock(mock_team):
    for task in SyntheticBenchmark().load(20, seed=5):
        plain = Session(task, mock_team(task))
        plain.run()
        cf = Session(task, mock_team(task), ["analyst", "critic", "specialist"])
        cf.run()
        n = len(plain.board.get_messages())
        prefix = [(m.agent_id, m.tag, m.prediction) for m in cf.board.get_messages()[:n]]
        assert prefix == [(m.agent_id, m.tag, m.prediction) for m in plain.board.get_messages()]


def test_session_is_persisted_and_reloadable(tmp_path, demo_task, mock_team):
    store = JsonStore(tmp_path)
    session = Session(demo_task, mock_team(demo_task), ["analyst"], store=store, session_id="demo")
    result = session.run()
    reloaded = Blackboard.load(JsonStore(tmp_path), "demo")
    assert reloaded.get_state().to_dict() == session.board.get_state().to_dict()
    meta = store.read_meta("demo")
    assert meta["status"] == result.status and meta["cf_agents"] == ["analyst"]


def test_unknown_cf_agent(demo_task, mock_team):
    with pytest.raises(ValueError):
        Session(demo_task, mock_team(demo_task), ["ghost"])


def test_result_serializes(demo_task):
    import json
    team = build_team(demo_task, MockLLMProvider())
    data = run_session(demo_task, team, ["analyst"]).to_dict()
    json.dumps(data)
    assert data["interventions"][0]["branches"]
