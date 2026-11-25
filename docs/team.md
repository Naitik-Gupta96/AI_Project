# Team roles and milestones

The spec splits the work into three roles. This is where each role's deliverables live in the
code, so each person knows which modules, tests and docs they own.

## Student 1: infrastructure and protocol control

| Deliverable | Code | Tests |
|---|---|---|
| Thread-safe Blackboard repository (event log, versioned commits, subscribers) | `src/ai_project/blackboard/` | `tests/blackboard/` |
| JSON / Redis-backed stores | `blackboard/store.py` | `tests/blackboard/test_store.py` |
| PXP tag validator and state machine | `protocol/grammar.py`, `protocol/pxp.py`, `blackboard/models.py` (status transitions) | `tests/protocol/` |
| Intelligibility classification | `protocol/intelligibility.py` | `tests/protocol/test_intelligibility.py` |
| Event-driven scheduler, priority arbiter, consensus, deadlock | `scheduler/`, `deadlock/` | `tests/scheduler/`, `tests/deadlock/` |

Docs: [pxp.md](pxp.md), [architecture.md](architecture.md).

## Student 2: agent engineering and counterfactual architecture

| Deliverable | Code | Tests |
|---|---|---|
| Model wrappers for local 7B models (vLLM, Ollama, transformers), broker, cache | `llm/providers/`, `llm/broker.py`, `llm/cache.py`, `llm/factory.py` | `tests/llm/` |
| Prompt library: personas per domain, JSON schemas | `llm/prompts/` (`matrix.json`, `personas/`, `schemas/`), `llm/prompts.py` | `tests/agents/test_agent.py` |
| Agent pipeline and the PXP AGENT procedure | `agents/` | `tests/agents/` |
| Retrospective sandbox, credit assignment, live intervention | `counterfactual/` | `tests/counterfactual/` |

Docs: [counterfactual.md](counterfactual.md).

## Student 3: front end and benchmarking

| Deliverable | Code | Tests |
|---|---|---|
| WebSocket server | `server/` | `tests/server/` |
| React/D3 UI: reasoning graph, split counterfactual panel, inspector, analytics | `web/` | `web/src/board.test.ts` |
| Ingest for KramaBench, MSCoRe, MedAgentBench; tools | `benchmarks/`, `agents/tools.py` | `tests/benchmarks/` |
| Token tracking, convergence metrics, ablation runner, plots | `llm/usage.py`, `experiments/` | `tests/experiments/` |

Docs: [experiments.md](experiments.md), [api.md](api.md), [../web/README.md](../web/README.md),
[../scripts/gpu_runbook.md](../scripts/gpu_runbook.md).

## Milestones

| Milestone (spec) | State |
|---|---|
| 1. Blackboard and scheduler processing RATIFY / REJECT state changes | done |
| 2. Local 7B models connected, prompt library, WebSocket link to the UI | done |
| 3. Counterfactual module verified on a synthetic deadlock; graph view of the simulation | done (`architecture` task; see [counterfactual.md](counterfactual.md)) |
| 4. Benchmark batches, token-efficiency charts, paper | batches done at reduced scale (25 tasks per group, [results](../results/ablation-quick-ollama-qwen2.5-7b/), [experiments.md](experiments.md#results)); report written ([paper/](../paper/)) |

## How we work

- `main` is the default branch and always passes CI (ruff, pytest on Python 3.11 and 3.13, the
  web tests and build).
- Work happens on short branches (`feat/…`, `fix/…`, `docs/…`), merged with a pull request once
  CI is green. Delete the branch after merging.
- After a merge, everyone runs `git switch main && git pull && git fetch --prune`.
- The state at the flash talk is tagged `v0.1-flash-talk`.
