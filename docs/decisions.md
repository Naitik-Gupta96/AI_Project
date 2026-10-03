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

**Future**: If experiments show a need for more tags (e.g., BRAINSTORM, QUESTION), can extend enum.

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

**Implementation**: `HistoryEvent` is a frozen dataclass with `to_dict()`/`from_dict()`, and it keeps the message's metadata (see Decision 15). `History.get_all()` returns a copy of the list.

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

## Decision 10b: Serialization via to_dict()/from_dict()

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
- Documented in `docs/shared_contract.md`; enforced by `test_only_public_blackboard_api_is_used`

---

The records below were added during the 2026-10-03 hardening pass.

## Decision 12: A Deterministic Mock Provider Instead of Mock Logic in Agents

**Status**: Accepted

**Context**: The agents ran private mock methods whenever they detected a
`MockLLMProvider`, choosing options with Python's `hash()`, which is salted
per process. The same task deadlocked in one process and reached consensus in
another, and the provider had a second, unrelated mock implementation.

**Decision**: Every decision goes through one pipeline (context → prompt →
`LLMProvider.generate` → parser → decision). The deterministic mock is a
provider that applies explicit role rules to the structured context.

**Reasoning**: One abstraction; the demo is reproducible; the rules are
readable and testable; swapping in a model changes one constructor argument.
Labelling: the mock is called a deterministic mock everywhere, never an LLM.

## Decision 13: Local Model Support Is Optional

**Status**: Accepted

**Decision**: `OllamaProvider` (standard library HTTP) behind the same interface.
Not used by the demo, the tests' expected outcomes or any reported result.

**Reasoning**: The flash talk must not depend on a model, network or API key,
and a 4B local model took minutes per run and did not follow the role
instructions reliably in a trial run. Keeping the path working allows LLM
experiments later without changing the architecture.

## Decision 14: PXP Tag Semantics

**Status**: Accepted

**Decision**: `prediction` always names the option the tag is about. RATIFY X
supports X; REVISE X replaces the proposal with X; REFUTE X objects to the
standing proposal X, with any alternative in `metadata["alternative"]`; REJECT
objects to every option. Agents normalize model output to these rules.

**Reasoning**: Consensus, deadlock and policies derive stances from history. A
REFUTE whose prediction is some other option (which the old mock agents
produced) is ambiguous and breaks those derivations.

## Decision 15: Branches Re-publish History, Including Metadata

**Status**: Accepted

**Decision**: A counterfactual branch is a new Blackboard on which history up
to the branch point is re-published (with each message's metadata), then the
intervention, then a new Scheduler replays. `HistoryEvent` stores metadata.

**Reasoning**: Re-publishing makes the Blackboard recompute its own state
instead of trusting an edited snapshot. Metadata matters because agents act on
it (a named alternative). Without it, a pure replay of a run containing an
alternative could diverge from the original.

## Decision 16: What "Deadlock" Means

**Status**: Accepted

**Decision**: Deadlock is either (a) the standing proposal was objected to
`max_disagreement_cycles` (2) times since it was introduced and someone still
objects, or (b) no never-before-seen proposal for `max_stagnant_steps` (6)
messages while someone still dissents. Running out of `max_steps` is a separate
stop reason, not a deadlock.

**Reasoning**: Both rules are checkable from history alone and explainable in
one sentence. A single objection, or an objection that leads to a new proposal,
is normal debate and is not counted.

## Decision 17: Counterfactual Agents and the Counterfactual Fraction

**Status**: Accepted

**Context**: The project title promises counterfactual agents, and the old
experiment config varied a "counterfactual fraction" (0, 0.33, 0.66, 1) over 3
agents without defining it. The old runner implemented it as a probability of
recovery, which measured nothing.

**Decision**: An agent is *counterfactual-capable* if, after a deadlock, it may
revise one of its own past messages in hindsight, using only its own evidence
and what the run made public. The counterfactual fraction is the share of the 3
agents that are capable. The resolver tries revisions latest message first (the
smallest change to history) and stops at the first branch that reaches consensus.

## Decision 18: Experiments Run the Real Pipeline

**Status**: Accepted

**Decision**: The experiment calls `pipeline.run_task` for every trial and
records seed, task, condition, traces, branches, provider and commit. Synthetic
*tasks* are allowed and labelled; synthetic *outcomes* are not.

**Reasoning**: Results must come from the system they describe and be
re-executable (the UI re-runs any trial and checks it against the record).

## Decision 19: Replaceable, Stateless Scheduling Policies

**Status**: Accepted

**Decision**: A policy is an object with `select(SchedulingContext) -> Selection`
(agent id, rule, human-readable reason). The built-in `RoundRobinPolicy` and
`PriorityPolicy` keep no state between calls.

**Reasoning**: Turn-taking is a research variable (the proposal compares
coordination strategies), so it must change without touching the Scheduler.
Statelessness is what makes counterfactual replay faithful: a branch board
with the same history gets the same selections. The reason string goes into
the trace, so the UI can show why each agent spoke. Snapshots (Decision 7)
serve the same goal from the data side: branches start from an isolated copy
of history, never from the live board.
