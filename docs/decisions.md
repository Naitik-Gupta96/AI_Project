# Architecture Decision Records

## Decision 1: In-Memory Blackboard for Prototype

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Need a Blackboard implementation for the flash talk prototype (Oct 6).

**Decision**: Use in-memory implementation with `threading.RLock` for synchronization.

**Reasoning**:
- Fast local development and testing
- Sufficient for flash-talk prototype with mock agents
- Thread-safe for concurrent agent simulation
- Can be replaced with Redis/PostgreSQL behind same interface later

**Future**: Persistent backend can be introduced behind the same `Blackboard` interface by creating `RedisBlackboard` subclass or adapter.

---

## Decision 2: Structured PXP Messages Instead of Free-Form Strings

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Agents need to communicate predictions and explanations.

**Decision**: Define `PXPMessage` dataclass with required fields: `message_id`, `agent_id`, `tag`, `prediction`, `explanation`, `confidence`, `iteration`, `timestamp`, `metadata`.

**Reasoning**:
- Makes validation, replay, visualization and analytics easier
- Enforces that every agent output has both prediction AND explanation
- Enables structured disagreement tracking (RATIFY/REVISE/REFUTE/REJECT)
- JSON-serializable for UI and experiment logging

---

## Decision 3: Dataclass Over Pydantic for PXPMessage

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Need a typed representation for PXP messages.

**Decision**: Use Python standard library `dataclass` instead of Pydantic.

**Reasoning**:
- Zero external dependencies (lightweight for academic prototype)
- Type hints + `__post_init__` validation sufficient
- `to_dict()` / `from_dict()` methods provide serialization
- Pydantic would add ~500KB dependency for marginal benefit here

**Trade-off**: Less automatic validation, but we have explicit `PXPValidator` class.

---

## Decision 4: Four Fixed PXP Tags (RATIFY, REVISE, REFUTE, REJECT)

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Proposal defines four interaction tags.

**Decision**: Implement exactly these four as `PXPTag` enum. No extensibility for now.

**Reasoning**:
- Matches proposal exactly
- Keeps protocol simple and analyzable
- Deadlock detection can rely on known tag patterns
- Visualization can have fixed color/legend per tag

**Future**: If research shows need for more tags (e.g., BRAINSTORM, QUESTION), can extend enum.

---

## Decision 5: threading.RLock for Synchronization

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Blackboard must be thread-safe for concurrent agent access.

**Decision**: Use `threading.RLock` protecting all state-changing operations.

**Reasoning**:
- Standard library, no dependencies
- Reentrant: same thread can acquire multiple times (needed for nested calls)
- Sufficient for prototype-scale concurrency (10-20 threads)
- All public mutating methods (`publish_message`, `set_status`, `record_event`, `snapshot`) protected

**Future**: For production, could use `asyncio.Lock` for async or Redis transactions for distributed.

---

## Decision 6: Append-Only History with Immutable Events

**Date**: 2024-09-30
**Status**: Accepted

**Context**: History needed for deadlock detection, counterfactual replay, visualization.

**Decision**: `History` class with append-only list of `HistoryEvent` objects. Events are immutable once appended.

**Reasoning**:
- Guarantees historical reproducibility for counterfactuals
- Past events never change when future state changes
- Enables exact replay at any iteration
- Thread-safe via same RLock

**Implementation**: `HistoryEvent` is a dataclass with `to_dict()`/`from_dict()`. `History.get_all()` returns copy.

---

## Decision 7: Snapshot Returns Deep Copy

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Counterfactual engine needs isolated historical state.

**Decision**: `Blackboard.snapshot()` returns `BlackboardSnapshot` with deep-copied state and history.

**Reasoning**:
- Modifying snapshot must NOT affect live Blackboard
- Enables safe counterfactual branching
- Tested: `test_modifying_snapshot_does_not_affect_live_board`
- Uses `copy.deepcopy` in `BlackboardSnapshot.__post_init__`

---

## Decision 8: Validation Before State Mutation

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Invalid PXP messages must not corrupt Blackboard.

**Decision**: `PXPValidator.validate()` runs BEFORE any state change in `publish_message()`.

**Reasoning**:
- Explicit invariant: invalid message → state unchanged, history unchanged, iteration not advanced
- Tested: `test_invalid_message_does_not_mutate_state`
- Validator only checks structural correctness, not reasoning quality

---

## Decision 9: Auto-Correct Iteration in publish_message

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Agents might send messages with wrong iteration numbers.

**Decision**: `publish_message()` auto-corrects `message.iteration` to `current_iteration + 1`.

**Reasoning**:
- Prevents iteration gaps/duplicates from buggy agents
- Maintains strict sequential iteration for history ordering
- Agents don't need to track iteration perfectly

---

## Decision 10: Status State Machine with Validated Transitions

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Blackboard status must follow logical progression.

**Decision**: `BlackboardStatus` enum with `set_status()` validating transitions.

**Valid Transitions**:
```
INITIALIZED → RUNNING, FAILED
RUNNING → CONSENSUS, DEADLOCK, FAILED
CONSENSUS → FAILED
DEADLOCK → RUNNING, FAILED
FAILED → (none)
```

**Reasoning**:
- Prevents invalid states (e.g., INITIALIZED → CONSENSUS)
- Clear semantics for scheduler and UI
- `InvalidStatusTransitionError` raised on violation

---

## Decision 10: Serialization via to_dict()/from_dict()

**Date**: 2024-09-30
**Status**: Accepted

**Context**: UI, experiments, and future persistence need JSON serialization.

**Decision**: All core objects implement `to_dict()` and `from_dict()` classmethod.

**Objects with Serialization**:
- `PXPMessage`
- `BlackboardState`
- `HistoryEvent`
- `BlackboardSnapshot`

**Reasoning**:
- Pure Python dicts, no custom encoders needed
- JSON-serializable (no datetime objects, enums converted to values)
- Enables experiment logging, UI APIs, file storage

---

## Decision 11: Public API Only - No Internal Access

**Date**: 2024-09-30
**Status**: Accepted

**Context**: Teammates must integrate without modifying Blackboard internals.

**Decision**: Document public API as contract. Private attributes (`_state`, `_history`, `_lock`) not for external use.

**Reasoning**:
- Enables future refactoring (Redis backend, async, etc.)
- Clear integration guide for teammates
- Tested via `docs/shared_contract.md` and `docs/integration_guide.md`