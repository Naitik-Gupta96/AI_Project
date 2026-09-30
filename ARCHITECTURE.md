# Architecture Documentation

## System Architecture

```
                    TASK
                      |
                      v
                +-----------+
                | BLACKBOARD|  ← IMPLEMENTED NOW (Person 1)
                +-----+-----+
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       Agent A     Agent B     Agent C  ← FUTURE (Person 2)
          |           |           |
          +-----------+-----------+
                      |
                   Scheduler      ← FUTURE (Person 3)
                      |
             +--------+--------+
             |                 |
         Consensus          Deadlock
                                 |
                          Counterfactual  ← FUTURE (Person 3)
                                 |
                               UI          ← FUTURE (Person 4)
```

## Component Status

| Component | Status | Owner |
|-----------|--------|-------|
| Blackboard Core | ✅ IMPLEMENTED | Person 1 |
| PXP Protocol | ✅ IMPLEMENTED | Person 1 |
| PXP Validator | ✅ IMPLEMENTED | Person 1 |
| History/Event Log | ✅ IMPLEMENTED | Person 1 |
| Snapshot/Serialization | ✅ IMPLEMENTED | Person 1 |
| Thread Safety | ✅ IMPLEMENTED | Person 1 |
| PEX Agents | 🔄 FUTURE | Person 2 |
| LLM Integration | 🔄 FUTURE | Person 2 |
| Scheduler | 🔄 FUTURE | Person 3 |
| Deadlock Detection | 🔄 FUTURE | Person 3 |
| Counterfactual Engine | 🔄 FUTURE | Person 3 |
| Visualization UI | 🔄 FUTURE | Person 4 |
| Evaluation Framework | 🔄 FUTURE | Person 4 |

## Data Flow

1. **Task Initialization**: External caller creates a task on the Blackboard
2. **Agent Publication**: Agents publish PXP messages (validated before acceptance)
3. **State Update**: Blackboard updates current prediction/explanation, increments iteration, records history
4. **Scheduler Control**: Scheduler reads state/history, controls agent turns, sets status
5. **Counterfactual Replay**: Engine reads history/snapshots, creates branches
6. **Visualization**: UI reads state/history for display

## Blackboard State Machine

```
INITIALIZED → RUNNING → CONSENSUS
                    ↓
               DEADLOCK → (Counterfactual) → RUNNING
                    ↓
                 FAILED
```

- **INITIALIZED**: Task created, no messages yet
- **RUNNING**: Normal operation, agents publishing
- **CONSENSUS**: All agents RATIFY same prediction
- **DEADLOCK**: Agents cannot agree (REFUTE/REJECT cycle detected)
- **FAILED**: Unrecoverable error or timeout

## PXP Message Flow

```
Agent → PXPMessage → Validator → Blackboard.publish_message()
                                              ↓
                                    ┌─────────┴─────────┐
                                    ↓                   ↓
                              State Update        History Append
                              (prediction,        (immutable
                               explanation,        event)
                               iteration)
```

## Key Interfaces

### Blackboard API (src/ai_project/blackboard/board.py)
- `initialize_task(task: str, metadata: dict = None) -> None`
- `publish_message(message: PXPMessage) -> None`
- `get_state() -> BlackboardState`
- `get_latest_message() -> Optional[PXPMessage]`
- `get_history() -> List[HistoryEvent]`
- `get_iteration() -> int`
- `set_status(status: BlackboardStatus) -> None`
- `snapshot() -> BlackboardSnapshot`
- `record_event(event: HistoryEvent) -> None`

### PXP Protocol (src/ai_project/protocol/pxp.py)
- `PXPTag` enum: RATIFY, REVISE, REFUTE, REJECT
- `PXPMessage` dataclass with all required fields
- `PXPValidator` for structural validation

## Design Decisions

See [docs/decisions.md](decisions.md) for detailed Architecture Decision Records.