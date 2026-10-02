import json
import os
import random
from dataclasses import asdict
from datetime import datetime
import yaml

from ai_project.ui_models import UIEvent, RunSummary, SimulationResult

def load_config(config_path="experiments/config.yaml"):
    if not os.path.exists(config_path):
        return {
            "agents": {"total": 3},
            "counterfactual_fraction": [0.0, 0.33, 0.66, 1.0],
            "trials": 20,
            "seed": 42
        }
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def run_mock_simulation(task_id: int, cf_fraction: float) -> SimulationResult:
    # Generate mock events
    original_events = [
        UIEvent(step=1, agent_id="Analyst", tag="RATIFY", prediction="Option A", explanation="Evidence A", confidence=0.82),
        UIEvent(step=2, agent_id="Critic", tag="REFUTE", prediction="Option A", explanation="Evidence conflicts", confidence=0.77),
        UIEvent(step=3, agent_id="Specialist", tag="REVISE", prediction="Option B", explanation="New evidence B", confidence=0.71),
    ]
    
    # 30% chance of deadlocking in the mock
    is_deadlocked = random.random() < 0.5
    
    if is_deadlocked:
        original_events.append(UIEvent(step=4, agent_id="Analyst", tag="REFUTE", prediction="Option B", explanation="Conflicts with A", confidence=0.6))
        orig_summary = RunSummary(status="DEADLOCK", prediction="Option A", iterations=4, deadlocked=True)
        
        # Determine if counterfactual resolves it (higher fraction = higher chance)
        if random.random() < cf_fraction:
            cf_events = original_events[:2] # Diverged at step 2
            cf_events.append(UIEvent(step=2, agent_id="Critic", tag="REVISE", prediction="Option A", explanation="Minor adjustment", confidence=0.75))
            cf_events.append(UIEvent(step=3, agent_id="Specialist", tag="RATIFY", prediction="Option A", explanation="Agreed with revised evidence", confidence=0.8))
            cf_summary = RunSummary(status="CONSENSUS", prediction="Option A", iterations=3, deadlocked=False)
            divergence_step = 2
        else:
            cf_events = list(original_events)
            cf_summary = RunSummary(status="DEADLOCK", prediction="Option A", iterations=4, deadlocked=True)
            divergence_step = None
    else:
        orig_summary = RunSummary(status="CONSENSUS", prediction="Option B", iterations=3, deadlocked=False)
        cf_events = None
        cf_summary = None
        divergence_step = None
        
    return SimulationResult(
        original_summary=orig_summary,
        original_events=original_events,
        counterfactual_summary=cf_summary,
        counterfactual_events=cf_events,
        divergence_step=divergence_step
    )

def run_experiments():
    config = load_config()
    random.seed(config.get("seed", 42))
    
    trials = config.get("trials", 20)
    fractions = config.get("counterfactual_fraction", [0.0, 0.33, 0.66, 1.0])
    
    results = []
    
    for cf_frac in fractions:
        for t in range(trials):
            res = run_mock_simulation(t, cf_frac)
            
            # Serialize for JSON
            record = {
                "cf_fraction": cf_frac,
                "trial": t,
                "original_summary": asdict(res.original_summary),
                "original_events": [asdict(e) for e in res.original_events],
                "counterfactual_summary": asdict(res.counterfactual_summary) if res.counterfactual_summary else None,
                "counterfactual_events": [asdict(e) for e in res.counterfactual_events] if res.counterfactual_events else None,
                "divergence_step": res.divergence_step
            }
            results.append(record)
            
    os.makedirs("experiments/results", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_file = f"experiments/results/results_{date_str}.json"
    
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Experiments completed. Results saved to {out_file}")
    return out_file

if __name__ == "__main__":
    run_experiments()
