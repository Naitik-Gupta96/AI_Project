# Intelligible Blackboard Architecture with Counterfactual Agents

Three or more agents solve a task through a shared, structured blackboard instead of passing
text down a chain. Every message follows the Two-Way Intelligibility Protocol (PXP) of
Baskar et al.: a prediction, an explanation, and a tag (`INIT`, `RATIFY`, `REVISE`, `REFUTE`,
`REJECT`) that the protocol derives from the sender's judgments. When the board deadlocks,
agents with counterfactual capability look back at their own past messages. Each replays the
session in an isolated sandbox with an alternative message, credits that message by how much
closer the team came to consensus, and applies the best change to the live board: a lesson in
its prompt, a revised position, a lower voting weight.

## Layout

```
src/ai_project/
  protocol/        PXP messages, the Algorithm 1 grammar, intelligibility levels
  blackboard/      event-sourced board, optimistic versioning, memory/JSON/Redis stores
  scheduler/       event-driven scheduler, priority arbiter, weighted consensus
  deadlock/        deadlock rules (REJECT, REFUTE loop, stagnation)
  agents/          agent pipeline (context -> prompt -> provider -> parser -> grammar), teams
  llm/             provider interface, deterministic mock, prompt matrix, parser, usage meter
  counterfactual/  retrospective sandbox, credit assignment, live-board intervention
  benchmarks/      task model and loaders (synthetic so far)
  session.py       one session end to end
tests/             mirrors src/
docs/pxp.md        how PXP is applied to a multi-agent blackboard
```

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate elsewhere)
pip install -e ".[dev]"
python -m pytest
```

Run the demo task in Python:

```python
from ai_project.agents import build_team
from ai_project.benchmarks import SyntheticBenchmark, architecture_task
from ai_project.llm.providers.mock import MockLLMProvider
from ai_project.session import run_session

task = architecture_task()
result = run_session(task, build_team(task, MockLLMProvider()), cf_agents=["analyst"],
                     benchmark=SyntheticBenchmark())
print(result.status, result.final_prediction)   # CONSENSUS Option B
```

Without `cf_agents` the same task ends in `DEADLOCK`.

## Status

| Deliverable (spec) | State |
|---|---|
| A. Thread-safe blackboard, PXP grammar, priority scheduler | done |
| B. Counterfactual sandbox and credit assignment | done |
| B. Local 7B model broker, prompt matrix for all benchmarks | in progress |
| C. FastAPI/WebSocket server and React/D3 UI | in progress |
| D. KramaBench, MSCoRe, MedAgentBench loaders; ablation runner; plots | in progress |
