# Evaluation & Metrics

## Running Experiments

To run a batch of mock trials across different counterfactual configurations:
```bash
python experiments/run_experiment.py
```
By default, this runs 20 trials for each configuration (0%, 33%, 66%, 100% counterfactual capability) and saves a detailed JSON array in `experiments/results/`.

## Result File Format (JSON)
Each trial record contains:
- `cf_fraction`: Configuration percentage.
- `trial`: Index of the trial.
- `original_summary`: `RunSummary` object of the first pass.
- `original_events`: Trace of `UIEvent` objects.
- `counterfactual_summary`: (Optional) `RunSummary` of the alternative timeline.
- `counterfactual_events`: (Optional) Trace of the new timeline.
- `divergence_step`: (Optional) Step where the counterfactual rollback occurred.

## Analyzing Results

To generate metrics from a result file:
```bash
python experiments/analyze_results.py [path_to_json]
```
If no path is provided, it analyzes the most recent JSON file in `experiments/results/`.
It generates a summary CSV tracking:
- `total_trials`
- `deadlock_rate`: Percentage of original runs hitting impasse.
- `consensus_rate`: Overall percentage of tasks resulting in consensus (including recovered).
- `mean_iterations`: Average steps before termination.
- `cf_recovery_rate`: Percentage of deadlocks successfully recovered by counterfactual branching.
