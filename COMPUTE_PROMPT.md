# Prompt for the compute machine

> Give this whole file to the AI coding agent (for example Claude Code) on the machine that will
> run the experiments. It is self-contained: the agent needs no other context.

---

You are taking over the compute phase of a university research project:
**Intelligible Blackboard Architecture with Counterfactual Agents**
(https://github.com/Naitik-Gupta96/AI_Project, default branch `main`).

The code is finished and tested. Three LLM agents coordinate through a shared blackboard using
the PXP protocol (INIT / RATIFY / REVISE / REFUTE / REJECT). Counterfactual-capable agents
replay deadlocked sessions in a sandbox and apply the best alternative to the live board.

What is left is to run the experiments with a real model, check them, and put the results into
the repository and the paper. The model is **Qwen2.5-7B-Instruct**: the spec asks for a local 7B
model.

## Your goal

1. Set the machine up and prove the code works on it (tests, a smoke run, the UI).
2. Run the full ablation: 4 groups (0 / 33 / 67 / 100% counterfactual-capable agents) × 500 tasks
   (300 MSCoRe + 100 KramaBench + 100 MedAgentBench) = 2,000 sessions.
3. Check the run, produce the report, and commit the results, the figures and the paper's results
   section through a pull request.
4. Clean up: delete this prompt file from the repository, and leave the repository looking like
   the team did the work themselves (Step 8).
5. Tell the human exactly what happened.

Read these first, in the repository: `README.md`, `docs/experiments.md`,
`scripts/gpu_runbook.md`, `docs/architecture.md`.

## Rules

- **Git identity.** Commit as `Naitik-Gupta96 <guptanaitik1234@gmail.com>`, with no
  `Co-Authored-By` or other AI attribution lines in commits or PR descriptions. Set it per
  repository with `git config user.name Naitik-Gupta96` and
  `git config user.email guptanaitik1234@gmail.com`.
- **Write like the team.** This applies to commit messages, PR titles and descriptions, docs,
  paper text and code comments.
  - Commits: short conventional subjects (`feat:`, `fix:`, `docs:`, `exp:`, `chore:`), with a
    plain body explaining why.
  - PR descriptions: a few factual lines.
  - Never mention AI assistants, agents running the work, prompts given to you, hand-offs, this
    file, or "generated with" lines anywhere in the repository or on GitHub.
  - No emoji, no marketing tone, no filler. Match the style of the existing files and the
    existing git history (`git log`).
- **Workflow.** Never commit to `main` directly. Work on a branch (`fix/...`, `exp/...`), open a
  pull request, wait for CI (ruff, pytest on Python 3.11 and 3.13, web tests and build) to pass,
  then merge and delete the branch.
- **Never commit data.** Keep out of git: `data/`, `runs/`, `.cache/`, model weights, `refsol.py`
  (the MedAgentBench grader is the authors' file), session logs and the response cache.
- **Do not change the experimental design.** Leave alone: group fractions, sample sizes, seeds,
  session settings (message budget, k, τ, interventions, apply mode, tool calls) and scoring
  thresholds. If something forces a change, stop and ask the human.
- **What you may fix.** Bugs you find (in adapters, parsing, tools, the UI), each with a test in a
  PR. Prompt wording only if a smoke run shows the model misreading an instruction. Never change
  what information agents see.
- **One machine, one path.** All four groups of a run must come from the same machine, provider
  and model build. Never mix vLLM and Ollama results.
- **Report honestly.** Copy numbers from `summary.json`; never estimate or round them up. If
  something fails or is skipped, say so.

## Step 1: detect the hardware and pick the path

Run the checks for your OS:

- `nvidia-smi` (all OSes);
- `uname -sm` (macOS and Linux);
- `systeminfo` (Windows).

| You find | Path | Configs |
|---|---|---|
| NVIDIA GPU with ≥ 16 GB VRAM | **A: vLLM**, `Qwen/Qwen2.5-7B-Instruct` in bf16 | `experiments/configs/smoke.toml`, `ablation.toml` |
| NVIDIA GPU with 12–15 GB | **A: vLLM** with the AWQ checkpoint (see A.2) | copies of the above with the model name changed |
| Apple Silicon (`Darwin arm64`) with ≥ 16 GB memory | **B: Ollama** with Metal, `qwen2.5:7b-instruct` (4-bit) | `experiments/configs/smoke-ollama.toml`, `ablation-ollama.toml` |
| Apple Silicon with 8 GB | **B** with `OLLAMA_NUM_PARALLEL=1`, and copies of the Ollama configs with `workers = 1` and `max_in_flight = 1` | copies |
| Anything else (CPU only, AMD GPU, NVIDIA < 12 GB) | **Stop.** Report the hardware to the human: 2,000 sessions on CPU would take weeks. | |

Tell the human which path you chose and why, then continue.

## Step 2: set up and verify the code

Requirements:
- Python 3.11 or newer;
- Node 20 or newer;
- git;
- Docker:
  - **Linux:** Docker Engine plus `nvidia-container-toolkit` for path A.
  - **Windows:** Docker Desktop with WSL2.
  - **macOS:** Docker Desktop. In Settings → General, enable "Use Rosetta for x86/amd64
    emulation" (the FHIR image is x86 only).

```bash
git clone https://github.com/Naitik-Gupta96/AI_Project.git && cd AI_Project
python3 -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev,bench,plots]"
python -m pytest                       # must pass
ruff check src tests scripts           # must pass
cd web && npm ci && npm test && npm run build && cd ..    # must pass
bb run --cf analyst                    # mock session: ends "status CONSENSUS answer Option B"
```

If anything fails here, stop, investigate and fix it through a PR (Rules) before going on. Do not
run models on a broken tree.

## Step 3: start the services

### Path A (vLLM)

1. Check that Docker can see the GPU:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```
2. Start the services and build the sandbox:
   ```bash
   docker compose up -d vllm fhir      # first start downloads ~15 GB of weights and ~2 GB of FHIR image
   docker compose build sandbox        # image for KramaBench's python tool
   curl -s http://127.0.0.1:8000/v1/models     # repeat until Qwen/Qwen2.5-7B-Instruct is listed
   ```
3. **For 12–15 GB of VRAM (A.2):** start vLLM with
   `MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ docker compose up -d vllm`. If it runs out of memory, lower
   `--max-model-len` in `docker-compose.yml` to 12288. Then copy `smoke.toml` and `ablation.toml`
   to new files, change every `Qwen/Qwen2.5-7B-Instruct` to `Qwen/Qwen2.5-7B-Instruct-AWQ` (the
   provider and the KramaBench `judge`), and give each run a new `name`.

### Path B (Ollama)

1. Install Ollama (macOS: `brew install ollama`, or the app from ollama.com).
2. If the app is running, quit it, so the parallel setting below takes effect.
3. Start the server and pull the model:
   ```bash
   OLLAMA_NUM_PARALLEL=4 OLLAMA_MAX_LOADED_MODELS=1 ollama serve      # leave running (own terminal/tmux)
   ollama pull qwen2.5:7b-instruct
   ollama run qwen2.5:7b-instruct "Reply with OK"                     # sanity check
   ```
4. Start the FHIR server and build the sandbox:
   ```bash
   docker compose up -d fhir
   docker compose build sandbox
   ```

### Both paths

```bash
curl -s "http://127.0.0.1:8080/fhir/metadata" | head -c 300   # FHIR up (first start takes ~1-2 min)
docker run --rm ai-project-sandbox python -c "import pandas; print('sandbox ok')"
```

## Step 4: get the data

```bash
bb fetch mscore kramabench medagentbench    # ~450 MB MSCoRe + ~530 MB KramaBench lakes
```

MedAgentBench's grader `refsol.py` is not in its repository. The authors share it through a Box
link in their README (https://github.com/stanfordmlgroup/MedAgentBench, "Download the refsol.py").
Save it as `data/medagentbench/refsol.py`.

If you cannot download it yourself, ask the human to do it, and wait. MedAgentBench cannot be
scored without it.

## Step 5: smoke run and checks

1. Run the smoke config for your path, then check it:
   ```bash
   bb ablate experiments/configs/smoke.toml            # path B: smoke-ollama.toml
   bb check runs/experiments/<smoke-run-name>          # must print OK
   ```
   `bb check` exits with code 1 and lists problems when:
   - trials crashed;
   - more than 5% of sessions failed because an agent produced no valid message;
   - the MedAgentBench grader raised errors;
   - token counts are missing.

   It warns when:
   - the KramaBench paraphrase judge fell back to ROUGE-1;
   - agents average more than one rejected attempt per session.
2. Look at real sessions, not just numbers:
   ```bash
   bb serve --runs runs/experiments/<smoke-run-name> --experiments runs/experiments
   # open http://127.0.0.1:8765 → Open → pick sessions; Analytics shows the smoke run
   ```
   Open at least two sessions per benchmark, and one from the 100% group that deadlocked.
   Confirm:
   - **MSCoRe:** answers are in Chinese and on topic. Judgments (match / agree / changed) are
     plausible.
   - **KramaBench:** agents call `list_files` and `python` (tool events in the board log), and the
     final answer has the format the question asks for.
   - **MedAgentBench:** predictions are JSON `{"answer": [...], "posts": [...]}`. Grading does not
     error. Open the trial's `score.detail` in `trials.jsonl`.
   - **Counterfactual:** a deadlocked 100% session shows an intervention, with sandbox branches in
     the Counterfactual panel.
3. Start one live session from the UI's **New session** form, using the real provider from the
   Provider list, to confirm streaming works with the model.
4. **The MedAgentBench grader adapter has never been run against the real `refsol.py`.**
   `src/ai_project/benchmarks/medagentbench.py` builds the transcript (`result`, `history` with
   `role` / `content`) from the official harness's code. If `bb check` reports grader errors,
   read `refsol.py`, fix the adapter to match it (with a test), and rerun the smoke with
   `--restart`.

Repeat step 5 until `bb check` prints OK and the sessions look right. Record what you fixed.

## Step 6: the full ablation

1. **Estimate the runtime.** The smoke run's elapsed time per trial × 2,000 is a ceiling: the
   cache shares calls between groups.
   - Tell the human the estimate.
   - If it is above 48 hours, ask before starting.
2. **Keep the machine awake and run it detached:**
   - macOS: `caffeinate -dims bb ablate experiments/configs/ablation-ollama.toml`
   - Linux: inside `tmux`, run `systemd-inhibit --what=sleep:idle bb ablate experiments/configs/ablation.toml`
   - Windows: set the power plan to never sleep, then run the command in a terminal that stays open.
3. **If it stops** (crash, reboot, sleep), run the same command again. Finished trials are kept,
   and only missing ones run. Never pass `--restart` to the full run unless the human asks.
4. **Every few hours**, run `bb check runs/experiments/<run-name>`. It reports progress and
   catches problems early.

## Step 7: report and commit the results

1. **Generate the report.**
   ```bash
   bb check  runs/experiments/<run-name> | tee runs/experiments/<run-name>/health.txt   # must end with OK
   bb report runs/experiments/<run-name>
   ```
2. **Commit the results.** On a branch `exp/<run-name>`:
   - add `results/<run-name>/` containing `meta.json`, `summary.json`, `groups.csv`,
     `health.txt`, `figures/`, `tables/`, and `trials.jsonl.gz` (`gzip -k trials.jsonl`; skip it
     if larger than 50 MB and say so);
   - copy `figures/` and `tables/` into `paper/`;
   - update the docs and paper:
     - `docs/experiments.md`: add a **Results** section. Give the model and build (bf16 vLLM or
       4-bit Ollama), hardware, dates, runtime, and the per-group table with 95% intervals and
       McNemar p-values, all copied from `summary.json`. Then cover convergence success,
       intelligibility depth and token cost, each in one short paragraph that states only what
       the numbers show.
     - `paper/main.tex`: fill **Experimental setup** from `docs/experiments.md`, and the
       **Results** text around the existing figure and table. Leave Introduction and Discussion
       to the team.
     - `paper/references.bib`: complete the author lists from each paper's arXiv page.
     - `README.md`: replace the Status section with the run name, the headline numbers and a link
       to `results/<run-name>/`.
   - Open a PR, wait for CI, merge.
3. **Hand over the large artifacts.** Zip `runs/experiments/<run-name>/sessions/` and
   `cache.sqlite` for the human to store outside git. These are the session logs the UI can
   replay, and the cache that makes reruns free.

## Step 8: clean up

Do this last, after every other PR is merged.

1. On a branch `chore/cleanup`, delete this file:
   ```bash
   git rm COMPUTE_PROMPT.md
   ```
   Nothing in the repository links to it.
2. Check that no traces remain:
   ```bash
   git grep -n -i -E "COMPUTE_PROMPT|claude|anthropic|chatgpt|copilot|ai agent|ai assistant|coding agent|hand-?off|as an ai"
   ```
   This must print nothing. Words like `prompt` in `src/ai_project/llm/prompts/` are the project's
   own agent prompt library and are fine. Rewrite anything else in the plain team style.
3. Check that no local files are tracked:
   ```bash
   git ls-files | grep -E "^(\.claude|data|runs|\.cache)/|refsol\.py|\.sqlite$"
   ```
   This must print nothing. If it lists anything, `git rm --cached` it.
4. Commit as `chore: remove the experiment run checklist`. Open a PR with a one-line plain
   description, wait for CI, merge, and delete the branch.
5. Leave the repository tidy:
   - only `main`, locally and on GitHub;
   - `git status` clean;
   - no stray files from your work. Your notes, logs and scratch files go outside the repository
     or get deleted.
6. Your report to the human (Step 9) goes in this chat, not into the repository.

## Step 9: final message to the human

Report:
- **Setup:**
  - hardware, path (A or B), model build;
  - the commit of `main` you ran;
  - start and end time, total runtime;
- **Problems:** everything you fixed (with PR links), and anything you could not fix;
- **Run health:** the `bb check` output;
- **Results:** the headline numbers per group, overall and per benchmark (convergence success with
  95% CI, deadlock and recovery rates, Ultra-Strong / Strong share, tokens per instance live vs
  sandbox), and the McNemar results against the control group;
- **Locations:** where the results, figures and zipped artifacts are;
- **Cleanup:** confirmation that `COMPUTE_PROMPT.md` is deleted, the trace checks printed nothing,
  and only `main` remains;
- **Still open:** anything left, such as the Introduction and Discussion of the paper.

## Known caveats to keep in mind (already documented in `docs/experiments.md`)

- **MSCoRe answers are capped** at about 500 characters, so prompts fit the context window. ROUGE-L
  is therefore lower than for unconstrained answers, equally for every group.
- **The KramaBench paraphrase judge** for 10 `string_approximate` tasks is the same Qwen model.
  KramaBench used a stronger judge; say so in the results.
- **The model makes the explanation-agreement and reasoning-change judgments itself.** The tag
  rule is then applied exactly by code.
