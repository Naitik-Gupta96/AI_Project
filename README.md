# Intelligible Blackboard Architecture with Counterfactual Agents

Three language-model agents solve a task through a shared, structured **blackboard** instead of
passing text down a chain. Every message follows the **Two-Way Intelligibility Protocol (PXP)** of
Baskar et al. It is a prediction, an explanation, and a tag (`INIT`, `RATIFY`, `REVISE`, `REFUTE`,
`REJECT`) derived from the sender's judgments of the message it answers.

When the board **deadlocks**, agents with **counterfactual capability** replay the session in an
isolated sandbox with alternatives to their own past messages. Each alternative is credited by how
much closer it brings the team to consensus, and the best one is applied to the live board:
- a lesson added to the agent's prompt;
- a revised position;
- a lower voting weight.

An ablation varies how many of the three agents have this capability (0, 33, 67 and 100%) on
MSCoRe, KramaBench and MedAgentBench.

CS F407 Artificial Intelligence, BITS Pilani K.K. Birla Goa Campus, AY 2026–27 Semester I. Team
404byArcticDonkeys: Naitik Gupta, Malay Neema, Mayank Sharma, Yash Singh.
**Report:** [paper/project_report.pdf](paper/project_report.pdf).

---

## Results at a glance

Two experiments, reported at the scale at which they were actually run.

**1. Language-model run.**
- **Setup:** Qwen2.5-7B-Instruct, 4-bit (Q4_K_M), through Ollama 0.40.3 on an Apple M5 laptop with
  16 GB, run on 24 Nov 2026 in 37 minutes.
- **Scale:** reduced to 25 tasks per group, 100 sessions in all. The brief specifies 500 per group;
  no 24 GB GPU was available.
- **Files:** [results/ablation-quick-ollama-qwen2.5-7b/](results/ablation-quick-ollama-qwen2.5-7b/).

| Benchmark | Tasks per group | Convergence success, 95% CI (identical in all four groups) |
|---|---|---|
| MSCoRe | 10 | 0.00 [0.00, 0.28] |
| KramaBench | 5 | 0.20 [0.04, 0.62] |
| MedAgentBench | 10 | 0.30 [0.11, 0.60] |
| All | 25 | 0.16 [0.06, 0.35] |

Every session reached consensus in four messages (an `INIT`, then two `RATIFY`s), so no session
deadlocked and no counterfactual intervention ran. The four groups gave the same answer on every
task, and every McNemar test has p = 1. The run shows the pipeline working end to end on real
benchmarks. It cannot show an effect of counterfactual agents, because the situation they act on
never arose.

**2. Pipeline check with scripted agents.** The full 4 × 500 design on synthetic decision tasks,
in which each role privately knows something that rules options out. The agents follow
deterministic rules (no language model), so this measures the mechanism, not LLM behaviour.

| Counterfactual-capable | 0% | 33% | 67% | 100% |
|---|---|---|---|---|
| Sessions that deadlocked | 0.51 | 0.51 | 0.51 | 0.51 |
| Deadlocks recovered | 0.000 | 0.024 | 0.075 | 0.106 |
| Convergence success | 0.490 | 0.502 | 0.528 | 0.544 |
| Model calls per session | 4.27 | 6.67 | 9.10 | 11.85 |
| McNemar p vs 0% | – | 0.031 | 4 × 10⁻⁶ | 2 × 10⁻⁸ |

Here counterfactual agents recover deadlocks and raise convergence success, at about 2.8 times the
model calls. In 134 of the 255 deadlocked tasks no option is feasible, so deadlock is the correct
outcome there.

---

## How it works

```
 UI layer        web/ (React + D3)  ⇄  server/ (FastAPI, one WebSocket per session)
                        ▲ board events, sandbox progress        │ pause / step / stop
 Control layer   Scheduler: priority arbiter → who acts next; consensus and deadlock checks
                        ▲ events                                │ act(board) → message
 Communication   Blackboard: event-sourced state, PXP grammar checked on every commit,
 layer           versioned writes, stores in memory / JSON lines / Redis
                        ▲ read-only snapshot                    │ lesson, position, weight
 Reasoning       Agents (persona + JSON schema → model → PXP message), counterfactual resolver
 layer           (reflect → sandbox replay per alternative → credit → apply), model providers
```

