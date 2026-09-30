# Experiments Directory

This directory contains experiment scripts, outputs, and results.

## Structure
```
experiments/
├── README.md          # This file
├── scripts/           # Experiment runner scripts
├── output/            # Generated experiment outputs (gitignored)
├── results/           # Parsed results (gitignored)
└── logs/              # Experiment logs (gitignored)
```

## Running Experiments

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run benchmark (when implemented)
python experiments/scripts/run_benchmark.py --config config.yaml
```

## Output Format

Experiments should output:
- `experiments/output/<experiment_name>/state.json` - Final Blackboard state
- `experiments/output/<experiment_name>/history.json` - Full interaction history
- `experiments/output/<experiment_name>/snapshot.json` - Snapshot for replay
- `experiments/results/<experiment_name>.json` - Aggregated metrics

## Integration with Blackboard

```python
from ai_project.blackboard import Blackboard
from experiments.exporter import export_experiment

board = Blackboard()
# ... run experiment ...
export_experiment(board, "experiments/output/my_experiment")
```