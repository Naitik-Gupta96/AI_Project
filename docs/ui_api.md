# UI API

```bash
pip install -e ".[ui]"
python -m streamlit run frontend/app.py
```

`frontend/app.py` only renders. Every value it shows comes from
`ai_project.ui`, which builds typed views from real executions
(`pipeline.run_task`) or from pilot results files. The frontend makes no
scheduling, deadlock or counterfactual decisions.

## Tabs

| Tab | Purpose | Data source |
|---|---|---|
| Flash Talk | task → interaction → deadlock → reflection → intervention → replay → outcome | `flash_talk_demo(cf_agents)` (live run) |
| Run Explorer | metadata, selectable timeline, per-event details, raw data | live Flash Talk run, or a recorded pilot trial re-executed live and checked against its record |
| Evaluation | methodology, results by fraction and condition, what is not measured | `experiments/results/pilot_*.json` |

Set `AI_PROJECT_RESULTS_DIR` to read results from another directory (the tests do).

## Data contract (`ai_project.ui.models`)

| Type | Fields |
|---|---|
| `RunEvent` | `kind` (message / inherited / intervention / status), `step`, `tag`, `agent_id`, `role`, `prediction`, `explanation`, `confidence`, `alternative`, `rule`, `reason` (why the scheduler chose the agent, or why the status was set), `status_after`, `timestamp`, `message_id` |
| `Outcome` | `status`, `prediction`, `iterations`, `reason` |
| `RunView` | `title`, `task`, `options`, `mode`, `provider`, `policy`, `config`, `events`, `outcome` |
| `AgentView` | `agent_id`, `role`, `description`, `evidence`, `counterfactual_capable` |
| `ReflectionView` | `agent_id`, `step`, `original`, `revised` (None = no change), `replayed`, `outcome` |
| `CounterfactualView` | `agent_id`, `branch_point`, `original_event`, `revised_event`, `branch: RunView`, `divergence_step`, `shared_prefix`, `recovered`, `summary` |
| `DemoView` | `original`, `agents`, `cf_agents`, `reflections`, `branches`, `final`, `original_preserved`, `runtime_ms`; `shown_branch` = the recovering branch, else the last one tried |
| `ExperimentView` | `path`, `mode`, `provider`, `generated_at`, `git_commit`, `parameters`, `definitions`, `by_fraction`, `by_condition`, `n_trials` |

All types serialize with `.to_dict()`.

Mode labels: `MODE_MOCK = "DETERMINISTIC MOCK"`, `MODE_LOCAL_MODEL = "LIVE / LOCAL MODEL"`,
`MODE_PILOT = "END-TO-END PILOT"`.

## Adapter (`ai_project.ui.adapter`)

| Function | Returns |
|---|---|
| `flash_talk_demo(cf_agents=("critic",), provider=None)` | `DemoView` of the Flash Talk task |
| `demo_view(pipeline_run)` | `DemoView` of any `PipelineRun` |
| `run_view(result, task, provider, title, trace=None)` | `RunView` of a `SchedulerResult` (pass a branch's full trace for branches) |
| `find_results(dir)` / `experiment_view(path)` | pilot results files / their `ExperimentView` |
| `trial_demo_view(doc, trial)` | `(DemoView, reproduced)` for a recorded trial |

`original_preserved` is computed by comparing the original board's history and
status after branching with the original result, not assumed.
