# Integration Guide for Teammates

This guide explains how each team member should integrate their components with the Blackboard/PXP foundation.

---

## HOW PERSON 2 SHOULD ADD AGENTS

### Using Built-in Agents (Ready to Use)

```python
from ai_project.agents import AnalystAgent, CriticAgent, SpecialistAgent
from ai_project.llm import MockLLMProvider
from ai_project.blackboard import Blackboard

# Create Blackboard
board = Blackboard()
board.initialize_task("Your task here")

# Create agents with mock provider (deterministic, no external deps)
provider = MockLLMProvider()
analyst = AnalystAgent(agent_id="analyst_1", llm_provider=provider)
critic = CriticAgent(agent_id="critic_1", llm_provider=provider)
specialist = SpecialistAgent(agent_id="specialist_1", llm_provider=provider)

# Scheduler controls WHEN agents act
msg1 = analyst.act(board)
board.publish_message(msg1)

msg2 = critic.act(board)
board.publish_message(msg2)

msg3 = specialist.act(board)
board.publish_message(msg3)
```

### Building Custom Agents

```python
from ai_project.agents import BaseAgent
from ai_project.agents.models import AgentContext, AgentDecision
from ai_project.protocol import PXPTag
from ai_project.llm import MockLLMProvider

class MyCustomAgent(BaseAgent):
    def reason(self, context: AgentContext) -> AgentDecision:
        # Access structured context
        task = context.task
        history = context.recent_history
        current = context.current_prediction
        
        # Your reasoning logic here
        return AgentDecision(
            tag=PXPTag.RATIFY,
            prediction="Your decision",
            explanation="Your reasoning trace",
            confidence=0.85,
            metadata={"custom": "data"}
        )

agent = MyCustomAgent(agent_id="custom_1", role="Custom Role", llm_provider=MockLLMProvider())
message = agent.act(board)
board.publish_message(message)
```

### Agent Output Requirements

- **Prediction**: Concrete decision/answer (string)
- **Explanation**: Reasoning trace (string)
- **Tag**: One of RATIFY, REVISE, REFUTE, REJECT
- **Confidence**: Float 0-1

---

## HOW PERSON 3 SHOULD ADD SCHEDULER

### Step 1: Basic Scheduler Loop
```python
# scheduler/scheduler.py
from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.protocol import PXPMessage, PXPTag

class Scheduler:
    def __init__(self, board: Blackboard, agents: list):
        self.board = board
        self.agents = agents
        self.max_iterations = 10

    def run(self, task: str):
        # 1. Initialize
        self.board.initialize_task(task)
        self.board.set_status(BlackboardStatus.RUNNING)

        # 2. Main loop
        for iteration in range(1, self.max_iterations + 1):
            # Check for consensus/deadlock
            if self._check_consensus():
                self.board.set_status(BlackboardStatus.CONSENSUS)
                break
            if self._check_deadlock():
                self.board.set_status(BlackboardStatus.DEADLOCK)
                break

            # 3. Select next agent (round-robin, priority, etc.)
            agent = self._select_agent(iteration)
            
            # 4. Get agent's message
            message = agent.reason(self.board)
            
            # 5. Publish (validated)
            self.board.publish_message(message)

        return self.board.get_state()

    def _check_consensus(self) -> bool:
        # e.g., last N messages all RATIFY same prediction
        history = self.board.get_history()
        if len(history) < 2:
            return False
        last_two = history[-2:]
        return (last_two[0].tag == "RATIFY" and 
                last_two[1].tag == "RATIFY" and
                last_two[0].prediction == last_two[1].prediction)

    def _check_deadlock(self) -> bool:
        # e.g., alternating REFUTE/REJECT without progress
        history = self.board.get_history()
        if len(history) < 4:
            return False
        recent_tags = [e.tag for e in history[-4:]]
        return recent_tags.count("REFUTE") >= 3
```

### Step 2: Scheduler Controls Status
```python
# Status transitions (validated)
board.set_status(BlackboardStatus.RUNNING)      # Normal operation
board.set_status(BlackboardStatus.CONSENSUS)    # Agreement reached
board.set_status(BlackboardStatus.DEADLOCK)     # Stuck - needs counterfactual
board.set_status(BlackboardStatus.FAILED)       # Error/timeout
```

---

## HOW PERSON 3 SHOULD ACCESS HISTORY FOR COUNTERFACTUAL REPLAY

### Step 1: Read History for Analysis
```python
# counterfactual/analyzer.py
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import HistoryEvent

def analyze_deadlock(board: Blackboard) -> dict:
    history = board.get_history()
    
    # Find conflict pattern
    conflicts = []
    for i, event in enumerate(history):
        if event.tag in ("REFUTE", "REJECT"):
            conflicts.append({
                "iteration": event.iteration,
                "agent": event.agent_id,
                "prediction": event.prediction,
                "explanation": event.explanation,
            })
    
    # Identify branching points
    branch_points = find_branch_points(history)
    
    return {
        "conflicts": conflicts,
        "branch_points": branch_points,
    }
```

