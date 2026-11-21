# Running the experiments

The model is Qwen2.5-7B-Instruct. Pick the path that matches the machine:

| Machine | Model server | Configs |
|---|---|---|
| NVIDIA GPU, 16 GB+ VRAM (Linux, or Windows with WSL2 + Docker Desktop) | vLLM, `Qwen/Qwen2.5-7B-Instruct` (bf16) | `smoke.toml`, `ablation.toml` |
| NVIDIA GPU, 12–15 GB | vLLM, `Qwen/Qwen2.5-7B-Instruct-AWQ` | copies of the above with the model name changed |
| Apple Silicon, 16 GB+ | Ollama, `qwen2.5:7b-instruct` (4-bit) | `smoke-ollama.toml`, `ablation-ollama.toml` |

A CPU-only machine is too slow for 2,000 sessions. Run all four groups of one ablation on the same
machine and model build.

## 1. Install and check

```bash
git clone https://github.com/Naitik-Gupta96/AI_Project.git && cd AI_Project
python3 -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev,bench,plots]"
python -m pytest && ruff check src tests scripts
cd web && npm ci && npm test && npm run build && cd ..
bb run --cf analyst                                     # ends with "status CONSENSUS answer Option B"
```

## 2. Start the model, the FHIR server and the sandbox

On macOS, enable "Use Rosetta for x86/amd64 emulation" in Docker Desktop first. The FHIR image is
x86 only.

**NVIDIA (vLLM):**

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi   # Docker sees the GPU
docker compose up -d vllm fhir
curl -s http://127.0.0.1:8000/v1/models        # repeat until the model is listed
```

For a 12–15 GB card, start vLLM with
`MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ docker compose up -d vllm`. Lower `--max-model-len` in
`docker-compose.yml` if it runs out of memory, and use copies of the configs with the AWQ model name
(provider and KramaBench `judge`) and a new run `name`.

**Apple Silicon (Ollama):**

```bash
OLLAMA_NUM_PARALLEL=4 OLLAMA_MAX_LOADED_MODELS=1 ollama serve   # own terminal; quit the Ollama app first
ollama pull qwen2.5:7b-instruct
docker compose up -d fhir
```

With 8 GB of memory, use `OLLAMA_NUM_PARALLEL=1` and set `workers = 1` and `max_in_flight = 1` in
copies of the Ollama configs.

**Both:**

```bash
docker compose build sandbox                    # image for KramaBench's python tool
curl -s http://127.0.0.1:8080/fhir/metadata | head -c 200
```

## 3. Get the data

```bash
bb fetch mscore kramabench medagentbench
```

MedAgentBench's grader is distributed separately. Download `refsol.py` from the link in the
[MedAgentBench README](https://github.com/stanfordmlgroup/MedAgentBench) and save it as
`data/medagentbench/refsol.py`. Do not commit it.

## 4. Smoke test

```bash
bb ablate experiments/configs/smoke.toml        # or smoke-ollama.toml
bb check  runs/experiments/<smoke-run>          # must print OK
bb serve --runs runs/experiments/<smoke-run>    # open http://127.0.0.1:8765 and read some sessions
```

`bb check` flags:
- crashed trials;
- sessions that failed because an agent produced no valid message;
- MedAgentBench grader errors;
- KramaBench judge fallbacks;
- missing token counts.

In the UI, check that:
- MSCoRe answers are in Chinese;
- KramaBench agents call `list_files` and `python`;
- MedAgentBench predictions are `{"answer": [...], "posts": [...]}`;
- deadlocked sessions in the 100% group show an intervention.

The MedAgentBench grading adapter (`benchmarks/medagentbench.py`) follows the official harness but
has not been run against the real `refsol.py`. If `bb check` reports grader errors, align the
adapter with `refsol.py` and rerun the smoke with `--restart`.

## 5. The ablation

```bash
bb ablate experiments/configs/ablation.toml     # or ablation-ollama.toml
```

- **Keep the machine awake.** macOS: prefix with `caffeinate -dims`. Linux: run inside `tmux`
  under `systemd-inhibit --what=sleep:idle`.
- **Interruptions.** If it stops, run the same command again: finished trials are kept.
- **Health.** Run `bb check` every few hours.
- **Cache.** The response cache (`cache.sqlite` in the run directory) lets the four groups share
  their calls up to the first deadlock.

## 6. Results

```bash
bb check  runs/experiments/<run>                # must print OK
bb report runs/experiments/<run>
```

This writes:
- `summary.json` and `groups.csv`;
- `figures/convergence.svg`, `figures/intelligibility.svg` and `figures/tokens.svg`;
- `tables/groups.tex`.

Copy `figures/` and `tables/` into `paper/`. Commit `summary.json`, `groups.csv`, the figures, the
tables and a gzipped `trials.jsonl` under `results/<run>/`. Keep `sessions/` and `cache.sqlite`
outside git and share them separately. `bb serve --experiments runs/experiments` shows the results
in the Analytics tab.
