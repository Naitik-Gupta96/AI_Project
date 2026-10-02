# Flash Talk - October 6

## Objective
Demonstrate a working vertical slice of the Intelligible Blackboard Architecture with Counterfactual Agents.

## What We Will Show (IMPLEMENTED)

### 1. Agents → Blackboard → Structured PXP Interaction
- Multiple agents publishing to a shared Blackboard
- PXP messages with prediction + explanation
- Four interaction tags: RATIFY, REVISE, REFUTE, REJECT

### 2. Disagreement Detection
- Agent A: RATIFY "Option B"
- Agent B: REFUTE "Option B" → proposes alternative
- Blackboard captures disagreement in history

### 3. History & Snapshot for Counterfactual Integration
- Append-only event log preserves all interactions
- Snapshot isolation enables counterfactual branching
- Ready for Person 3's counterfactual engine

### 4. Clean Integration Points
- Person 2: `agent.publish_message(board)` 
- Person 3: `board.get_history()`, `board.snapshot()`, `board.set_status()`
- Person 4: `board.get_state()`, `board.get_history()` (serializable)

## What We Will NOT Show (FUTURE WORK)
- LLM-based agents (Person 2)
- Scheduler with turn management (Person 3)
- Deadlock detection algorithm (Person 3)
- Counterfactual replay engine (Person 3)
- Real-time visualization UI (Person 4)
- Benchmark evaluation (Person 4)

## Demo Script
```bash
python examples/blackboard_demo.py
```

## Expected Demo Output
```
Task initialized: "Select the best approach for X"

Agent A -> RATIFY: "Option B" (confidence: 0.82)
  Explanation: "Option B satisfies all constraints."

Agent B -> REFUTE: "Option B" (confidence: 0.75)
  Explanation: "Option B fails constraint C3."

Current Status: RUNNING
Iteration: 2

History:
  1. Agent A RATIFY "Option B"
  2. Agent B REFUTE "Option B"

Snapshot created.
Snapshot modified (simulated counterfactual branch).
Live Blackboard unchanged ✓
```

## UI Demo (Person 4)
```bash
python examples/run_demo.py      # or: streamlit run frontend/app.py
```

### Presenter Guide
1. Run the demo script. The UI opens on the "Flash Talk Demo" tab.
2. Keep "Deadlock -> counterfactual consensus (Scenario C)" selected and click **Run Demo**.
3. Original path: analyst RATIFY Option A, critic REFUTE Option A, specialist REFUTE Option A -> `DEADLOCK` after 3 steps.
4. Counterfactual path: only step 2 is changed (the critic's refutation also names Option B). The UI shows "Diverged at Step 2"; the specialist then REVISEs to Option B and the critic and analyst RATIFY it -> `CONSENSUS` on Option B after 5 steps.
5. Expand individual steps to show each agent's confidence and explanation.

These runs use deterministic mock agents: they prove the mechanism, not an empirical result.

## Key Talking Points
1. **Structured Communication**: No free-form strings - every message has prediction + explanation + tag
2. **Validation First**: Invalid messages rejected before touching state
3. **Historical Reproducibility**: Full event log enables replay and counterfactuals
4. **Thread-Safe**: Ready for concurrent agent execution
5. **Integration Ready**: Stable APIs for all three teammates