# UI API Documentation

## Running the UI

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
- `confidence`: Agent confidence score.

### `RunSummary`
Summarizes an execution trace.
- `status`: CONSENSUS or DEADLOCK.
- `prediction`: Final agreed prediction, if any.
- `iterations`: Number of steps executed.
- `deadlocked`: Boolean indicating if impasse was reached.

### `SimulationResult`
Pairs the original execution trace with the counterfactual alternative branch.
