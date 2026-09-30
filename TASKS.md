# Task Roadmap

## Phase 0: Repository Inspection
- [x] Inspect repository (empty, no git)
- [x] Initialize git repository

## Phase 1: Bootstrap Repository Structure
- [x] Create directory structure (src/, docs/, tests/, examples/, experiments/, prompts/)
- [x] Create README.md
- [x] Create PROJECT.md
- [x] Create ARCHITECTURE.md
- [x] Create TEAM.md
- [x] Create TASKS.md (this file)
- [x] Create FLASH_TALK.md
- [x] Create RESEARCH.md
- [x] Create pyproject.toml
- [x] Create .gitignore
- [x] Create .env.example

## Phase 2: Development Tooling
- [x] pyproject.toml with project metadata, dependencies, test config
- [x] .gitignore for Python, venv, IDE, caches, env files

## Phase 3: Project Documentation
- [x] README.md
- [x] PROJECT.md
- [x] ARCHITECTURE.md
- [x] TEAM.md
- [x] TASKS.md
- [x] FLASH_TALK.md
- [x] RESEARCH.md

## Phase 4: PXP Message Contract Design
- [x] Design PXPMessage with: message_id, agent_id, tag, prediction, explanation, confidence, iteration, timestamp, metadata
- [x] Choose dataclass for typed representation
- [x] Document decision in docs/decisions.md

## Phase 5: PXP Tags Implementation
- [x] PXPTag enum with RATIFY, REVISE, REFUTE, REJECT
- [x] Validation: valid tag, non-empty agent_id, present prediction/explanation, confidence 0-1, non-negative iteration, present message_id, valid timestamp

## Phase 6: Blackboard State Implementation
- [x] BlackboardState with: task, status, iteration, current_prediction, current_explanation, latest_message, metadata
- [x] BlackboardStatus enum: INITIALIZED, RUNNING, CONSENSUS, DEADLOCK, FAILED
- [x] Document status meanings

## Phase 7: Blackboard API Implementation
- [x] initialize_task()
- [x] publish_message()
- [x] get_state()
- [x] get_latest_message()
- [x] get_history()
- [x] get_iteration()
- [x] set_status()
- [x] snapshot()
- [x] record_event()

## Phase 8: History Implementation
- [x] HistoryEvent with iteration, agent_id, tag, timestamp, prediction, explanation
- [x] Append-only event log
- [x] Order preserved
- [x] Past events immutable

## Phase 9: Thread Safety
- [x] threading.RLock for all state-changing operations
- [x] publish_message(), set_status(), record_event(), snapshot() protected
- [x] No corruption, no lost events, no duplicate iterations, consistent history

## Phase 10: Snapshot Implementation
- [x] snapshot() returns independent object
- [x] Modifying snapshot doesn't affect live board
- [x] Tested isolation

## Phase 11: Serialization
- [x] PXPMessage.to_dict() / from_dict()
- [x] BlackboardState.to_dict() / from_dict()
- [x] HistoryEvent.to_dict() / from_dict()
- [x] JSON-safe representations

## Phase 12: Validation Behavior
- [x] Invalid messages rejected BEFORE state change
- [x] State unchanged on validation failure
- [x] History unchanged on validation failure
- [x] Iteration not advanced on validation failure
- [x] Explicit invariant tests

## Phase 13: Blackboard Demo
- [x] examples/blackboard_demo.py
- [x] Creates board, initializes task
- [x] Agent A publishes RATIFY
- [x] Agent B publishes REFUTE
- [x] Prints state and history
- [x] Creates snapshot, mutates it, shows live board unchanged
- [x] Demo executes successfully

## Phase 14: Unit Tests
- [x] test_pxp.py - PXP validation tests
- [x] test_blackboard.py - Blackboard API tests
- [x] test_history.py - History tests
- [x] test_snapshot.py - Snapshot isolation tests
- [x] test_thread_safety.py - Concurrency tests
- [x] All tests pass

## Phase 15: Integration Contract
- [x] docs/shared_contract.md - How teammates use the API
- [x] Person 2: agent -> PXP message -> Blackboard
- [x] Person 3: scheduler -> Blackboard state/history/status
- [x] Person 4: UI -> Blackboard state/history (serialized)

## Phase 16: Integration Guide
- [x] docs/integration_guide.md
- [x] How Person 2 adds agents
- [x] How Person 3 adds scheduler
- [x] How Person 3 accesses history for counterfactual replay
- [x] How Person 4 consumes state/history

## Phase 17: Architecture Decision Records
- [x] docs/decisions.md
- [x] Decision: In-memory Blackboard for prototype
- [x] Decision: Structured PXP messages
- [x] Decision: dataclass over Pydantic
- [x] Decision: threading.RLock for synchronization
- [x] Decision: Append-only history

## Phase 18: Code Quality
- [x] Type hints throughout
- [x] Clear naming conventions
- [x] Docstrings on public APIs
- [x] Small focused functions
- [x] Sensible exceptions
- [x] No unnecessary globals
- [x] No hardcoded secrets
- [x] No dead code

## Phase 19: Test Full Foundation
- [x] Run full test suite
- [x] Fix all failures
- [x] Run unit tests
- [x] Run blackboard demo
- [x] Verify serialization
- [x] Verify concurrency

## Phase 20: Git Workflow
- [ ] Create branch feature/blackboard-pxp-foundation
- [ ] Commit progression (11+ commits)
- [ ] Push branch to GitHub
- [ ] Report branch, commits, files

## Phase 21: Boundaries Check
- [x] No LLM agents
- [x] No scheduler
- [x] No deadlock algorithm
- [x] No counterfactual engine
- [x] No Redis
- [x] No WebSockets
- [x] No React/D3
- [x] No benchmark ingestion

## Phase 22: Definition of Done
- [x] Clean repository structure
- [x] pyproject.toml exists
- [x] .gitignore exists
- [x] README exists
- [x] Project documentation exists
- [x] PXPMessage exists
- [x] PXPTag exists
- [x] All 4 tags work
- [x] Validation exists
- [x] Invalid messages rejected
- [x] Task initialization
- [x] State reading
- [x] Message publishing
- [x] Latest message available
- [x] Prediction/explanation stored
- [x] Status available
- [x] Iteration available
- [x] History available
- [x] History ordering preserved
- [x] Thread-safe updates
- [x] Snapshot support
- [x] Serialization support
- [x] Unit tests written
- [x] Concurrency tested
- [x] Serialization tested
- [x] Snapshot isolation tested
- [x] Invalid-input behavior tested
- [x] Full test suite passes
- [x] Demo script exists
- [x] Demo executed successfully
- [x] Blackboard API documented
- [x] PXP contract documented
- [x] Team integration contract documented
- [x] Architecture documented
- [x] Design decisions documented
- [ ] Work committed
- [ ] Branch identified
- [ ] Repository usable for teammates

## Phase 23: Final Self-Review
- [ ] Person 2 can build agent without modifying internals
- [ ] Person 3 can build scheduler without rewriting board
- [ ] Person 3 can access history for counterfactual replay
- [ ] Person 4 can read state/history for visualization
- [ ] Redis backend could be added behind same interface
- [ ] Malformed PXP cannot corrupt Blackboard
- [ ] Snapshot cannot modify live board
- [ ] Concurrent writes cannot lose events
- [ ] Code understandable by undergraduate teammate
- [ ] Documentation tells others exactly what to do