- **PXP tags.** A message compares the message it answers, `(y', e')`, with the sender's own
  previous position, `(y'', e'')`. Here MATCH asks whether the predictions match and AGREE whether
  the explanations agree.

  | MATCH | AGREE | Tag |
  |---|---|---|
  | yes | yes | `RATIFY` |
  | exactly one of them | | `REVISE` if the sender changed its position, otherwise `REFUTE` |
  | no | no | `REJECT` from message 4 on, `REVISE`/`REFUTE` before |

  The model supplies the judgments, and code computes the tag. The blackboard's grammar rejects
  any message whose tag does not follow; it never repairs one. See [docs/pxp.md](docs/pxp.md).
- **Scheduler.** It is event-driven: every change to the board triggers a round.
  - **Ranking.** A priority arbiter ranks the agents: +10 for a pending intervention, +3 if the
    agent has not spoken, +2 for news since its last post, +1 if its last tag was not `RATIFY`.
  - **Consensus.** At least two agents ratify the same message, with at least 75% of the voting
    weight.
  - **Deadlock.** A `REJECT`, three `REFUTE`s in a row, or six messages without a new prediction.
- **Counterfactual credit.** On a deadlock, each capable agent proposes up to three alternatives
  for each of its last three messages, and replays the rest of the session from each in a sandbox.
  - **Credit:** consensus proximity at the end of the replay, minus the proximity on the live board
    at the deadlock.
  - **Applied:** the best alternative with positive credit. Its lesson joins the agent's prompt,
    the agent's position is revised, and its weight becomes `max(0.25, w·(1 − 0.5·credit))`.

  See [docs/counterfactual.md](docs/counterfactual.md) for a worked example.
- **Intelligibility.** Every session is classified One-Way, Strong or Ultra-Strong following
  Mestha et al., Definitions 1–2.

## Spec deliverables

| Deliverable in the brief | Where |
|---|---|
| **A.** Thread-safe blackboard with JSON/Redis persistence, PXP grammar and state machine, event-driven priority scheduler | `src/ai_project/blackboard`, `protocol`, `scheduler`, `deadlock` |
| **B.** Local 7B model wrappers (vLLM, Ollama, transformers), prompt matrix with JSON schemas, retrospective sandbox with credit assignment | `src/ai_project/llm`, `agents`, `counterfactual` |
| **C.** FastAPI/WebSocket server; React/D3 UI with the reasoning graph, split counterfactual panel, step-through inspector and red alerts for cascading `REJECT`s | `src/ai_project/server`, `web/` |
| **D.** Loaders for KramaBench, MSCoRe and MedAgentBench; token, cycle and convergence tracking; ablation runner; plots | `src/ai_project/benchmarks`, `experiments`, `experiments/configs` |
| Strong / Ultra-Strong intelligibility classification | `src/ai_project/protocol/intelligibility.py` |
| Ablation over 0 / 33 / 67 / 100% counterfactual-capable agents | `experiments/configs/*.toml`, `src/ai_project/experiments/runner.py` |

---

## Reproducing the project

There are four levels. Levels 1 and 2 need no model, no GPU and no data download, and take a few
minutes. Level 3 reproduces the reported language-model run. Level 4 is the full 2,000-session
design.

| Level | What it shows | Needs | Time |
|---|---|---|---|
| 1 | Tests, a deadlock fixed by the sandbox, the pipeline check | Python 3.11+ | 2–3 min |
| 2 | The live web UI and the results dashboards | Level 1, plus Node 20+ | 3 min |
| 3 | The reported Qwen2.5-7B run (25 tasks per group) | Ollama, Docker, about 10 GB free disk | about 1.5 h, 40 min of it the run |
| 4 | The full design (500 tasks per group) | an NVIDIA GPU with 24 GB, Docker | several hours |

### Install

Run these from the repository root.

```bash
git clone https://github.com/Naitik-Gupta96/AI_Project.git
cd AI_Project
python -m venv .venv
source .venv/bin/activate              # Windows (cmd or PowerShell): .venv\Scripts\activate
pip install -e ".[dev,bench,plots]"
```

