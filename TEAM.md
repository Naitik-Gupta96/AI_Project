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
**Status**: ✅ COMPLETE (this branch)

**Responsibilities**:
- Agent abstraction (BaseAgent, AgentDecision, AgentContext)
- Concrete agents: Analyst, Critic, Specialist
- LLM provider abstraction (MockLLMProvider, extensible interface)
- Structured output parsing and validation
- Prompt templates for each agent role
- Integration with Blackboard via `agent.act(board)` → `board.publish_message()`
- Deterministic mock provider for demos/testing
- Unit tests and integration tests
- Agent demo

**Deliverables**:
- `src/ai_project/agents/` - Agent implementations
- `src/ai_project/llm/` - LLM provider abstraction, mock, parser
- `prompts/` - Prompt templates
- `examples/agents_demo.py` - Working demonstration
- `tests/agents/`, `tests/llm/` - Test coverage
- `docs/agents_api.md` - API documentation

**Integration Point**:
```python
from ai_project.agents import AnalystAgent, CriticAgent, SpecialistAgent
from ai_project.llm import MockLLMProvider
from ai_project.blackboard import Blackboard

board = Blackboard()
board.initialize_task("Your task")

provider = MockLLMProvider()
analyst = AnalystAgent("analyst_1", provider)
critic = CriticAgent("critic_1", provider)
specialist = SpecialistAgent("specialist_1", provider)

# Scheduler controls WHEN
msg1 = analyst.act(board)
board.publish_message(msg1)

msg2 = critic.act(board)
board.publish_message(msg2)

msg3 = specialist.act(board)
board.publish_message(msg3)
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