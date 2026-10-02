# UI API Documentation

## Running the UI

Install the UI dependencies once:
```bash
pip install -e ".[ui]"
```

To run the full multi-tab interface:
```bash
streamlit run frontend/app.py
```

## Running the Presentation Demo

To launch directly into the flash talk mode:
```bash
python examples/run_demo.py
```

## UI Models

The frontend depends on standard data contracts to stay decoupled from the backend implementation.

### `UIEvent`
Represents a single agent action on the Blackboard.
- `step`: Execution sequence step.
- `agent_id`: Analyst, Critic, etc.
- `tag`: PXP Message Tag (RATIFY, REFUTE, REVISE, REJECT).
- `prediction`: The hypothesis supported.
- `explanation`: The reasoning.
- `confidence`: Agent confidence score (`None` if the agent gave none).

### `RunSummary`
Summarizes an execution trace.
- `status`: CONSENSUS or DEADLOCK.
- `prediction`: Final agreed prediction, if any.
- `iterations`: Number of steps executed.
- `deadlocked`: Boolean indicating if impasse was reached.

### `SimulationResult`
Pairs the original execution trace with the counterfactual alternative branch.
- `divergence_step`: First step where the two traces differ (`None` without a counterfactual).
- `summary`: One-sentence comparison of the two runs (`None` without a counterfactual).

The models live in `ai_project.ui.models` and are re-exported from `ai_project.ui`.

## Backend Adapter (`ai_project.ui`)

The frontend never calls the Scheduler or counterfactual engine directly. The
adapter converts their results into the UI models above:

| Function | Returns |
|---|---|
| `event_to_ui(event)` | `UIEvent` from a serialized history event (`iteration` becomes `step`) |
| `summarize(result)` | `RunSummary` from a `SchedulerResult` |
| `build_simulation_result(original, outcome=None)` | `SimulationResult` from an original `SchedulerResult` and an optional `CounterfactualOutcome` |
| `run_scenario(scenario)` | runs a scheduler `Scenario` (no counterfactual) |
| `run_deadlock_counterfactual_demo()` | Scenario C: original DEADLOCK on Option A, counterfactual CONSENSUS on Option B, diverging at step 2 |
| `run_pex_agents_demo(task=...)` | Person 2's Analyst, Critic and Specialist (MockLLMProvider) under the Scheduler |

`DEMO_RUNS` maps each scenario name shown in the Flash Talk Demo tab to the
function that runs it. Add an entry there to show a new scenario in the UI.

Person 2's mock agents choose options with Python's `hash(task)`, so the
"PEX agents" outcome can change between app restarts unless `PYTHONHASHSEED`
is set. The scheduler scenarios are fully deterministic.

The Run Viewer and Experiment Analytics tabs still read the files produced by
the mock simulator in `experiments/run_experiment.py` (see
[evaluation.md](evaluation.md)).