This installs the `bb` command. If your shell cannot find `bb` (common on Windows when the
environment is not activated), use `python -m ai_project.cli` in its place. For example,
`python -m ai_project.cli run --cf analyst`.

### Level 1: tests and the mechanism (no model)

```bash
python -m pytest                       # expected: 355 passed
bb run --cf analyst                    # one session in the terminal
bb run --cf critic                     # the same session with only the critic capable
bb ablate experiments/configs/mock-synthetic.toml   # the 4 × 500 pipeline check, about 20 s
```

What to expect:
- **`bb run --cf analyst`:**
  - The analyst opens with Option A, the critic refutes, the specialist ratifies B, and the analyst
    rejects. This is the deadlock.
  - The sandbox tries 2 alternatives. Changing the analyst's opening to B earns credit +0.67.
  - It is applied (weight 1.00 → 0.67), and the session ends `status CONSENSUS answer Option B`.
- **`bb run --cf critic`:** nothing the critic changes helps, and the session ends
  `status DEADLOCK`.
- **`bb ablate … mock-synthetic.toml`:**
  - It prints the pipeline-check table above (`cf0 0.49 … cf100 0.54`) and the McNemar tests.
  - It writes `runs/experiments/mock-synthetic/`: `summary.json`, `groups.csv`, `trials.jsonl`,
    `figures/` and `tables/`.

### Level 2: the web UI (no model)

```bash
cd web && npm ci && npm run build && cd ..
bb serve                               # then open http://127.0.0.1:8765
```

- **Sessions tab.** The start page shows the task and what each agent privately knows. With the
  analyst selected (the default), press **Run session**. Then:
  - **Story strip:** it lights up step by step (opening, discussion, deadlock in red, sandbox
    replay, fix applied, consensus in green).
  - **Graph and replay panel:** the reasoning graph grows around the task, and the counterfactual
    replay panel beside it shows the sandbox branches with their credit and the change applied.
  - **Scrubber:** under the graph, step back and forth through every event (← →), or press
    **Replay**.
  - **Contrast:** press **New session**, select only the critic, and run again. It stays
    deadlocked.
- **Analytics tab.** It shows every run under the experiments folder. `bb serve` alone shows the
  pipeline check from Level 1. To see the committed language-model results, start it with
  `bb serve --experiments results`.
- **Light or dark mode.** Use the button in the top bar.

For development, `cd web && npm run dev` serves the UI on http://127.0.0.1:5173 with hot reload,
proxied to `bb serve`. See [web/README.md](web/README.md).

### Level 3: the reported language-model run

The run behind `results/ablation-quick-ollama-qwen2.5-7b/` used an Apple M5 laptop. Any machine
that can run Ollama and Docker works.

