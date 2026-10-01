# Shared Integration Contract

This document defines the exact interfaces that teammates must use to integrate with the Blackboard/PXP foundation.
**Do NOT access private internal dictionaries or mutate Blackboard internals directly.**
The public API below is the contract.

---

## For Person 2: PEX Agents + LLM Integration (Implemented)

### Agent Layer API

The agent layer provides ready-to-use agents and building blocks.

```python
from ai_project.agents import (
    AnalystAgent, CriticAgent, SpecialistAgent,
    BaseAgent, AgentDecision, AgentContext,
    AgentError
)
from ai_project.llm import (
    MockLLMProvider, AgentDecisionParser,
    LLMProvider, ParseError
)
from ai_project.blackboard import Blackboard
```

### Using Built-in Agents

```python
# Create agents with mock provider (for demo/testing)
provider = MockLLMProvider()
analyst = AnalystAgent(agent_id="analyst_1", llm_provider=provider)
critic = CriticAgent(agent_id="critic_1", llm_provider=provider)
specialist = SpecialistAgent(agent_id="specialist_1", llm_provider=provider)

# Agents act on Blackboard (scheduler controls WHEN)
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

class CustomAgent(BaseAgent):
    def reason(self, context: AgentContext) -> AgentDecision:
        # Access structured context
        task = context.task
        history = context.recent_history
        current = context.current_prediction
        
        # Your reasoning logic
        return AgentDecision(
            tag=PXPTag.RATIFY,
            prediction="Your decision",
            explanation="Your reasoning",
            confidence=0.85
        )

agent = CustomAgent(agent_id="custom_1", role="Custom", llm_provider=provider)
message = agent.act(board)
```

### Agent Context

Agents receive structured `AgentContext`:

```python
context = AgentContext(
    task="Task description",
    current_prediction="Option A",
    current_explanation="Previous reasoning",
    status="RUNNING",
    iteration=2,
    recent_history=[HistoryEvent, ...],
    agent_id="critic_1",
    agent_role="Critic"
)

# For prompt templating
prompt_data = context.to_prompt_context()
```

### LLM Provider Abstraction

```python
# Mock provider (deterministic, no external deps)
provider = MockLLMProvider(seed=42)

# Custom provider
class MyProvider(LLMProvider):
    def generate(self, prompt: str, **kwargs) -> str:
        # Call your LLM
        return llm_response

    def is_available(self) -> bool:
        return True

provider = MyProvider()
```

### Structured Output Parsing

```python
from ai_project.llm import AgentDecisionParser, ParseError

parser = AgentDecisionParser()

# Valid JSON with all required fields
json_str = '{"tag": "RATIFY", "prediction": "A", "explanation": "Reason", "confidence": 0.8}'
decision = parser.parse(json_str)

# Handles markdown fences automatically
json_str = '```json\n{"tag": "RATIFY", ...}\n```'
decision = parser.parse(json_str)

# Validation errors
try:
    parser.parse('invalid')
except ParseError as e:
    print(f"Parse failed: {e}")
```

### Required Fields in AgentDecision / PXPMessage

| Field | Required | Description |
|-------|----------|-------------|
| `agent_id` | Yes | Non-empty string, unique per agent |
| `tag` | Yes | `PXPTag.RATIFY`, `REVISE`, `REFUTE`, `REJECT` |
| `prediction` | Yes | Non-empty string |
| `explanation` | Yes | Non-empty string |
| `confidence` | Yes | Float 0.0-1.0 |
| `iteration` | Auto | Auto-corrected by Blackboard |
| `message_id` | Auto | Auto-generated if not provided |
| `timestamp` | Auto | Auto-generated |
| `metadata` | No | Dict for extra data |

---

## For Person 2: PEX Agents + LLM Integration (Legacy Pattern)

### Input
- Task description (from `board.get_state().task`)
- Current board state (from `board.get_state()`)
- History (from `board.get_history()`)

### Output
- `PXPMessage` object

### Usage Pattern
```python
from ai_project.protocol import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard

board = Blackboard()

# 1. Get context from board
state = board.get_state()
history = board.get_history()
task = state.task
current_iteration = state.iteration

# 2. Agent reasoning (LLM call, etc.)
# ... your agent logic here ...

# 3. Create PXP message
message = PXPMessage.create(
    agent_id="my_agent",           # Unique agent identifier
    tag=PXPTag.RATIFY,             # One of: RATIFY, REVISE, REFUTE, REJECT
    prediction="Option B",         # The agent's decision
    explanation="Reasoning...",    # Why this decision
    confidence=0.82,               # Optional: 0.0 to 1.0
    iteration=current_iteration + 1,
    metadata={"model": "gpt-4", "prompt_version": "v1"}  # Optional
)

# 4. Publish to Blackboard (validated before acceptance)
board.publish_message(message)

# On validation failure: InvalidMessageError raised, state unchanged
```

### Required Fields in PXPMessage
| Field | Required | Description |
|-------|----------|-------------|
| `agent_id` | Yes | Non-empty string, unique per agent |
| `tag` | Yes | `PXPTag.RATIFY`, `REVISE`, `REFUTE`, or `REJECT` |
| `prediction` | Yes | Non-empty string |
| `explanation` | Yes | Non-empty string |
| `confidence` | No | Float 0.0-1.0 |
| `iteration` | Yes | Must match expected (auto-corrected) |
| `message_id` | Auto | Auto-generated if not provided |
| `timestamp` | Auto | Auto-generated |
| `metadata` | No | Dict for extra data |

