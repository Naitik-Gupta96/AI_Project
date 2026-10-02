from ai_project.ui_models import UIEvent, RunSummary, SimulationResult

def test_ui_models():
    summary = RunSummary(status="CONSENSUS", prediction="Option A", iterations=3, deadlocked=False)
    event = UIEvent(step=1, agent_id="TestAgent", tag="RATIFY", prediction="Option A", explanation="Test", confidence=1.0)
    
    sim = SimulationResult(
        original_summary=summary,
        original_events=[event],
        counterfactual_summary=None,
        counterfactual_events=None,
        divergence_step=None
    )
    
    assert sim.original_summary.status == "CONSENSUS"
    assert len(sim.original_events) == 1
    assert sim.original_events[0].agent_id == "TestAgent"
