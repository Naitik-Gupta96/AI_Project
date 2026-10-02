# AI Project: Intelligible Blackboard Architecture with Counterfactual Agents

## Project Purpose
This project implements an intelligible blackboard architecture for multi-agent AI systems where agents communicate through a globally shared structured Blackboard rather than direct message-passing chains. The system supports counterfactual reasoning for deadlock resolution.

## Current Stage
**Phase 1: Foundational Architecture (Person 1)**
- Blackboard + PXP protocol foundation complete
- Scheduler, consensus/deadlock detection and counterfactual replay complete (Person 3, `feature/scheduler-counterfactual`)
- Ready for Person 2 (PEX agents + LLM), Person 3 (Scheduler + Counterfactual), Person 4 (UI + Evaluation)

## Architecture Overview
```
                    TASK
                      |
                      v
                +-----------+
                | BLACKBOARD|  ← IMPLEMENTED (Person 1)
                +-----+-----+
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       Agent A     Agent B     Agent C  ← FUTURE (Person 2)
          |           |           |
          +-----------+-----------+
                      |
                   Scheduler      ← IMPLEMENTED (Person 3)
                      |
             +--------+--------+
             |                 |
         Consensus          Deadlock
                                 |
                          Counterfactual  ← IMPLEMENTED (Person 3)
                                 |
                               UI          ← FUTURE (Person 4)
```

## Repository Structure
```
AI_Project/
├── README.md
├── PROJECT.md
├── ARCHITECTURE.md
├── TEAM.md
├── TASKS.md
├── FLASH_TALK.md
├── RESEARCH.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── docs/
│   ├── proposal_summary.md
│   ├── blackboard_api.md
│   ├── shared_contract.md
│   ├── decisions.md
│   ├── integration_guide.md
│   ├── scheduler_api.md
│   └── counterfactual_api.md
├── src/
│   └── ai_project/
│       ├── __init__.py
│       ├── blackboard/
│       │   ├── __init__.py
│       │   ├── board.py
│       │   ├── models.py
│       │   ├── history.py
│       │   └── exceptions.py
│       ├── protocol/
│       │   ├── __init__.py
│       │   ├── pxp.py
│       │   └── validator.py
│       ├── scheduler/          # Person 3: scheduler, policies, consensus, trace, mock agents
│       ├── deadlock/           # Person 3: stance analysis + deadlock detection
│       └── counterfactual/     # Person 3: branching, replay, comparison
├── examples/
│   ├── blackboard_demo.py
│   └── scheduler_demo.py
├── tests/
│   ├── test_blackboard.py
│   ├── test_pxp.py
│   ├── test_history.py
│   ├── test_snapshot.py
│   ├── test_thread_safety.py
│   ├── scheduler/
│   ├── deadlock/
│   └── counterfactual/
├── experiments/
│   └── README.md
└── prompts/
    └── README.md
```

## Installation
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e .
pip install -e ".[dev]"
```

## Running Tests
```bash
pytest tests/ -v
```

## Running Demo
```bash
python examples/blackboard_demo.py
python examples/scheduler_demo.py    # scheduler -> deadlock -> counterfactual -> consensus
```

## Person 1 Responsibilities (This Branch)
- Blackboard core implementation
- PXP message protocol and validation
- Thread-safe state management
- History/event logging
- Snapshot/serialization support
- Unit tests and demo

## Future Teammates Will Build
- **Person 2**: PEX agents with LLM integration that produce PXP messages
- **Person 3**: Scheduler with deadlock detection and counterfactual reasoning engine
- **Person 4**: Real-time visualization UI and evaluation/experiment framework