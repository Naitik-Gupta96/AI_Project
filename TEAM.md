# Team Roles

Current status of every component: [README.md#project-status](README.md#project-status).

## Person 1: Blackboard and PXP protocol

- `src/ai_project/protocol/`: PXP message, tags, validator
- `src/ai_project/blackboard/`: Blackboard, history, snapshots, serialization, thread safety
- Tests: `tests/test_blackboard.py`, `test_pxp.py`, `test_history.py`, `test_snapshot.py`, `test_thread_safety.py`
- Docs: [docs/blackboard_api.md](docs/blackboard_api.md), decisions 1-11 in [docs/decisions.md](docs/decisions.md)

## Person 2: Agents and providers

- `src/ai_project/agents/`: agent contract, `BaseAgent` decision pipeline, analyst/critic/specialist
- `src/ai_project/llm/`: provider interface, deterministic mock (role rules), Ollama provider, parser, prompt templates
- `src/ai_project/tasks.py`: decision tasks with role-partitioned evidence
- Tests: `tests/agents/`, `tests/llm/`, `tests/test_tasks.py`
- Docs: [docs/agents_api.md](docs/agents_api.md)

## Person 3: Scheduler, deadlock detection, counterfactual engine

- `src/ai_project/scheduler/`: Scheduler, policies, registry, consensus, trace, test-double agents
- `src/ai_project/deadlock/`: stance analysis and deadlock rules
- `src/ai_project/counterfactual/`: branching, replay, comparison, counterfactual resolver
- Tests: `tests/scheduler/`, `tests/deadlock/`, `tests/counterfactual/`
- Docs: [docs/scheduler_api.md](docs/scheduler_api.md), [docs/counterfactual_api.md](docs/counterfactual_api.md)

## Person 4: UI and evaluation

- `frontend/app.py`, `src/ai_project/ui/`: Streamlit UI and the typed adapter it renders
- `src/ai_project/experiment.py`, `experiments/`: end-to-end pilot runner and analysis
- Tests: `tests/ui/`, `tests/experiment/`
- Docs: [docs/ui_api.md](docs/ui_api.md), [docs/evaluation.md](docs/evaluation.md)

## Shared

- `src/ai_project/pipeline.py`: the end-to-end path every demo and experiment uses
- `tests/test_pipeline.py`: integration and cross-process determinism
- [FLASH_TALK.md](FLASH_TALK.md): presentation guide

## Conventions

- Work on feature branches; open a pull request into the integration branch.
- `python -m pytest` must pass before merging.
- Status claims live in the README table only; update it with the code.
