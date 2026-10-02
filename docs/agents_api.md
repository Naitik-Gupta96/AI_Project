# Agents API Reference

## Overview

The Agents module provides a complete agent layer for the Blackboard/PXP system. It includes:

- **BaseAgent**: Abstract base class for all agents
- **AgentDecision**: Internal structured decision representation
- **AgentContext**: Structured context for agent reasoning
- **Concrete Agents**: Analyst, Critic, Specialist
- **LLM Providers**: Mock and extensible provider interface
- **Structured Parsing**: JSON output validation

---

## Core Classes

### AgentDecision

Internal structured representation of an agent's reasoning output.

```python
from ai_project.agents import AgentDecision
from ai_project.protocol import PXPTag

decision = AgentDecision(
    tag=PXPTag.RATIFY,
    prediction="Option A",
    explanation="Reasoning...",
    confidence=0.85,
    metadata={"key": "value"}
)

# Convert to PXPMessage for Blackboard
pxp_msg = decision.to_pxp_message("agent_id", iteration=1)

# Serialize
data = decision.to_dict()
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tag | PXPTag | Yes | RATIFY, REVISE, REFUTE, REJECT |
| prediction | str | Yes | Concrete decision |
| explanation | str | Yes | Reasoning trace |
| confidence | float | Yes | 0.0 - 1.0 |
| metadata | dict | No | Extra data |

**Methods**:
- `to_pxp_message(agent_id, iteration)` → PXPMessage
- `to_dict()` → dict

---

### AgentContext

Structured context passed to agents for reasoning.

```python
from ai_project.agents import AgentContext

context = AgentContext(
    task="Choose best option",
    current_prediction="Option A",
    current_explanation="Previous reasoning...",
    status="RUNNING",
    iteration=2,
    recent_history=[...],
    agent_id="critic_1",
    agent_role="Critic"
)

# For prompt templating
prompt_data = context.to_prompt_context()
```

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| task | str | Task description |
| current_prediction | str | Latest board prediction |
| current_explanation | str | Latest board explanation |
| status | str | Board status |
| iteration | int | Current iteration |
| recent_history | List[HistoryEvent] | Recent events |
| agent_id | str | This agent's ID |
| agent_role | str | This agent's role |
| metadata | dict | Extra context |

**Methods**:
- `to_prompt_context()` → dict for templating

---

### BaseAgent

Abstract base class for all agents.

```python
from ai_project.agents import BaseAgent
from ai_project.llm import MockLLMProvider

class MyAgent(BaseAgent):
    def reason(self, context: AgentContext) -> AgentDecision:
        # Your reasoning logic here
        return AgentDecision(...)

agent = MyAgent(agent_id="my_agent", role="Custom", llm_provider=MockLLMProvider())
message = agent.act(board)  # Returns PXPMessage
```

**Constructor**:
```python
BaseAgent(
    agent_id: str,           # Unique identifier
    role: str,               # Human-readable role
    llm_provider: LLMProvider = None,  # Optional LLM
    parser: AgentDecisionParser = None  # Optional parser
)
```

**Methods**:
- `act(board: Blackboard) -> PXPMessage` - Main entry point
- `reason(context: AgentContext) -> AgentDecision` - Abstract, implement this
- `get_identity() -> dict` - Returns {"agent_id", "role"}

**Internal**:
- `_build_context(board)` - Builds AgentContext from Blackboard
- `_call_llm(prompt)` - Calls provider and parses output

---

### AnalystAgent

Generates initial or independent predictions.

```python
from ai_project.agents import AnalystAgent
from ai_project.llm import MockLLMProvider

analyst = AnalystAgent(
    agent_id="analyst_1",
    llm_provider=MockLLMProvider()  # or real provider
)
```

**Behavior**:
- If no current prediction: generates initial prediction (RATIFY)
- If prediction exists: evaluates independently (usually RATIFY)
- Uses mock or real LLM provider

---

### CriticAgent

Challenges or validates current reasoning.

```python
from ai_project.agents import CriticAgent
from ai_project.llm import MockLLMProvider

