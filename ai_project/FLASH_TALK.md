# Flash Talk Demo Instructions

The multi-agent blackboard presentation requires a simple, visual representation of deadlocks and counterfactual resolution.

## Presenting the Demo
To start the demo directly:
```bash
python examples/run_demo.py
```
This script launches the Streamlit UI which is pre-configured with a "Flash Talk Demo" tab.

### Presenter Guide
1. Run the demo script.
2. The UI will open showing a summary of the original path resulting in a `DEADLOCK`.
3. Explain the baseline execution (3 agents attempting to reach consensus, deadlocking at step 4).
4. Emphasize the "Counterfactual Path" column, showing where the deadlock was intercepted and alternative `CONSENSUS` reached.
5. Demonstrate the UI's interactive event steps to drill down into confidence and explanation values.
