# Intelligible Blackboard Architecture with Counterfactual Agents

A research prototype. Three role-based agents (analyst, critic, specialist)
coordinate only through a shared **Blackboard** using structured **PXP**
messages. A **Scheduler** decides who acts and detects **consensus** or
**deadlock**. After a deadlock, **counterfactual-capable** agents revise one
of their own past messages in hindsight, and the **counterfactual engine**
branches history at that message and replays the future to see whether the
team would have agreed.

```
 DecisionTask ──► Blackboard (state + append-only PXP history + snapshots)
                     ▲   │
     PXP messages    │   │ context
                     │   ▼
        analyst · critic · specialist ── LLMProvider (deterministic mock | optional Ollama)
                     ▲
                     │ who acts next
                 Scheduler ── consensus check ── deadlock detector
                                                      │ DEADLOCK
                                                      ▼
                         counterfactual-capable agents reflect on their own messages
                                                      │ intervention
                                                      ▼
                       counterfactual engine: branch at step k → replay → compare
                                                      │
                               UI (Flash Talk · Run Explorer · Evaluation) · pilot experiment
```

## Project status

This table is the single source of truth for status; other documents link here.

| Component | Status | Evidence |
|---|---|---|
| Blackboard, PXP protocol, validation, history, snapshots | **Implemented** | `src/ai_project/blackboard`, `protocol`; unit + thread-safety tests |
| Role agents (analyst, critic, specialist) | **Implemented, deterministic mock** | `agents/`, `llm/mock.py`: explicit role rules, no language model |
| Provider abstraction (one decision pipeline) | **Implemented** | `llm/base.py`; every decision goes context → prompt → provider → parser |
| Local model provider (Ollama) | **Implemented, optional, lightly tried** | `llm/ollama.py`; tested against a stubbed HTTP layer; one manual run with `qwen3:4b` (see [FLASH_TALK.md](FLASH_TALK.md)); not used for any reported number |
| Scheduler, policies, consensus, deadlock detection | **Implemented** | `scheduler/`, `deadlock/`; tests incl. edge cases |
| Counterfactual branching, replay, comparison | **Implemented** | `counterfactual/engine.py`; isolation and replay tests |
| Counterfactual agents (reflection → intervention → replay) | **Implemented** | `counterfactual/resolver.py`, `BaseAgent.reflect` |
| End-to-end Flash Talk scenario | **Demonstrated** (deterministic mock) | UI Flash Talk tab, `examples/flash_talk_demo.py` |
| Streamlit UI | **Implemented** | `frontend/app.py` on the typed adapter in `ui/` |
| Pilot experiment | **End-to-end pilot** on synthetic tasks with deterministic mock agents | `experiment.py`, [docs/evaluation.md](docs/evaluation.md) |
| Experiments with LLM agents | **Planned** | runner supports `--provider ollama`; no results yet |
| Benchmarks (KramaBench, MSCoRe, MedAgentBench) | **Planned**, not integrated | proposal only |
| Human evaluation of intelligibility | **Planned** | not measured |

Vocabulary used everywhere: **DETERMINISTIC MOCK** (rule-based agents, no
model), **LIVE / LOCAL MODEL** (Ollama), **END-TO-END PILOT** (the real
system run over generated tasks). No result in this repository comes from a
language model or a benchmark.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate elsewhere)
pip install -e ".[dev]"           # core + UI + pytest/ruff

python -m pytest                                  # 265 tests, ~10 s
python examples/flash_talk_demo.py                # end-to-end demo in the terminal
python -m streamlit run frontend/app.py           # the UI
python experiments/run_experiment.py              # pilot: 800 trials, ~3 s
python experiments/analyze_results.py             # summary tables + CSV
```

The core package has no third-party dependencies (`pip install -e .`); `[ui]`
adds Streamlit and pandas, `[dev]` adds the UI plus pytest and ruff. No
internet access, API key or model is needed for anything above.

Optional, with a local [Ollama](https://ollama.com) server:

```bash
ollama pull qwen3:4b
python examples/flash_talk_demo.py --provider ollama --model qwen3:4b   # minutes, not seconds
```

## Other demos

```bash
python examples/agents_demo.py       # inside one agent decision: context, prompt, raw output, message
python examples/scheduler_demo.py    # scheduler + engine with scripted test-double agents
python examples/blackboard_demo.py   # Blackboard API: publish, history, snapshot isolation
```

## Repository layout

```
src/ai_project/
  protocol/        PXP message, tags, validator
  blackboard/      Blackboard, state, history, snapshots
  tasks.py         DecisionTask (options + role-partitioned evidence), Flash Talk task, generator
  agents/          AgentContext/AgentDecision, BaseAgent pipeline, the three roles
  llm/             provider interface, deterministic mock (role rules), Ollama, parser, prompts/
  scheduler/       Scheduler, policies, registry, consensus, trace (+ test-double agents)
  deadlock/        stance analysis, deadlock rules
  counterfactual/  engine (branch/replay/compare), resolver (counterfactual agents)
  pipeline.py      run_task: the one end-to-end path
  experiment.py    pilot runner and descriptive analysis
  ui/              typed UI models + adapter
frontend/app.py    Streamlit UI
examples/          CLI demos
experiments/       run_experiment.py, analyze_results.py, results/ (generated, git-ignored)
tests/             unit, integration, determinism, UI tests
docs/              API references, decisions, evaluation
```

## Documentation

- [FLASH_TALK.md](FLASH_TALK.md): presentation guide (demo flow, safe claims, backup plan)
- [ARCHITECTURE.md](ARCHITECTURE.md): components and data flow
- [RESEARCH.md](RESEARCH.md): research question, hypotheses, what is and is not tested
- [docs/decisions.md](docs/decisions.md): engineering decision records
- [docs/evaluation.md](docs/evaluation.md): pilot methodology and results
- API: [blackboard](docs/blackboard_api.md) · [agents](docs/agents_api.md) ·
  [scheduler](docs/scheduler_api.md) · [counterfactual](docs/counterfactual_api.md) ·
  [UI](docs/ui_api.md) · [contract between layers](docs/shared_contract.md)
- [TEAM.md](TEAM.md), [TASKS.md](TASKS.md), [PROJECT.md](PROJECT.md), [hardening report](docs/hardening_report.md)
