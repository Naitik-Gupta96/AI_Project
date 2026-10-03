# Experiments

```bash
python experiments/run_experiment.py          # end-to-end pilot: 100 tasks x 8 conditions, seed 42
python experiments/analyze_results.py         # descriptive tables + *_summary.csv
python experiments/run_experiment.py --help   # --tasks, --seed, --options, --objection-rate, --provider
```

Every trial runs the real system through `ai_project.pipeline.run_task`. Results
are written to `results/pilot_<provider>_seed<seed>_n<tasks>.json` (git-ignored,
regenerated in seconds) with the seed, parameters, git commit and provider
configuration. The logic lives in `src/ai_project/experiment.py`; these scripts
are command-line wrappers.

Methodology, definitions, current numbers and their limits:
[docs/evaluation.md](../docs/evaluation.md).
