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

## Phase 22: Person 2 - Agents / PEX Layer
- [x] Agent abstraction (BaseAgent, AgentDecision, AgentContext)
- [x] AnalystAgent implementation
- [x] CriticAgent implementation
- [x] SpecialistAgent implementation
- [x] LLM provider abstraction (LLMProvider base class)
- [x] MockLLMProvider (deterministic, for demos/testing)
- [x] AgentDecisionParser with validation
- [x] Prompt templates (analyst.md, critic.md, specialist.md, structured_output.md)
- [x] Agent-to-Blackboard integration (agent.act(board) → PXPMessage)
- [x] Person 2 unit tests (models, base, analyst, critic, specialist, integration)
- [x] Person 2 LLM tests (mock provider, parser)
- [x] All existing Person 1 tests still pass
- [x] End-to-end agent demo (examples/agents_demo.py)
- [x] Documentation (agents_api.md, updated shared_contract.md, integration_guide.md)
- [x] Updated TEAM.md and TASKS.md

## Phase 23: Definition of Done (Updated)
- [x] Person 1 foundation is integrated
- [x] Existing baseline tests pass
- [x] BaseAgent exists
- [x] Analyst exists
- [x] Critic exists
- [x] Specialist exists
- [x] AgentDecision exists
- [x] Agents use the existing PXPTag/PXPMessage
- [x] Agent context is structured
- [x] History can be consumed
- [x] LLM provider abstraction exists
- [x] Deterministic mock provider exists
- [x] Structured output parser exists
- [x] Invalid output is rejected safely
- [x] Agent-to-Blackboard integration works
- [x] End-to-end agent test passes
- [x] All previous tests still pass
- [x] Agent demo works
- [x] Documentation is complete
- [x] Person 3 has a clear invocation API
- [x] Person 4 has structured outputs to consume
- [ ] Code committed
- [ ] Branch is pushed
- [ ] PR is ready

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