1. **Install the services.** Install [Ollama](https://ollama.com) and Docker Desktop. On Apple
   Silicon, also turn on "Use Rosetta for x86/amd64 emulation" in Docker Desktop, because the
   MedAgentBench FHIR image is x86 only.
2. **Start the model server** in its own terminal (quit the Ollama app first), then pull the model:
   ```bash
   OLLAMA_NUM_PARALLEL=4 OLLAMA_MAX_LOADED_MODELS=1 ollama serve
   ollama pull qwen2.5:7b-instruct                       # about 4.7 GB
   ```
   If Ollama listens somewhere other than `127.0.0.1:11434`, set `OLLAMA_HOST`.
3. **Start the FHIR server and build the sandbox image** for KramaBench's `python` tool:
   ```bash
   docker compose up -d fhir
   docker compose build sandbox
   curl -s http://127.0.0.1:8080/fhir/metadata | head -c 200   # should print FHIR metadata
   ```
4. **Get the data,** about 1 GB, written to `data/`:
   ```bash
   bb fetch mscore kramabench medagentbench
   ```
   MedAgentBench's official grader, `refsol.py`, is distributed separately. Download it from the
   link in the [MedAgentBench README](https://github.com/stanfordmlgroup/MedAgentBench) and save
   it as `data/medagentbench/refsol.py`.
5. **Run, check and report:**
   ```bash
   bb ablate experiments/configs/ablation-quick-ollama.toml      # about 40 min; resumable
   bb check  runs/experiments/ablation-quick-ollama-qwen2.5-7b   # expected: OK
   bb report runs/experiments/ablation-quick-ollama-qwen2.5-7b   # summary.json, groups.csv, figures/, tables/
   ```
   - **Resuming.** If the run stops, run the same command again: finished trials are kept.
   - **Comparing.** Compare `summary.json` with
     `results/ablation-quick-ollama-qwen2.5-7b/summary.json`. Ollama does not guarantee
     bit-identical output at temperature 0, so single answers can differ.
     `results/…/trials.jsonl.gz` holds every recorded trial.

### Level 4: the full design on a GPU

`experiments/configs/ablation.toml` runs the specified design: 4 groups × 500 tasks (300 MSCoRe,
100 KramaBench and 100 MedAgentBench), 2,000 sessions. It serves Qwen2.5-7B-Instruct in bf16 through
vLLM. The bf16 weights alone take 15.2 GB, so this needs a 24 GB NVIDIA GPU. Then run:

```bash
docker compose up -d vllm fhir && docker compose build sandbox
bb fetch mscore kramabench medagentbench          # plus refsol.py, as in Level 3
bb ablate experiments/configs/smoke.toml          # 20 sessions first; bb check must print OK
bb ablate experiments/configs/ablation.toml       # 2,000 sessions, resumable
bb check  runs/experiments/ablation-qwen2.5-7b
bb report runs/experiments/ablation-qwen2.5-7b
```

[scripts/gpu_runbook.md](scripts/gpu_runbook.md) covers every hardware path step by step:
- bf16 on 24 GB GPUs;
- the AWQ 4-bit build on 12–23 GB GPUs;
- Ollama on Apple Silicon;
- what `bb check` looks for.

---

## Command reference

| Command | Does |
|---|---|
| `bb run [--cf AGENT …] [--provider SPEC] [--task-id ID]` | Runs one session and prints the transcript. The default is the synthetic `architecture` task with the mock. |
| `bb serve [--port 8765] [--runs runs] [--experiments DIR]` | Starts the API and the web UI. |
| `bb fetch mscore kramabench medagentbench` | Downloads benchmark data into `data/` (or `$BB_DATA_DIR`). |
| `bb ablate CONFIG [--out DIR] [--restart]` | Runs an experiment and resumes unfinished ones. Results go to `runs/experiments/<name>/`. |
| `bb check RUN_DIR` | Runs health checks (crashed trials, failed sessions, grader errors, missing token counts) and prints OK or the problems. |
| `bb report RUN_DIR` | Writes `summary.json`, `groups.csv`, the figures and the LaTeX table. |

Provider specs are:
- `mock`;
- `ollama:<model>`;
- `vllm:<model>`;
- `openai:<model>@<base_url>`;
- `hf:<model>`.

## Experiment configurations (`experiments/configs/`)

| File | Design | Model |
|---|---|---|
| `mock-synthetic.toml` | 4 × 500 synthetic tasks | scripted agents (no model) |
| `ablation-quick-ollama.toml` | 4 × 25 (10 MSCoRe, 5 KramaBench, 10 MedAgentBench), **the reported run** | Qwen2.5-7B via Ollama |
| `ablation.toml` | 4 × 500 (300 / 100 / 100), the full design | Qwen2.5-7B bf16 via vLLM |
| `ablation-ollama.toml` | 4 × 500, the same design | Qwen2.5-7B via Ollama |
| `smoke.toml`, `smoke-ollama.toml` | 2 groups × 10 tasks, a check before a long run | vLLM / Ollama |

Settings shared by every design:
- **Seed and decoding:** seed 0, temperature 0.
- **Session:** a 12-message budget, `REJECT` allowed from message 4, a consensus threshold of 0.75,
  at most 2 interventions per session, and up to 4 tool calls per turn.

## Result files

`results/ablation-quick-ollama-qwen2.5-7b/` holds:

| File | Contents |
|---|---|
| `meta.json` | the full configuration, the model and provider settings, the commit of the code and the start time |
| `summary.json` | every metric per group and benchmark, with confidence intervals, plus the McNemar tests |
| `groups.csv` | the same per-group metrics as a table |
| `trials.jsonl.gz` | one line per session: answer, score, status, tags, intelligibility, tokens and interventions |
| `health.txt` | the `bb check` output |
| `figures/`, `tables/` | the plots and the LaTeX table from `bb report` |

## Troubleshooting

| Problem | Fix |
|---|---|
| `bb` is not recognized (Windows) | Activate the environment (`.venv\Scripts\activate`) or use `python -m ai_project.cli …`. |
| In Windows cmd, a path with `$HOME` creates a folder named `$HOME` | `$HOME` is PowerShell syntax; in cmd use `%USERPROFILE%`. |
| Port 8765 is in use | `bb serve --port 8766`. |
| Analytics says "No experiment results yet" | Run Level 1's `bb ablate`, or start the server with `bb serve --experiments results`. |
| `bb check` reports MedAgentBench grader errors | The FHIR server is down: `docker compose up -d fhir`, then rerun the same `bb ablate` command (it resumes). |
| `refsol.py missing` | Download it as described in Level 3, step 4. |
| Ollama runs out of memory (8 GB machines) | Use `OLLAMA_NUM_PARALLEL=1`, and set `workers = 1` and `max_in_flight = 1` in a copy of the config. |

## Documentation

| | |
|---|---|
| [paper/project_report.pdf](paper/project_report.pdf) | the project report (method, setup, results, discussion) |
| [docs/architecture.md](docs/architecture.md) | the four layers and how a session runs |
| [docs/pxp.md](docs/pxp.md) | the protocol, the grammar, and every adaptation for three agents |
| [docs/counterfactual.md](docs/counterfactual.md) | reflection, sandbox, credit and intervention, with a worked example |
| [docs/experiments.md](docs/experiments.md) | the design, benchmarks, metrics, the full results and the limitations |
| [docs/api.md](docs/api.md) | REST and WebSocket messages |
| [docs/team.md](docs/team.md) | roles, what each owns, milestones, workflow |
| [web/README.md](web/README.md) | the UI's views and code |
| [scripts/gpu_runbook.md](scripts/gpu_runbook.md) | running the experiments on each kind of hardware |

## Repository layout

```
src/ai_project/
  protocol/        PXP messages, grammar (Algorithm 1), intelligibility
  blackboard/      event-sourced board, stores (memory, JSON lines, Redis)
  scheduler/       scheduler, priority arbiter, consensus
  deadlock/        deadlock rules
  agents/          agent pipeline, AGENT procedure, team builder, tools
  llm/             providers, broker, cache, prompt matrix, personas and schemas, parser
  counterfactual/  sandbox replay, credit assignment, intervention
  benchmarks/      synthetic, MSCoRe, KramaBench, MedAgentBench, scoring, fetch
  experiments/     ablation runner, analysis, plots
  server/          FastAPI app and live sessions
  session.py       one session end to end
  cli.py           bb run | serve | fetch | ablate | check | report
web/               React + TypeScript + D3 UI
experiments/configs/   experiment configurations (see above)
results/           committed results of the reported run
paper/             project report (LaTeX source and PDF)
docker-compose.yml, docker/   vLLM, FHIR server, Redis, code sandbox image
scripts/           gpu_runbook.md, export_ui_fixture.py
tests/             mirrors src/ (355 tests); CI runs them on every pull request
```

## Status and limitations

All four deliverables are implemented and tested, and CI (ruff, pytest on Python 3.11 and 3.13,
the web tests and build) runs on every pull request. Limitations:
- **Scale.** The language-model run is at reduced scale with a 4-bit model. Its intervals are wide
  (up to 58 points), and it had no deadlocks.
- **Mock numbers.** The pipeline check uses scripted agents, so it shows that the mechanism works,
  not how language models behave.
- **Full design.** It is ready to run (`ablation.toml`) when a suitable GPU is available.

See [docs/experiments.md](docs/experiments.md#limitations). The state at the flash talk is tagged
`v0.1-flash-talk`.
