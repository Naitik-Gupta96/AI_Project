# Intelligible Blackboard Architecture with Counterfactual Agents

Three language-model agents solve a task through a shared, structured blackboard instead of
passing text down a chain. Every message follows the Two-Way Intelligibility Protocol (PXP) of
Baskar et al.:
- a prediction;
- an explanation;
- a tag (`INIT`, `RATIFY`, `REVISE`, `REFUTE`, `REJECT`) that the protocol derives from the
  sender's judgments of the message it answers.

When the board deadlocks, agents with counterfactual capability replay the session in an
isolated sandbox with alternatives to their own past messages. Each alternative is credited by
how much closer it brings the team to consensus, and the best one is applied to the live board:
- a lesson added to the agent's prompt;
- a revised position;
- a lower voting weight.

An ablation varies how many of the three agents have that capability (0, 33, 67, 100%) over 500
tasks from MSCoRe, KramaBench and MedAgentBench.

## What is in the box

| Spec deliverable | Where |
|---|---|
| **A.** Thread-safe blackboard, JSON/Redis persistence, PXP grammar and state machine, event-driven priority scheduler | `src/ai_project/blackboard`, `protocol`, `scheduler`, `deadlock` |
| **B.** Local 7B model broker (vLLM, Ollama, transformers), prompt matrix with JSON schemas, retrospective sandbox with credit assignment | `src/ai_project/llm`, `agents`, `counterfactual` |
| **C.** FastAPI/WebSocket server and React/D3 UI: reasoning graph, counterfactual split panel, step-through inspector, analytics | `src/ai_project/server`, `web/` |
| **D.** Loaders for KramaBench, MSCoRe, MedAgentBench; token and convergence tracking; ablation runner; plots | `src/ai_project/benchmarks`, `experiments` |
| Strong / Ultra-Strong intelligibility classification | `src/ai_project/protocol/intelligibility.py` |

## Try it (no GPU, no model)

Requires Python 3.11+ and Node 20+.

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows   (source .venv/bin/activate elsewhere)
pip install -e ".[dev]"
python -m pytest                       # the test suite

bb run --cf analyst                    # a session in the terminal: deadlock, sandbox, recovery
bb ablate experiments/configs/mock-synthetic.toml   # the 4 x 500 design on the mock, ~10 s

cd web && npm install && npm run build && cd ..
bb serve                               # http://127.0.0.1:8765
```

In the UI, press **Run session** with the analyst counterfactual-capable:
1. Watch the board deadlock.
2. Watch the sandbox branches fill in.
3. See the intervention applied and the team reach consensus.
4. Drag the scrubber to step back through any of it.

Without a model, the agents run on a deterministic mock whose rules are documented in
`llm/providers/mock.py`. Its numbers say nothing about language models.

## Real runs

The model is Qwen2.5-7B-Instruct: on an NVIDIA GPU through vLLM, on Apple Silicon through
Ollama. [scripts/gpu_runbook.md](scripts/gpu_runbook.md) has both paths step by step. In short
(NVIDIA):

```bash
docker compose up -d vllm fhir && docker compose build sandbox
bb fetch mscore kramabench medagentbench          # plus MedAgentBench's refsol.py, see runbook
bb ablate experiments/configs/smoke.toml
bb ablate experiments/configs/ablation.toml       # 2,000 sessions, resumable
bb check  runs/experiments/ablation-qwen2.5-7b    # health checks: crashes, grader errors, tokens
bb report runs/experiments/ablation-qwen2.5-7b    # summary, figures, LaTeX table
```

With limited compute time, `experiments/configs/ablation-quick-ollama.toml` runs the same design
on a Mac at reduced scale: 25 tasks per group (100 sessions) instead of 500.

## Documentation

| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | the four layers and how a session runs |
| [docs/pxp.md](docs/pxp.md) | the protocol, the grammar, and every adaptation for more than two agents |
| [docs/counterfactual.md](docs/counterfactual.md) | reflection, sandbox, credit, intervention, with a worked example |
| [docs/experiments.md](docs/experiments.md) | design, benchmarks, metrics, limitations |
| [docs/api.md](docs/api.md) | REST and WebSocket messages |
| [docs/team.md](docs/team.md) | the three roles, what each owns, milestones, workflow |
| [web/README.md](web/README.md) | the UI |
| [paper/](paper/) | the project report (course template) and its PDF |

## Layout

```
src/ai_project/
  protocol/        PXP messages, grammar (Algorithm 1), intelligibility
  blackboard/      event-sourced board, stores
  scheduler/       scheduler, arbiter, consensus
  deadlock/        deadlock rules
  agents/          agent pipeline, AGENT procedure, team builder, tools
  llm/             providers, broker, cache, prompt matrix and templates, parser
  counterfactual/  sandbox replay, credit assignment, intervention
  benchmarks/      synthetic, MSCoRe, KramaBench, MedAgentBench, scoring, fetch
  experiments/     ablation runner, analysis, plots
  server/          FastAPI app and live sessions
  session.py       one session end to end
  cli.py           bb run | serve | fetch | ablate | check | report
web/               React + TypeScript + D3 UI
experiments/configs/   ablation(-ollama|-quick-ollama).toml, smoke(-ollama).toml, mock-synthetic.toml
docker-compose.yml, docker/   vLLM, FHIR server, Redis, code sandbox image
scripts/           gpu_runbook.md, export_ui_fixture.py
tests/             mirrors src/
```

## Status

The code for all four deliverables is complete and tested, and CI runs on every pull request.

**Results.** `ablation-quick-ollama-qwen2.5-7b` is a reduced-scale run of the ablation: 25 tasks
per group, 100 sessions (the brief specifies 500 per group), with Qwen2.5-7B-Instruct 4-bit through
Ollama on a Mac. Every session reached consensus without a deadlock, so no counterfactual
intervention ran and the four groups scored the same: convergence success 0.16 overall
(MedAgentBench 0.30, KramaBench 0.20, MSCoRe 0.00). Details are in
[docs/experiments.md](docs/experiments.md#results) and
[results/ablation-quick-ollama-qwen2.5-7b/](results/ablation-quick-ollama-qwen2.5-7b/). The full
design (`ablation.toml`, 2,000 sessions) is ready to run when compute allows. The state at the
flash talk is tagged `v0.1-flash-talk`.
