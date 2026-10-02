import os
import json
from experiments.run_experiment import run_mock_simulation
from experiments.analyze_results import analyze

def test_mock_simulation():
    res = run_mock_simulation(task_id=0, cf_fraction=1.0)
    assert res.original_summary is not None
    assert len(res.original_events) > 0

def test_analysis_pipeline(tmp_path):
    # Create dummy results
    dummy_results = [
        {
            "cf_fraction": 0.5,
            "trial": 0,
            "original_summary": {"status": "DEADLOCK", "prediction": "A", "iterations": 4, "deadlocked": True},
            "original_events": [],
            "counterfactual_summary": {"status": "CONSENSUS", "prediction": "B", "iterations": 3, "deadlocked": False},
            "counterfactual_events": [],
            "divergence_step": 2
        },
        {
            "cf_fraction": 0.5,
            "trial": 1,
            "original_summary": {"status": "CONSENSUS", "prediction": "A", "iterations": 3, "deadlocked": False},
            "original_events": [],
            "counterfactual_summary": None,
            "counterfactual_events": None,
            "divergence_step": None
        }
    ]
    
    file_path = tmp_path / "dummy_results.json"
    with open(file_path, "w") as f:
        json.dump(dummy_results, f)
        
    analyze(str(file_path))
    
    csv_path = str(file_path).replace(".json", "_summary.csv")
    assert os.path.exists(csv_path)
    
    with open(csv_path, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2 # header + 1 fraction row
        
        cols = lines[1].strip().split(",")
        # frac=0.5, trials=2, deadlock_rate=0.5, consensus_rate=1.0, mean_iter=3.5, cf_rec_rate=1.0
        assert float(cols[0]) == 0.5
        assert int(cols[1]) == 2
        assert float(cols[2]) == 0.5
        assert float(cols[3]) == 1.0
        assert float(cols[4]) == 3.5
        assert float(cols[5]) == 1.0
