# Team Roles and Responsibilities

## Person 1: Foundational Architecture / Blackboard / PXP
**Status**: ✅ COMPLETE (this branch)

**Responsibilities**:
- Blackboard core implementation with thread-safe state management
- PXP message protocol (RATIFY, REVISE, REFUTE, REJECT)
- PXP message validation
- History/event logging (append-only)
- Snapshot isolation for counterfactual replay
- Serialization (JSON-safe)
- Unit tests and demo
- Integration documentation for teammates

**Deliverables**:
- `src/ai_project/blackboard/` - Blackboard implementation
- `src/ai_project/protocol/` - PXP protocol and validator
- `docs/shared_contract.md` - Integration contract
- `docs/integration_guide.md` - How-to for teammates
- `examples/blackboard_demo.py` - Working demonstration
- `tests/` - Full test suite

---

## Person 2: PEX Agents + LLM Integration
**Status**: 🔄 FUTURE

**Responsibilities**:
- Implement agent classes that produce PXPMessage outputs
- LLM prompt engineering for structured prediction + explanation
- Agent orchestration (when to speak, what context to use)
- Integration with Blackboard via `publish_message()`

**Integration Point**:
```python
from ai_project.protocol import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard

board = Blackboard()
# ... get context from board.get_state(), board.get_history()
message = PXPMessage(
    message_id="msg_001",
    agent_id="agent_A",
    tag=PXPTag.RATIFY,
    prediction="Option B",
    explanation="Option B satisfies constraints.",
    confidence=0.82,
    iteration=board.get_iteration() + 1,
)
board.publish_message(message)
```

---

## Person 3: Scheduler + Deadlock Detection + Counterfactual Reasoning
**Status**: 🔄 FUTURE

**Responsibilities**:
- Deterministic scheduler controlling agent turn order
- Deadlock detection from Blackboard history patterns
- Counterfactual replay engine using `board.snapshot()` and history
- Resolution strategies (retry, branch, escalate)

**Integration Points**:
```python
from ai_project.blackboard import Blackboard, BlackboardStatus

board = Blackboard()

# Scheduler reads state
state = board.get_state()
latest = board.get_latest_message()
history = board.get_history()
iteration = board.get_iteration()

# Scheduler controls flow
board.set_status(BlackboardStatus.DEADLOCK)

# Counterfactual engine
snapshot = board.snapshot()
# ... create branch, replay with different agent choices
```

---

## Person 4: Visualization + Evaluation/Experiments
**Status**: 🔄 FUTURE

**Responsibilities**:
- Real-time UI showing Blackboard state, history, agent interactions
- Experiment framework for running benchmarks
- Results collection, analysis, and reporting
- Integration with serialized Blackboard state/history

**Integration Points**:
```python
from ai_project.blackboard import Blackboard

board = Blackboard()

# UI reads current state
state = board.get_state()  # Returns serializable dict-like object
history = board.get_history()  # List of serializable events

# For experiment logging
import json
json.dump(state.to_dict(), f)
json.dump([e.to_dict() for e in history], f)
```