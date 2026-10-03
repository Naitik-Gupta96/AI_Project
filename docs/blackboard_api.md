# Blackboard API Reference

## Class: Blackboard

Thread-safe Blackboard for multi-agent communication via PXP protocol.

### Constructor

```python
Blackboard()
```
Creates an uninitialized Blackboard. Call `initialize_task()` before use.

### Methods

#### `initialize_task(task: str, metadata: Optional[Dict[str, Any]] = None) -> None`

Initialize a new task on the Blackboard.

**Parameters**:
- `task`: Task description string
- `metadata`: Optional dictionary of additional metadata

**Raises**: None

**Example**:
```python
board = Blackboard()
board.initialize_task("Choose the best architecture", {"team": "AI_Project"})
```

---

#### `publish_message(message: PXPMessage) -> None`

Publish a PXP message to the Blackboard.

Validates message before any state change. On success: updates state, increments iteration, appends to history.

**Parameters**:
- `message`: PXPMessage to publish

**Raises**:
- `InvalidMessageError`: If message fails validation (state unchanged)
- `BlackboardNotInitializedError`: If board not initialized

**Example**:
```python
msg = PXPMessage.create("agent_A", PXPTag.RATIFY, "Option B", "Reason...", 0.8, 1)
board.publish_message(msg)
```

---

#### `get_state() -> BlackboardState`

Get current Blackboard state (copy).

**Returns**: `BlackboardState` - Copy of current state

**Raises**: `BlackboardNotInitializedError` if board not initialized

---

#### `get_latest_message() -> Optional[Dict[str, Any]]`

Get the latest accepted message as a dictionary.

**Returns**: Message dict or `None` if no messages yet

**Raises**: `BlackboardNotInitializedError` if board not initialized

---

#### `get_history() -> List[HistoryEvent]`

Get the complete event history in chronological order.

**Returns**: `List[HistoryEvent]` - Copy of history list

**Raises**: `BlackboardNotInitializedError` if board not initialized

---

#### `get_iteration() -> int`

Get current iteration number.

**Returns**: `int` - Current iteration (0 if no messages published)

**Raises**: `BlackboardNotInitializedError` if board not initialized

---

#### `set_status(status: BlackboardStatus) -> None`

Set the Blackboard status with validated transitions.

**Parameters**:
- `status`: New `BlackboardStatus`

**Raises**:
- `BlackboardNotInitializedError`: If board not initialized
- `InvalidStatusTransitionError`: If transition is invalid

**Valid Transitions**:
```
INITIALIZED → RUNNING, FAILED
RUNNING → CONSENSUS, DEADLOCK, FAILED
CONSENSUS → FAILED
DEADLOCK → RUNNING, FAILED
FAILED → (none)
```

---

#### `record_event(event: HistoryEvent) -> None`

Manually record an event in history (for scheduler/counterfactual use).

**Parameters**:
- `event`: `HistoryEvent` to record

**Raises**: `BlackboardNotInitializedError` if board not initialized

---

#### `snapshot() -> BlackboardSnapshot`

Create an independent snapshot of current state and history.

The snapshot is a deep copy - modifying it does not affect the live Blackboard.

**Returns**: `BlackboardSnapshot` with copied state and history

**Raises**:
- `BlackboardNotInitializedError`: If board not initialized
- `SnapshotError`: If snapshot creation fails

---

#### `load_snapshot(snapshot: BlackboardSnapshot) -> None`

Load state from a snapshot (for counterfactual replay).

**Parameters**:
- `snapshot`: `BlackboardSnapshot` to restore from

**Raises**: `BlackboardError` if snapshot is invalid

---

#### `clear() -> None`

Reset Blackboard to uninitialized state (for testing).

---

#### `reset() -> None`

Alias for `clear()`.

---

## Class: PXPMessage

Structured PXP message for agent communication.

### Factory Method

