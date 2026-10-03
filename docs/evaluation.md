# Evaluation: End-to-End Pilot

**Mode: END-TO-END PILOT, deterministic mock agents, synthetic tasks.** Every
number below comes from running the actual system. It describes how the
implemented mechanism behaves with rule-based agents. It is not evidence about
language-model agents, real tasks or benchmarks, and it is not a validated
research finding.

## Reproduce

```bash
python experiments/run_experiment.py        # 100 tasks × 8 conditions = 800 trials, ~3 s
python experiments/analyze_results.py       # tables + experiments/results/*_summary.csv
```

Output: `experiments/results/pilot_mock_seed42_n100.json` (git-ignored; regenerate
it). With the deterministic provider, two runs are identical except for
`generated_at`, `git_commit` and the measured runtimes (tested, including
across processes with different `PYTHONHASHSEED`). The UI's Run Explorer can
re-execute any recorded trial and checks it against the record.

## Design

- **Tasks.** `generate_tasks(100, seed=42)`: 3 options each. Analyst benefit
  scores are uniform in [0.2, 0.95] and the analyst objects below 0.40; the
  critic and the specialist each object to each option with probability 0.3,
  with a reason. Agents see only their own role's evidence.
- **Trial.** One task under one condition, run by `pipeline.run_task`:
  Blackboard → analyst/critic/specialist (MockLLMProvider) → Scheduler (priority
  policy, max 12 steps) → deadlock detection (2 disagreement cycles or 6
  stagnant steps) → if deadlocked, counterfactual reflection and replay.
- **Condition = counterfactual fraction.** The share of the 3 agents that may
  revise their own past messages after a deadlock: 0, 1/3, 2/3, 1. Every subset
  of each size is run (1 + 3 + 3 + 1 = 8 conditions), so a fraction's figures
  do not depend on which agent was picked.
- **Only the condition changes.** The original run is identical across
  conditions (tested), because reflection happens only after a deadlock.
- **Recorded per trial.** trial id, seed, task id, condition, original trace and
  outcome, deadlock rule, every replayed branch (agent, branch point, revised
  message, outcome, trace), metrics, runtime, provider configuration; per file:
  parameters, git commit, Python and package version.

## Metrics

| Metric | Definition |
|---|---|
| deadlock rate | original runs in which the deadlock detector fired |
| feasible | the task has an option no role objects to (ground truth; never shown to agents) |
| recovery rate | deadlocked runs where some branch reached CONSENSUS |
| recovery rate (feasible) | the same, counting only feasible tasks. Deadlock is the correct outcome on infeasible tasks |
| best-decision rate | trials ending in CONSENSUS on the best feasible option |
| branches replayed | counterfactual branches executed per deadlocked trial |

Not measured: token cost (the mock reports none; nothing is estimated from
text length), intelligibility to humans, benchmark accuracy.

## Results (seed 42, 100 tasks)

By counterfactual fraction (pooled over agent subsets; trials share tasks, so no intervals):

| fraction | trials | deadlock rate | deadlocked | of which feasible | recovery | recovery (feasible) | final consensus | best decision |
|---|---|---|---|---|---|---|---|---|
| 0 | 100 | 0.45 | 45 | 19 | 0.00 | 0.00 | 0.55 | 0.55 |
| 1/3 | 300 | 0.45 | 135 | 57 | 0.24 | 0.58 | 0.66 | 0.66 |
| 2/3 | 300 | 0.45 | 135 | 57 | 0.36 | 0.86 | 0.71 | 0.71 |
| 1 | 100 | 0.45 | 45 | 19 | 0.42 | 1.00 | 0.74 | 0.73 |

By condition (one trial per task, so a 95% Wilson interval over the task generator is shown):

| counterfactual-capable | feasible deadlocks | recovered | rate | 95% CI | branches replayed (mean) |
|---|---|---|---|---|---|
| none | 19 | 0 | 0.00 | [0.00, 0.17] | 0.00 |
| analyst | 19 | 11 | 0.58 | [0.36, 0.77] | 0.84 |
| critic | 19 | 5 | 0.26 | [0.12, 0.49] | 1.07 |
| specialist | 19 | 17 | 0.89 | [0.69, 0.97] | 0.96 |
| analyst + critic | 19 | 13 | 0.68 | [0.46, 0.85] | 1.80 |
| analyst + specialist | 19 | 18 | 0.95 | [0.75, 0.99] | 1.31 |
| critic + specialist | 19 | 18 | 0.95 | [0.75, 0.99] | 1.87 |
| all three | 19 | 19 | 1.00 | [0.83, 1.00] | 2.20 |

## Reading these results

- 26 of the 45 deadlocks are on infeasible tasks (no option acceptable to all
  roles). No branch can recover them, and none did.
- Recovery grows with the number of capable agents and never decreases when an
  agent is added (a property test checks this per task). This follows from the
  resolver trying every capable agent's revision, so it is a property of the
  mechanism, not an empirical discovery.
- Which single agent helps most (specialist > analyst > critic) is a
  consequence of the role rules: only the specialist adopts alternatives, so a
  critic revision helps only when the specialist accepts the named option.
- One recovered consensus was on a feasible option that was not the best one,
  so final consensus (0.74) and best decision (0.73) differ by one trial.
- 19 feasible deadlocks is a small sample, and the task generator's parameters
  (objection rate, number of options) drive all of these rates. Treat them as a
  description of this configuration only.

## Running with a local model

`python experiments/run_experiment.py --provider ollama --model qwen3:4b --tasks 5`
runs the same pipeline with a model; results are labelled non-deterministic and
record token counts reported by Ollama. One Flash Talk run with `qwen3:4b` made
about 15 model calls in 3 minutes on the development laptop (roughly 13 s per
call), so the full 800-trial design is impractical on that setup; no model
results exist yet.