critic = CriticAgent(
    agent_id="critic_1",
    llm_provider=MockLLMProvider()
)
```

**Behavior**:
- No prediction: returns REVISE requesting initial prediction
- Has prediction: RATIFY, REVISE, or REFUTE based on analysis
- Reads full history for context-aware critique

---

### SpecialistAgent

Provides independent specialized perspective.

```python
from ai_project.agents import SpecialistAgent
from ai_project.llm import MockLLMProvider

specialist = SpecialistAgent(
    agent_id="specialist_1",
    llm_provider=MockLLMProvider()
)
```

**Behavior**:
- Generates independent prediction based on specialization
- May RATIFY, REVISE, or REFUTE current prediction
- Considers full history and context

---

## LLM Providers

### LLMProvider (Abstract Base)

```python
from ai_project.llm import LLMProvider

class MyProvider(LLMProvider):
    def generate(self, prompt: str, **kwargs) -> str:
        return "response"

    def is_available(self) -> bool:
        return True
```

---

### MockLLMProvider

Deterministic provider for testing/demos.

```python
from ai_project.llm import MockLLMProvider

provider = MockLLMProvider(seed=42)
response = provider.generate("You are the Analyst agent. Task: test.")
# Returns JSON string with tag, prediction, explanation, confidence
```

**Features**:
- Deterministic: same seed + prompt = same output
- Role-aware: detects Analyst/Critic/Specialist from prompt
- Context-aware: extracts current prediction from prompt
- Fast: no network calls

---

### AgentDecisionParser

Parses and validates structured LLM output.

```python
from ai_project.llm import AgentDecisionParser, ParseError

parser = AgentDecisionParser()

# Valid JSON
json_str = '{"tag": "RATIFY", "prediction": "A", "explanation": "Good", "confidence": 0.8}'
decision = parser.parse(json_str)

# Handles markdown fences
json_str = '```json\n{"tag": "RATIFY", ...}\n```'
decision = parser.parse(json_str)
```

**Validation**:
- Required fields: tag, prediction, explanation, confidence
- Tag must be valid PXPTag
- Prediction/explanation non-empty
- Confidence in [0.0, 1.0]

**Exceptions**:
- `ParseError` for invalid/missing fields

---

## Usage Pattern

```python
from ai_project.blackboard import Blackboard
from ai_project.agents import AnalystAgent, CriticAgent, SpecialistAgent
from ai_project.llm import MockLLMProvider

# Setup
board = Blackboard()
board.initialize_task("Your task here")

provider = MockLLMProvider()
analyst = AnalystAgent("analyst_1", provider)
critic = CriticAgent("critic_1", provider)
specialist = SpecialistAgent("specialist_1", provider)

# Execute (scheduler would control this)
msg1 = analyst.act(board)
board.publish_message(msg1)

msg2 = critic.act(board)
board.publish_message(msg2)

msg3 = specialist.act(board)
board.publish_message(msg3)

# Results
history = board.get_history()
state = board.get_state()
```

---

## Error Handling

```python
from ai_project.agents import AgentError
from ai_project.llm import ParseError, ProviderUnavailableError

try:
    message = agent.act(board)
    board.publish_message(message)
except AgentError as e:
    # Agent reasoning failed (provider, parsing, etc.)
    print(f"Agent failed: {e}")
except InvalidMessageError as e:
    # PXP validation failed (should not happen with valid AgentDecision)
    print(f"Invalid message: {e}")
```

---

## Integration with Scheduler (Person 3)

```python
# Scheduler controls WHEN agents act
agent = agents["critic"]  # Get agent by role/id

# Scheduler decides order, then:
message = agent.act(board)  # Agent decides WHAT to communicate
board.publish_message(message)

# Scheduler can also:
board.set_status(BlackboardStatus.DEADLOCK)
snapshot = board.snapshot()  # For counterfactual
```

---

## Integration with UI/Evaluation (Person 4)

```python
# All structured data accessible
for event in board.get_history():
    print(event.agent_id, event.tag, event.prediction, event.confidence)

# Agent decisions available via history
state = board.get_state()
print(state.current_prediction, state.current_explanation)

# Serialization
json.dump(board.get_state().to_dict(), f)
json.dump([e.to_dict() for e in board.get_history()], f)
```