```python
@classmethod
PXPMessage.create(
    agent_id: str,
    tag: PXPTag,
    prediction: str,
    explanation: str,
    confidence: Optional[float] = None,
    iteration: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
    message_id: Optional[str] = None,
) -> PXPMessage
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_id` | `str` | Auto | Unique identifier |
| `agent_id` | `str` | Yes | Agent identifier |
| `tag` | `PXPTag` | Yes | RATIFY/REVISE/REFUTE/REJECT |
| `prediction` | `str` | Yes | Agent's decision |
| `explanation` | `str` | Yes | Reasoning |
| `confidence` | `Optional[float]` | No | 0.0-1.0 |
| `iteration` | `int` | Yes | Iteration number |
| `timestamp` | `str` | Auto | ISO timestamp |
| `metadata` | `Dict` | No | Extra data |

### Methods

#### `to_dict() -> Dict[str, Any]`

Convert to JSON-serializable dictionary.

#### `@classmethod from_dict(data: Dict[str, Any]) -> PXPMessage`

Create from dictionary.

---

## Enum: PXPTag

PXP interaction tags.

```python
class PXPTag(Enum):
    RATIFY = "RATIFY"
    REVISE = "REVISE"
    REFUTE = "REFUTE"
    REJECT = "REJECT"
```

### Method

```python
@classmethod
PXPTag.from_string(value: str) -> PXPTag
```
Case-insensitive string to enum conversion.

---

## Class: BlackboardState

Current state of the Blackboard.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `task` | `str` | Task description |
| `status` | `BlackboardStatus` | Current status |
| `iteration` | `int` | Current iteration |
| `current_prediction` | `str` | Latest prediction |
| `current_explanation` | `str` | Latest explanation |
| `latest_message` | `Optional[Dict]` | Latest message dict |
| `metadata` | `Dict` | Additional metadata |

### Methods

#### `to_dict() -> Dict[str, Any]`
#### `@classmethod from_dict(data: Dict[str, Any]) -> BlackboardState`

---

## Enum: BlackboardStatus

Task status.

```python
class BlackboardStatus(Enum):
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    CONSENSUS = "CONSENSUS"
    DEADLOCK = "DEADLOCK"
    FAILED = "FAILED"
```

---

## Class: HistoryEvent

Immutable event record (`frozen` dataclass). Assigning to a field raises
`dataclasses.FrozenInstanceError`, so history cannot be edited through a
reference returned by `get_history()` or `snapshot()`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | `int` | Iteration number |
| `agent_id` | `str` | Agent identifier |
| `tag` | `str` | PXP tag value |
| `timestamp` | `str` | ISO timestamp |
| `prediction` | `str` | Prediction |
| `explanation` | `str` | Explanation |
| `confidence` | `Optional[float]` | Confidence |
| `message_id` | `str` | Message ID |
| `metadata` | `Dict[str, Any]` | The message's metadata (e.g. `alternative`), kept so counterfactual replays are faithful |

### Methods

#### `to_dict() -> Dict[str, Any]`
#### `@classmethod from_dict(data: Dict[str, Any]) -> HistoryEvent`
#### `@classmethod from_message(message: PXPMessage, iteration: int) -> HistoryEvent`

---

## Class: BlackboardSnapshot

Independent snapshot of Blackboard state.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `state` | `BlackboardState` | Deep copied state |
| `history` | `List[HistoryEvent]` | Deep copied history |
| `timestamp` | `str` | Snapshot timestamp |

### Methods

#### `to_dict() -> Dict[str, Any]`
#### `@classmethod from_dict(data: Dict[str, Any]) -> BlackboardSnapshot`

---

## Exceptions

| Exception | When Raised |
|-----------|-------------|
| `BlackboardError` | Base class |
| `InvalidMessageError` | PXP message validation failed |
| `BlackboardNotInitializedError` | Operations before `initialize_task()` |
| `InvalidStatusTransitionError` | Invalid status transition |
| `SnapshotError` | Snapshot creation/load failed |

---

## Class: PXPValidator

Static validation for PXP messages.

### Methods

```python
@staticmethod
PXPValidator.validate(message: PXPMessage) -> List[ValidationError]
```
Returns list of errors (empty = valid).

```python
@staticmethod
PXPValidator.validate_or_raise(message: PXPMessage) -> None
```
Raises `ValueError` if invalid.

### Validation Rules

- `message_id`: non-empty
- `agent_id`: non-empty
- `tag`: valid `PXPTag`
- `prediction`: non-empty
- `explanation`: non-empty
- `confidence`: if present, 0.0-1.0
- `iteration`: non-negative
- `timestamp`: valid string