# Running the experiments on the GPU machine

This is the NVIDIA path (Linux, or Windows with WSL2 and Docker Desktop). A 7B model needs about
16 GB of GPU memory at bf16. On a 12 GB card, use the AWQ checkpoint
(`Qwen/Qwen2.5-7B-Instruct-AWQ`). On machines without an NVIDIA GPU (for example Apple Silicon),
serve the model with Ollama and use `smoke-ollama.toml` / `ablation-ollama.toml`.
[../COMPUTE_PROMPT.md](../COMPUTE_PROMPT.md) covers both paths step by step, written as a prompt
for an AI agent on the compute machine.

## 1. Install

```bash
git clone https://github.com/Naitik-Gupta96/AI_Project.git && cd AI_Project
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,bench,plots]"
```

## 2. Start the services

```bash
docker compose up -d vllm fhir      # model on :8000, FHIR on :8080 (first start downloads both)
docker compose build sandbox        # image for KramaBench's python tool
curl -s localhost:8000/v1/models    # wait until the model is listed
curl -s localhost:8080/fhir/metadata | head -c 200
```

## 3. Get the data

```bash
bb fetch mscore kramabench medagentbench
```

MedAgentBench's grader is distributed separately. Download `refsol.py` from the link in the
[MedAgentBench README](https://github.com/stanfordmlgroup/MedAgentBench) and save it as
`data/medagentbench/refsol.py`.

## 4. Smoke test

```bash
bb run --benchmark mscore --provider vllm:Qwen/Qwen2.5-7B-Instruct --cf design production market
bb ablate experiments/configs/smoke.toml
```

This runs 10 tasks in two groups across all three benchmarks. Check that:
- the counts in `runs/experiments/smoke-qwen2.5-7b/trials.jsonl` look sane;
- the `format_errors` column is not dominating;
- no trial has `"failed": true`.

## 5. The ablation

```bash
bb ablate experiments/configs/ablation.toml
```

- **What it runs:** 4 groups × 500 trials (300 MSCoRe, 100 KramaBench, 100 MedAgentBench).
- **Interruptions:** it can be stopped and restarted at any time; finished trials are kept.
- **Speed:** `workers` and `max_in_flight` in the config set the throughput. Raise them while the
  GPU is not saturated (watch `nvidia-smi`).
- **Cache:** the response cache (`cache.sqlite` in the run directory) means the four groups share
  their calls up to the first deadlock.

## 6. Results

```bash
bb check  runs/experiments/ablation-qwen2.5-7b    # must print OK (exit code 1 on problems)
bb report runs/experiments/ablation-qwen2.5-7b
```

This writes:
- `summary.json` and `groups.csv`;
- `figures/convergence.svg`, `figures/intelligibility.svg` and `figures/tokens.svg`;
- `tables/groups.tex`.

The paper includes the figures and table from there (copy them to `paper/`). For the UI, run
`bb serve` and open the Analytics tab.

To share results with the team, copy the whole `runs/experiments/<name>/` directory. It holds
every trial, every session's event log, and the cache.