### Step 2: Create Snapshot for Branching
```python
# counterfactual/engine.py
from ai_project.blackboard import Blackboard
from ai_project.blackboard.models import BlackboardSnapshot

class CounterfactualEngine:
    def __init__(self, board: Blackboard):
        self.board = board
        self.branches = []

    def create_branch(self, branch_name: str, modified_state: dict = None) -> BlackboardSnapshot:
        # 1. Snapshot current state
        snapshot = self.board.snapshot()
        
        # 2. Apply modifications to snapshot
        if modified_state:
            snapshot.state.current_prediction = modified_state.get("prediction", snapshot.state.current_prediction)
            snapshot.state.current_explanation = modified_state.get("explanation", snapshot.state.current_explanation)
            snapshot.state.metadata.update(modified_state.get("metadata", {}))
        
        # 3. Store branch
        self.branches.append({
            "name": branch_name,
            "snapshot": snapshot,
            "parent_iteration": self.board.get_iteration(),
        })
        
        return snapshot

    def replay_branch(self, branch_name: str) -> Blackboard:
        branch = next(b for b in self.branches if b["name"] == branch_name)
        # Load snapshot into a NEW board for isolated replay
        replay_board = Blackboard()
        replay_board.load_snapshot(branch["snapshot"])
        return replay_board
```

### Step 3: Replay with Different Agent Choices
```python
# On replay board, inject different agent responses
replay_board = engine.replay_branch("branch_v1")

# Simulate different agent at iteration 3
different_msg = PXPMessage.create(
    agent_id="agent_C",
    tag=PXPTag.RATIFY,  # Instead of REFUTE
    prediction="Alternative approach",
    explanation="Counterfactual reasoning...",
    confidence=0.75,
    iteration=3,
)
replay_board.publish_message(different_msg)

# Compare outcomes
original_outcome = original_board.get_state().current_prediction
counterfactual_outcome = replay_board.get_state().current_prediction
```

---

## HOW PERSON 4 SHOULD CONSUME STATE/HISTORY

### Step 1: Real-Time State Polling
```python
# ui/state_poller.py
import time
from ai_project.blackboard import Blackboard

class StatePoller:
    def __init__(self, board: Blackboard, interval: float = 0.5):
        self.board = board
        self.interval = interval

    def get_display_data(self) -> dict:
        state = self.board.get_state()
        return {
            "task": state.task,
            "status": state.status.value,
            "iteration": state.iteration,
            "prediction": state.current_prediction,
            "explanation": state.current_explanation,
            "latest_agent": state.latest_message["agent_id"] if state.latest_message else None,
            "latest_tag": state.latest_message["tag"] if state.latest_message else None,
        }

    def get_timeline(self) -> list:
        history = self.board.get_history()
        return [
            {
                "iteration": e.iteration,
                "agent": e.agent_id,
                "tag": e.tag,
                "prediction": e.prediction,
                "explanation": e.explanation,
                "confidence": e.confidence,
                "timestamp": e.timestamp,
            }
            for e in history
        ]
```

### Step 2: WebSocket/HTTP Endpoint (Example)
```python
# ui/api.py
from flask import Flask, jsonify
from ai_project.blackboard import Blackboard

app = Flask(__name__)
board = Blackboard()  # Shared instance

@app.route("/api/state")
def get_state():
    return jsonify(board.get_state().to_dict())

@app.route("/api/history")
def get_history():
    return jsonify([e.to_dict() for e in board.get_history()])

@app.route("/api/snapshot")
def get_snapshot():
    return jsonify(board.snapshot().to_dict())
```

### Step 3: Experiment Data Export
```python
# experiments/exporter.py
import json
from pathlib import Path
from ai_project.blackboard import Blackboard

def export_experiment(board: Blackboard, output_dir: str):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # State
    with open(f"{output_dir}/state.json", "w") as f:
        json.dump(board.get_state().to_dict(), f, indent=2)
    
    # History
    with open(f"{output_dir}/history.json", "w") as f:
        json.dump([e.to_dict() for e in board.get_history()], f, indent=2)
    
    # Snapshot
    with open(f"{output_dir}/snapshot.json", "w") as f:
        json.dump(board.snapshot().to_dict(), f, indent=2)
```

---

## QUICK START CHECKLIST

### Person 2 (Agents)
- [ ] Import `PXPMessage`, `PXPTag` from `ai_project.protocol`
- [ ] Implement `reason(board) -> PXPMessage` method
- [ ] Use `board.get_state()` and `board.get_history()` for context
- [ ] Call `board.publish_message(msg)` to submit
- [ ] Handle `InvalidMessageError` for validation failures

### Person 3 (Scheduler)
- [ ] Import `Blackboard`, `BlackboardStatus` from `ai_project.blackboard`
- [ ] Implement scheduler loop with `board.set_status()`
- [ ] Use `board.get_history()` for deadlock detection
- [ ] Use `board.snapshot()` for counterfactual branches
- [ ] Use `board.load_snapshot()` to replay branches

### Person 4 (UI/Experiments)
- [ ] Use `board.get_state().to_dict()` for JSON state
- [ ] Use `[e.to_dict() for e in board.get_history()]` for timeline
- [ ] Use `board.snapshot().to_dict()` for reproducibility
- [ ] Poll at reasonable intervals (0.5-1s for demo)

---

## COMMON PATTERNS

### Running the Demo
```bash
python examples/blackboard_demo.py
```

### Running Tests
```bash
pytest tests/ -v
```

### Importing in Your Code
```python
from ai_project.protocol import PXPMessage, PXPTag, PXPValidator
from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.blackboard.models import HistoryEvent, BlackboardSnapshot
from ai_project.blackboard.exceptions import (
    InvalidMessageError,
    BlackboardNotInitializedError,
    InvalidStatusTransitionError,
)
```