### Validation Rules (Enforced by Blackboard)
- `agent_id` must be non-empty
- `tag` must be valid PXPTag
- `prediction` must be non-empty
- `explanation` must be non-empty
- `confidence` if present must be 0.0-1.0
- `iteration` must be non-negative
- Invalid messages are rejected BEFORE state mutation

---

## For Person 3: Scheduler + Deadlock Detection + Counterfactual Reasoning

### Scheduler: Reading State
```python
from ai_project.blackboard import Blackboard, BlackboardStatus

board = Blackboard()

# Current state
state = board.get_state()              # BlackboardState
latest = board.get_latest_message()    # Dict or None
history = board.get_history()          # List[HistoryEvent]
iteration = board.get_iteration()      # int

# Task info
task = state.task
status = state.status
current_prediction = state.current_prediction
current_explanation = state.current_explanation
```

### Scheduler: Controlling Flow
```python
# Set status (validated transitions only)
board.set_status(BlackboardStatus.RUNNING)
board.set_status(BlackboardStatus.CONSENSUS)
board.set_status(BlackboardStatus.DEADLOCK)
board.set_status(BlackboardStatus.FAILED)

# Valid transitions:
# INITIALIZED -> RUNNING, FAILED
# RUNNING -> CONSENSUS, DEADLOCK, FAILED
# CONSENSUS -> FAILED
# DEADLOCK -> RUNNING, FAILED
# FAILED -> (none)
```

### Scheduler: Publishing Messages (e.g., for system messages)
```python
from ai_project.protocol import PXPMessage, PXPTag

msg = PXPMessage.create(...)
board.publish_message(msg)
```

### Counterfactual Engine: History Access
```python
# Full history for replay
history = board.get_history()  # List[HistoryEvent] in chronological order

# Each HistoryEvent has:
# - iteration, agent_id, tag, timestamp
# - prediction, explanation, confidence, message_id

# Filter by iteration
events_at_iteration = [e for e in history if e.iteration == 3]
```

### Counterfactual Engine: Snapshot & Branch
```python
# Create isolated snapshot
snapshot = board.snapshot()  # BlackboardSnapshot

# Snapshot contains:
snapshot.state      # BlackboardState (deep copied)
snapshot.history    # List[HistoryEvent] (deep copied)
snapshot.timestamp  # ISO timestamp

# Modify snapshot for counterfactual branch
snapshot.state.current_prediction = "Alternative decision"
snapshot.state.metadata["branch"] = "counterfactual_v1"

# Load snapshot to replay (replaces live state)
board.load_snapshot(snapshot)

# Continue from branch...
board.publish_message(new_message)
```

---

## For Person 4: Visualization + Evaluation/Experiments

### UI: Reading State for Display
```python
from ai_project.blackboard import Blackboard

board = Blackboard()

# Current state (serializable)
state = board.get_state()
state_dict = state.to_dict()  # JSON-serializable dict

# History for timeline (serializable)
history = board.get_history()
history_dicts = [e.to_dict() for e in history]  # List[dict]

# Latest message for highlight
latest = board.get_latest_message()  # Dict or None
```

### Experiment Logging: Serialization
```python
import json

# Log full board state
with open("experiment_state.json", "w") as f:
    json.dump(board.get_state().to_dict(), f, indent=2)

# Log full history
with open("experiment_history.json", "w") as f:
    json.dump([e.to_dict() for e in board.get_history()], f, indent=2)

# Log snapshot for reproducibility
snapshot = board.snapshot()
with open("experiment_snapshot.json", "w") as f:
    json.dump(snapshot.to_dict(), f, indent=2)
```

### Key Data Structures (all have `.to_dict()`)
| Object | Method | Returns |
|--------|--------|---------|
| `BlackboardState` | `.to_dict()` | `dict` |
| `HistoryEvent` | `.to_dict()` | `dict` |
| `BlackboardSnapshot` | `.to_dict()` | `dict` |
| `PXPMessage` | `.to_dict()` | `dict` |

All dicts are JSON-serializable (no Python-specific types).

---

## What NOT To Do

| ❌ Don't | ✅ Do |
|----------|-------|
| `board._state.iteration = 5` | `board.publish_message(msg)` (increments) |
| `board._history.append(event)` | `board.record_event(event)` |
| `board._state.status = ...` | `board.set_status(BlackboardStatus.RUNNING)` |
| Access `board._lock` | Use public API (thread-safe) |
| Mutate `snapshot.state` expecting live change | Use `board.load_snapshot()` to apply |
| Assume `board.get_state()` returns same object | It returns a copy; mutate copy, not original |

---

## Error Handling

```python
from ai_project.blackboard.exceptions import (
    InvalidMessageError,
    BlackboardNotInitializedError,
    InvalidStatusTransitionError,
    SnapshotError,
)

try:
    board.publish_message(msg)
except InvalidMessageError as e:
    # Message validation failed - state unchanged
    print(f"Invalid message: {e}")

try:
    board.set_status(BlackboardStatus.CONSENSUS)
except InvalidStatusTransitionError as e:
    # Invalid transition - state unchanged
    print(f"Invalid transition: {e}")
```