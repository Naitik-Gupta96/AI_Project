# Instructions to compute

24 Nov 2026, updated the same day for a reduced-scale run

These are the steps for running the AI_Project experiments on the **RTX 5060 Ti (16 GB)** machine
and finishing the project:
- setup;
- two small PRs;
- the smoke run;
- a reduced-scale ablation;
- the results, the paper and cleanup.

**When every step below is done, this file is deleted** (Step 9).

**Update, 24 Nov 2026 (evening): the reduced-scale run moved to the Mac.** Only the Apple Silicon
Mac (M5, 16 GB) is available now, so the final run uses Ollama with `qwen2.5:7b-instruct` (4-bit,
Q4_K_M) and `experiments/configs/ablation-quick-ollama.toml`: 25 tasks per group (10 MSCoRe,
5 KramaBench, 10 MedAgentBench, one per task type), 100 sessions, into
`runs/experiments/ablation-quick-ollama-qwen2.5-7b`. Where the steps below name the 5060 Ti, vLLM,
the AWQ build or `ablation-quick-awq.toml`, read the Mac, Ollama and this config instead, and do
not run the GPU version as well. The results state the build (Ollama, 4-bit) and the reduced scale
(Rules). The paper's LaTeX is left for later.

**What changed in this version.** GPU time is limited, so the ablation now runs at reduced scale.
It keeps the brief's four groups, three benchmarks, model and session settings, with **40 tasks per
group** (160 sessions, about 15 to 30 minutes) instead of 500 (2,000 sessions, 3 to 8 hours). It
is reported as exactly that (Rules, "Report the scale honestly").

If you worked from an earlier version of this file:
1. Keep what is done and download this version again (below).
2. Re-read Steps 3, 5, 6 and 7 before going on.
3. If PR 2 of Step 3 is already merged, add the new config of Step 3 (item 3 of PR 2) and its test
   in a new PR, `exp/quick-ablation-config`.

## How to use this file

Download it outside the repository and work from that copy. Step 3 checks out a branch that is
older than this file, which would remove it from the working tree.

```bash
curl -fsSL https://raw.githubusercontent.com/Naitik-Gupta96/AI_Project/main/instructions_to_compute.md \
  -o ~/instructions_to_compute.md
```

Then tell Claude Code on that machine: *Read ~/instructions_to_compute.md and carry it out.*

**Who does what.** "You" in this file is Claude Code; "the human" is the person at the machine.

- **Claude Code does everything except starting the ablation run:**
  - all installs and downloads (drivers aside);
  - every code change and PR;
  - starting the services;
  - the smoke run;
  - preparing the ablation run.
- **The human starts the ablation run** from a terminal (cmd on Windows), so the run does not
  depend on a Claude Code session staying open. Step 6 prepares it, writes a one-line start
  command, and hands it over.
- **Afterwards,** Claude Code continues from Step 7, in the same session or a new one.

**Read first, in the repository:** `strictly_follow.md` (the project brief; follow it strictly),
`README.md`, `docs/experiments.md`, `scripts/gpu_runbook.md`, `docs/architecture.md`.

**Keep a log** outside the repository (`~/compute_log.md`). Record start and end times, commands,
PR links, numbers and problems. Steps 7 to 10 may run in a new session, so they rely on this log.

**Stop points.** Stop, report, and wait for an explicit answer when:

1. The GPU is not an NVIDIA card with at least 16 GB (Step 1).
2. `refsol.py` cannot be downloaded (Step 2).
3. **The smoke gate and hand-over:** the ablation run is prepared. Report the smoke numbers,
   deadlock rate and runtime estimate, and give the human the start command (Step 6). Never start
   the ablation run yourself.
4. The finished run shows a code bug (Step 7): a fix would put two commits into one run.
5. Anything would change the experimental design beyond what this file sets (Rules).
6. Before drafting the paper's Discussion (Step 8).

## Rules

- **Git identity.** Commit as Mayank Sharma, using the same email as Mayank's existing commits on
  `main`:

  ```bash
  git config user.name "Mayank Sharma"
  git config user.email "$(git log -1 --format=%ae --author=mayank-sharma262006 origin/main)"
  git config user.email   # must print an address, not an empty line
  ```

  Log in with `gh auth login`. Add no `Co-Authored-By` or other attribution lines to commits or
  PRs.
- **Workflow.** Never commit to `main` directly.
  1. Use a short branch (`fix/...`, `exp/...`, `docs/...`, `chore/...`) and open a PR.
  2. Wait for CI to pass: ruff, pytest on Python 3.11 and 3.13, web tests and build.
  3. Squash-merge and delete the branch: `gh pr merge <n> --squash --delete-branch`.
  4. Then run `git switch main && git pull && git fetch --prune`.
- **Style.** Commit subjects are short and conventional (`feat:`, `fix:`, `docs:`, `exp:`,
  `chore:`), with a plain body that says why. PR descriptions are a few factual lines. No emoji, no
  marketing tone. Match `git log` and the existing docs.
- **Never commit data.** Keep these out of git:
  - `data/`, `runs/`, `.cache/` and model weights;
  - `refsol.py`, session logs and `cache.sqlite`;
  - your copy of this file and your log.
- **Do not change the experimental design.** Leave these alone:
  - group fractions and seeds;
  - session settings: message budget, k, τ, interventions, apply mode, tool calls;
  - scoring thresholds, including MSCoRe's 0.3 ROUGE-L.

  The sample sizes are the ones this file sets (Step 3), with the one fallback in Step 5. If
  anything else forces a change, stop and ask. Parallelism (`workers`, `max_in_flight`) and vLLM
  memory settings are not design.
- **What you may fix.** Bugs in adapters, parsing, tools or the UI, each with a test, in its own
  PR. Change prompt wording only if a smoke run shows the model misreading an instruction.
- **One machine, one build.** All four groups must come from:
  - this machine;
  - vLLM with `Qwen/Qwen2.5-7B-Instruct-AWQ`;
  - one vLLM image;
  - one commit of `main`.

  Never use Ollama for the real run, and never mix in the Mac smoke numbers.
- **Report honestly.** Copy numbers from `summary.json` or `bb check`; never estimate or round
  them up. Say what failed or was skipped.
- **Report the scale honestly.** Wherever results appear (the docs, the paper including its
  abstract, the README and the final report), state:
  - the actual size, for example "40 tasks per group, 160 sessions; the brief specifies 500 per
    group";
  - the reason (limited GPU time);
  - that `ablation.toml` (or `ablation-awq.toml` on a 16 GB card) runs the full design unchanged;
  - that the intervals are wide at this size.

  Never describe the run as 500 tasks per group or 2,000 sessions. `meta.json` and `trials.jsonl`
  record every trial, so any such claim would contradict the committed data.

## Why the AWQ build on this card

Qwen2.5-7B-Instruct has 7.6 B parameters. In bf16 its weights alone take 15.2 GB, which leaves
nothing on a 16 GB card for the KV cache, the CUDA context or the display. Qwen's official 4-bit
AWQ release, `Qwen/Qwen2.5-7B-Instruct-AWQ`, needs about 5.5 GB. That leaves 7 to 8 GB of KV cache,
enough for the 24 parallel sessions of the ablation config. It is still Qwen2.5-7B-Instruct, the
spec's local 7B model. The Results and the paper state the build as "AWQ 4-bit".

The existing `smoke.toml` and `ablation.toml` name the bf16 model, so Step 3 adds AWQ copies of
them and the reduced-scale config.

## Where the project stands

- **Code:** all four spec deliverables are done on `main`, and CI is green.
- **Paper:**
  - The Introduction, the Architecture and the Experimental setup are written.
  - The Results wait for this run.
  - The Discussion waits for the Results.
- **Mac smoke run (Ollama, 4-bit):** this setup and smoke run found the bugs fixed in #8 to #15.
  - Every session reached consensus in 4 messages (INIT, then RATIFY from the others).
  - Nothing deadlocked, so no counterfactual intervention ran, and the 0% and 100% groups came out
    almost identical.
  - These numbers are not results. The deadlock rate is the thing to watch at the smoke gate.
- **Open branch:** `fix/medagentbench-post-functions` (commit 38b92a5, not merged).
  - The original MedAgentBench harness shows its agent every function in `funcs_v1.json`,
    including the three POST functions for orders and records. Our agents only saw the GET
    searches, so order tasks could not be answered in the form the grader reads.
  - The branch lists the POST functions (full url, description, payload fields) in the answer
    format. It adds about 1,300 tokens to each MedAgentBench prompt and has a test.
  - It is merged in Step 3.

**Decisions already taken (do not reopen):**

- **Reduced scale.** The run uses 40 tasks per group (20 MSCoRe, 10 KramaBench, 10 MedAgentBench,
  one per task type), reported as such (Rules).
- **No deadlocks is not a blocker.** The run goes ahead even if the smoke run shows no deadlocks.
  The Results then report the null result plainly; the design is not changed to force deadlocks.
- **MSCoRe runs as designed.** Expect accuracy near 0% in every group: answers are 50 to 250
  characters, while references have a median of about 1,100. Report it plainly with the ROUGE-L
  values, and say why.
- **The artifacts zip** (session logs and cache) stays on this machine.

## Step 1: hardware and tools

1. **Check the card:**

   ```bash
   nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
   ```

   It should show an RTX 5060 Ti with about 16,300 MiB. If not, stop (stop point 1).
2. **Driver.** Install the latest NVIDIA driver. The RTX 50 series (Blackwell) is not supported by
   older drivers.
3. **OS:**
   - **Linux:** install Docker Engine and `nvidia-container-toolkit`, and run long jobs in `tmux`.
   - **Windows:** install Docker Desktop with the WSL2 backend and work only inside the WSL2
     Ubuntu shell.
     - Clone into the Linux home directory, never under `/mnt/c`: the KramaBench lakes are slow
       through `/mnt/c`.
     - If the PC has 16 GB of RAM, give WSL more: in `%UserProfile%\.wslconfig`, put `[wsl2]` and
       `memory=12GB`, then run `wsl --shutdown`.
     - Make Ubuntu the default WSL distribution (`wsl --set-default Ubuntu`), and turn on Docker
       Desktop's WSL integration for it (Settings → Resources → WSL integration). The human's
       start command in Step 6 relies on both.
     - Set the power plan so the PC never sleeps.
4. **Also install:** Python 3.11+, Node 20+, git, `gh`, `tmux`.
5. **Docker sees the GPU:**

   ```bash
   docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
   ```

## Step 2: clone, verify, get the data

1. **Clone and install:**

   ```bash
   git clone https://github.com/Naitik-Gupta96/AI_Project.git && cd AI_Project
   python3 -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev,bench,plots]"
   ```

   Then set the git identity (Rules) and run `gh auth login`.
2. **Verify.** If anything fails, fix it through a PR first.

   ```bash
   python -m pytest
   ruff check src tests scripts
   (cd web && npm ci && npm test && npm run build)
   bb run --cf analyst          # mock session with an intervention; ends "status CONSENSUS answer Option B"
   ```

3. **Data** (about 1 GB; start the vLLM pull of Step 4 in parallel if you like):

   ```bash
   bb fetch mscore kramabench medagentbench
   curl -L -o data/medagentbench/refsol.py \
     "https://stanfordmedicine.app.box.com/index.php?rm=box_download_shared_file&shared_name=fizv0unyjgkb1r3a83rfn5p3dc673uho&file_id=f_1756907296228"
   wc -c data/medagentbench/refsol.py     # 15541 bytes
   head -2 data/medagentbench/refsol.py   # "import json", "from .utils import *"
   ```

   That URL is the direct download behind the Box link in the
   [MedAgentBench README](https://github.com/stanfordmlgroup/MedAgentBench). If the size or the
   first lines differ (for example an HTML login page), stop (stop point 2). Never commit
   `refsol.py`.

## Step 3: two PRs before any model runs

**PR 1: merge the MedAgentBench fix.**

```bash
git switch fix/medagentbench-post-functions
python -m pytest && ruff check src tests scripts
gh pr create --base main --head fix/medagentbench-post-functions \
  --title "fix: list the MedAgentBench POST functions in the answer format"
```

- **PR body:** the original harness shows its agent the POST functions of `funcs_v1.json`; without
  them, order and record tasks cannot be answered in the form the grader reads.
- Wait for CI, then squash-merge.

**PR 2: AWQ configs for a 16 GB GPU, including the reduced-scale ablation.** Do this on branch
`exp/awq-configs` from the updated `main`:

1. **`experiments/configs/smoke-awq.toml`:** a copy of `smoke.toml` with these changes:
   - `name = "smoke-qwen2.5-7b-awq"`;
   - `provider = "vllm:Qwen/Qwen2.5-7B-Instruct-AWQ"`;
   - KramaBench `judge = "vllm:Qwen/Qwen2.5-7B-Instruct-AWQ"`;
   - the header comment says it is for GPUs with less than 24 GB.
2. **`experiments/configs/ablation-awq.toml`:** a copy of `ablation.toml` with these changes:
   - `name = "ablation-qwen2.5-7b-awq"`;
   - the same provider and judge as above;
   - the header comment says: same design as `ablation.toml`; only the model build differs
     (Qwen's official AWQ 4-bit release, which fits a 16 GB GPU).

   This is the full design, kept for when GPU time allows. It is not run now.
3. **`experiments/configs/ablation-quick-awq.toml`:** a copy of `ablation-awq.toml` with these
   changes:
   - `name = "ablation-quick-qwen2.5-7b-awq"`;
   - `n = 20` for MSCoRe, `n = 10` for KramaBench and `n = 10` for MedAgentBench.

   With `n = 10`, the MedAgentBench loader takes one task per type. The header comment says:
   "Reduced-scale run of the spec's ablation for limited GPU time: 40 tasks per group instead of
   500. Everything else is as in ablation.toml."
4. **`tests/experiments/test_experiments.py`:**
   - Parametrize `test_ollama_ablation_has_the_same_design_as_the_spec_ablation` over
     `ablation-ollama.toml` and `ablation-awq.toml`, and rename it to match. For
     `ablation-awq.toml`, also assert that the provider and the KramaBench judge name the AWQ
     model.
   - Add a test for `ablation-quick-awq.toml`. Its fractions and `session_config()` equal those of
     `ablation.toml`, and its benchmarks are the same three in the same order with `n` of 20, 10
     and 10.
5. **`docker-compose.yml`:** change `--gpu-memory-utilization 0.90` to
   `--gpu-memory-utilization ${GPU_MEMORY_UTILIZATION:-0.90}`.
6. **`scripts/gpu_runbook.md`:**
   - **Hardware table:**
     - NVIDIA 24 GB+ uses bf16 (`smoke.toml`, `ablation.toml`).
     - NVIDIA 12 to 23 GB (e.g. RTX 5060 Ti 16 GB) uses `Qwen/Qwen2.5-7B-Instruct-AWQ`
       (`smoke-awq.toml`, `ablation-awq.toml`, and `ablation-quick-awq.toml` for limited GPU
       time). Give the reason: bf16 weights alone are 15.2 GB.
     - Apple Silicon is unchanged.
   - **Start command:** replace the "copies of the configs" text with
     `MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ docker compose up -d vllm fhir`, plus a note that
     `GPU_MEMORY_UTILIZATION=0.85` helps when the card also drives a display.
   - **Stale note:** delete the paragraph that says the MedAgentBench adapter "has not been run
     against the real `refsol.py`" (#12 checked it). Keep the advice that grader errors mostly mean
     FHIR is down.
7. **`README.md`:**
   - In the layout block, list the configs as
     `ablation(-awq|-quick-awq|-ollama).toml, smoke(-awq|-ollama).toml, mock-synthetic.toml`.
   - In "Real runs", mention the AWQ build for GPUs under 24 GB.
8. **Check, commit and merge.** Run `python -m pytest && ruff check src tests scripts`. Commit
   `exp: add AWQ run configs, including a reduced-scale ablation`, open the PR, wait for CI and
   squash-merge.

## Step 4: start the services

1. **Pull vLLM once,** and never again until the ablation run is finished: one image means one
   build.

   ```bash
   docker compose pull vllm fhir
   ```

2. **Start everything:**

   ```bash
   export MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ
   docker compose up -d vllm fhir
   docker update --restart unless-stopped $(docker compose ps -q vllm fhir)
   docker compose build sandbox
   curl -s http://127.0.0.1:8000/v1/models      # repeat until Qwen/Qwen2.5-7B-Instruct-AWQ is listed (5.5 GB download)
   curl -s http://127.0.0.1:8080/fhir/metadata | head -c 300
   docker run --rm ai-project-sandbox python -c "import pandas; print('sandbox ok')"
   ```

3. **If vLLM stops at startup,** read `docker compose logs vllm`:
   - **"No available memory for the cache blocks" or "insufficient free memory":** the display is
     using VRAM. Restart with
     `GPU_MEMORY_UTILIZATION=0.85 MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ docker compose up -d vllm`
     and note the value in the log.
   - **"no kernel image is available for execution on the device":** the image is too old for
     Blackwell. Pull it again before any run.
4. **Record the build** in the log; it goes into the Results:

   ```bash
   docker image inspect vllm/vllm-openai:latest --format '{{index .RepoDigests 0}}'
   docker compose exec vllm python3 -c "import vllm; print(vllm.__version__)"
   nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
   ```

   Also record the OS and the `GPU_MEMORY_UTILIZATION` value.

FHIR once stopped without warning on the Mac. While FHIR is down, MedAgentBench sessions get tool
errors and the grader cannot read reference values, so check it before every run.

## Step 5: smoke run and the gate

1. **Run it on the merged `main`.** It takes about 10 to 20 minutes, so run it in the background
   and check on it.

   ```bash
   git switch main && git pull
   time bb ablate experiments/configs/smoke-awq.toml   # writes runs/experiments/smoke-qwen2.5-7b-awq
   bb check runs/experiments/smoke-qwen2.5-7b-awq      # must print OK
   ```

   `bb check` exits with code 1 when any of these occur:
   - crashed trials;
   - more than 5% failed sessions;
   - grader errors;
   - missing token counts.

   It warns on judge fallbacks to ROUGE-1 and on more than one rejected attempt per session. Fix
   real bugs through PRs, then rerun with `--restart` (allowed for smoke runs only). Write down
   `git rev-parse HEAD`: the ablation run uses this commit.
2. **Read real sessions.** Run
   `bb serve --runs runs/experiments/smoke-qwen2.5-7b-awq --experiments runs/experiments` and
   open http://127.0.0.1:8765. Without a browser, read `sessions/<trial>/events.jsonl` and
   `trials.jsonl`. Read at least two sessions per benchmark:
   - **MSCoRe:** answers are in Chinese and on topic; the match / agree / changed judgments are
     plausible.
   - **KramaBench:** `list_files` and `python` tool events appear; the answer is in the format the
     question asks for.
   - **MedAgentBench:** predictions are `{"answer": [...], "posts": [...]}`. Posts use the listed
     urls (`<base>Observation`, `<base>MedicationRequest`, `<base>ServiceRequest`), and the grader
     raises no errors.
   - **Counterfactual:** any deadlocked 100%-group session shows an intervention with sandbox
     branches.
   - **Live UI:** start one live session from the UI's **New session** form with the vLLM provider.
3. **The smoke gate.** Collect the following; they open the hand-over message in Step 6:
   - **Numbers:** the smoke numbers per group and benchmark, copied from `summary.json`.
   - **Deadlocks:** the deadlock rate and the number of interventions in the 100% group. If both
     are 0, say plainly that the groups will probably not differ. This alone does not block the
     run (decided).
   - **Runtime estimate:** the smoke elapsed time ÷ 20 × 160, halved.
     - The smoke run has 8 workers and shares its cache across two groups; the ablation run has 24
       workers and shares it across four, so the unhalved figure is a ceiling.
     - **If the estimate is over 30 minutes,** reduce `ablation-quick-awq.toml` to 10 MSCoRe,
       5 KramaBench and 10 MedAgentBench (25 tasks per group, 100 sessions) through a PR before
       Step 6, and update its header comment and test. This is the one allowed size change. Report
       the size that was used.
   - **Fixes:** the PR links of any fixes.

## Step 6: prepare the ablation run and hand it to the human

The run is 4 groups (0, 33, 67 and 100% counterfactual-capable agents) × 40 tasks (20 MSCoRe + 10
KramaBench + 10 MedAgentBench), 160 sessions. It runs from
`experiments/configs/ablation-quick-awq.toml` into
`runs/experiments/ablation-quick-qwen2.5-7b-awq`. **Do not start it yourself.** Get everything
ready so that the human only has to run one command, then stop.

**Your part:**

1. **Size the parallelism now.** Nothing may change once the run has started.
   - Find the KV cache size in `docker compose logs vllm`: the line "GPU KV cache size: … tokens".
   - The config runs 24 sessions at once, with prompts of up to about 4,000 tokens.
   - If the cache holds fewer than 100,000 tokens, set `workers = 16` and `max_in_flight = 32` in
     `ablation-quick-awq.toml` through a PR. This is parallelism, not design.
2. **Check:**
   - `git switch main && git pull`, then `git status` is clean.
   - Record `git rev-parse HEAD` as the commit of the ablation run.
   - `docker compose ps` shows vLLM and FHIR up, and both `curl` checks from Step 4 answer.
   - There is enough free disk: about 10 × `du -sh runs/experiments/smoke-qwen2.5-7b-awq`.
3. **Write the run script** `~/run_ablation.sh`, outside the repository, and `chmod +x` it.
   - Use the real clone path and the `GPU_MEMORY_UTILIZATION` value from Step 4.
   - On Linux, prefix the `bb ablate` line with `systemd-inhibit --what=sleep:idle`.
   - Run `bash -n ~/run_ablation.sh` to check its syntax. Do not run the script itself.

   ```bash
   #!/usr/bin/env bash
   # Reduced-scale ablation, 4 groups x 40 tasks. Safe to run again: finished trials are kept.
   set -euo pipefail
   cd ~/AI_Project
   source .venv/bin/activate
   export MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ
   export GPU_MEMORY_UTILIZATION=0.90        # the value from Step 4
   docker compose up -d vllm fhir            # starts them if stopped; same settings, so no reload
   echo "waiting for vLLM and FHIR ..."
   until curl -sf http://127.0.0.1:8000/v1/models >/dev/null; do sleep 10; done
   until curl -sf http://127.0.0.1:8080/fhir/metadata >/dev/null; do sleep 10; done
   echo "start $(date -Is)" | tee -a ~/ablation.log
   bb ablate experiments/configs/ablation-quick-awq.toml 2>&1 | tee -a ~/ablation.log
   echo "end $(date -Is)" | tee -a ~/ablation.log
   bb check runs/experiments/ablation-quick-qwen2.5-7b-awq 2>&1 | tee -a ~/ablation.log
   ```

4. **Write the state into `~/compute_log.md`.** Steps 7 to 10 may run in a new session, so record
   everything they need:
   - the commit of the ablation run;
   - the vLLM version and image digest, the GPU, driver and OS, and `GPU_MEMORY_UTILIZATION`;
   - the smoke numbers and elapsed time;
   - the task counts in `ablation-quick-awq.toml`;
   - every PR link;
   - anything still open.
5. **STOP and hand over.** Send one message. It starts with the smoke gate report (Step 5, item
   3), then gives the human's part below with the real paths filled in.

**The human's part** (copy this into the hand-over message):

- **Start.** If you are happy with the smoke numbers, start the run. It should take about 15 to 30
  minutes. Keep the window open; it prints progress and ends with the `bb check` result.
  - **Windows:** open cmd and run `wsl -e bash -lc "~/run_ablation.sh"`.
  - **Linux:** open a terminal, run `tmux new -s ablation`, then `~/run_ablation.sh`.
- **Progress.** In a second window, run the command below (on Linux, the part inside the quotes).
  It says how many of the 160 trials are done.

  ```
  wsl -e bash -lc "cd ~/AI_Project && .venv/bin/bb check runs/experiments/ablation-quick-qwen2.5-7b-awq"
  ```

- **If it stops** (the window closed, a reboot or a crash), start Docker Desktop if it is not
  running and run the same start command again. Finished trials are kept; only the missing ones
  run.
- **If the progress check reports grader errors,** the FHIR server is down. Press Ctrl-C in the run
  window and start the run again; the script restarts FHIR.
- **Until it finishes:**
  - do not update Windows, the NVIDIA driver or Docker;
  - do not run `git pull` in the project;
  - keep the PC from sleeping.
- **When it finishes,** tell Claude Code: *The run finished; continue from Step 7.* If the session
  has closed, open a new one and say: *Read ~/instructions_to_compute.md and ~/compute_log.md,
  then continue from Step 7.*

## Step 7: after the run, the results PR

One PR, `exp/ablation-quick-qwen2.5-7b-awq`, carries:
- the results and the figures;
- the docs' Results section;
- the paper's Results text;
- the README status.

Every number in it is copied from `summary.json`, and every place that shows results states the
scale (Rules).

1. **Confirm the run.** Read `~/compute_log.md` and `~/ablation.log`.
   - `bb check runs/experiments/ablation-quick-qwen2.5-7b-awq` must report all planned trials and
     OK.
   - If trials are missing, ask the human to run the start command again; it resumes. Never pass
     `--restart`.
   - If it shows a code bug, stop (stop point 4).
   - Log the start, the end and the total runtime from `~/ablation.log`.
   - `git rev-parse HEAD` still equals the commit of the ablation run.
2. **Find a counterfactual example.** In `trials.jsonl`, look for a `cf100` trial with
   `deadlocked` true and `interventions_applied` of at least 1, and note its trial id for the
   Results. If there is none, say so.
3. **Generate:**

   ```bash
   R=runs/experiments/ablation-quick-qwen2.5-7b-awq
   bb check $R | tee $R/health.txt          # must end with OK
   bb report $R                             # figures/, tables/, summary.json, groups.csv
   ```

4. **Add the files:**
   - **`results/ablation-quick-qwen2.5-7b-awq/`:** `meta.json`, `summary.json`, `groups.csv`,
     `health.txt`, `figures/`, `tables/`, and `trials.jsonl.gz` (`gzip -k trials.jsonl`).
   - **`paper/figures/` and `paper/tables/`:** copies of the run's `figures/` and `tables/`.
     `paper/main.tex` already includes `tables/groups.tex`, `figures/convergence.png`,
     `figures/intelligibility.png` and `figures/tokens.png`.
5. **`docs/experiments.md`:**
   - **Design:** change the model line to "Qwen2.5-7B-Instruct (official AWQ 4-bit build) served
     by vLLM". Keep the specified design (500 per group) as it is, and add one sentence saying the
     run reported below used the reduced scale.
   - **Results:** add a `## Results` section before `## Limitations`. Open it with the scale
     statement from the Rules, then give:
     - **Setup facts:** model and build, vLLM version and image digest, GPU and driver, the commit
       of `main`, run dates and total runtime.
     - **Per-group table:** convergence success with 95% Wilson intervals, and McNemar p-values
       against the control group, overall and per benchmark.
     - **Paragraphs:** one short paragraph each on convergence success, intelligibility depth
       (Ultra-Strong / Strong share) and token cost (live vs sandbox), saying only what the numbers
       show. Include the deadlock and recovery rates.
     - **MSCoRe:** give the accuracy at 0.3, expected to be near 0% in every group, with the
       ROUGE-L F1 values and the reason: 50 to 250 characters against references of about 1,100.
     - **Counterfactual example:** the trial id from item 2, or the statement that none occurred.
   - **Limitations:** add the reduced scale.
6. **`paper/main.tex`:**
   - **Abstract:** replace "over 500 tasks from MSCoRe, KramaBench and MedAgentBench" with the
     actual scale, e.g. "in a reduced-scale run over 40 tasks per group from …".
   - **Experimental setup, Tasks:** rewrite the paragraph to the actual numbers: 20 MSCoRe tasks
     stratified by value chain and difficulty, 10 KramaBench tasks and 10 MedAgentBench tasks
     (one per task type), sampled with seed 0, 160 sessions. Add one sentence that the brief
     specifies 500 per group, that the repository's `ablation.toml` runs it unchanged, and that
     limited GPU time set the scale.
   - **Model and sessions:** write "Qwen2.5-7B-Instruct (AWQ 4-bit)".
   - **Serving stack:** replace the comment `% Serving stack, model build, hardware and run dates:
     added with the results.` with one sentence of those facts.
   - **Results:** write the text around the existing table and figures, in the style of the
     Experimental setup, and mention the wide intervals.
   - Do not touch the Introduction or the Architecture.
7. **`README.md` and `docs/team.md`:**
   - In the README, replace the Status section with:
     - the run name and its scale;
     - the headline numbers;
     - a link to `results/ablation-quick-qwen2.5-7b-awq/`;
     - one line that the full-scale configuration is ready to run.
   - In `docs/team.md`, mark Milestone 4 as done at reduced scale, with a link to the results.
8. **Commit and merge.** Run `ruff` and `pytest`, commit
   `exp: add the reduced-scale ablation results`, open the PR, wait for CI and squash-merge.
9. **Zip the large artifacts** (never committed; they stay on this machine):

   ```bash
   cd runs/experiments && zip -r ~/ablation-quick-qwen2.5-7b-awq-artifacts.zip \
     ablation-quick-qwen2.5-7b-awq/sessions ablation-quick-qwen2.5-7b-awq/cache.sqlite
   ls -lh ~/ablation-quick-qwen2.5-7b-awq-artifacts.zip
   ```

## Step 8: the Discussion and the PDF

The Introduction and Architecture are already in `paper/main.tex`. The Discussion is still a `%`
comment, and it belongs to the team.

1. **Ask before drafting the Discussion** (stop point 6).
   - If asked: use branch `docs/paper-discussion`, the results, and `docs/experiments.md`
     Limitations, including the reduced scale.
   - Cite only entries in `paper/references.bib`.
   - Open the PR for the team to review, and merge it only when the team has approved.
2. **Author line.** The proposal is Naitik Gupta, Malay Neema, Mayank Sharma, Yash Singh
   (alphabetical by surname). Ask whether the team has confirmed it; never change names or order
   on your own.
3. **Build the PDF** after the results PR:

   ```bash
   sudo apt install -y latexmk texlive-latex-extra    # or upload paper/ to Overleaf
   cd paper && latexmk -pdf main.tex
   ```

   - Check that no "run bb report" boxes remain and that the citations resolve.
   - Do not commit the PDF or the LaTeX build files unless asked.
   - Say where the PDF is.

## Step 9: clean up and delete this file

Do this last, after every other PR is merged. At the end, `main` is the only branch, `git status`
is clean, and this file is gone.

1. **Remove this file** on branch `chore/cleanup`:

   ```bash
   git rm instructions_to_compute.md
   git grep -n -i -E "instructions_to_compute|PLAN_RTX_5090|COMPUTE_PROMPT|rtx_5090|5090"   # must print nothing
   git grep -n -i -E "claude|anthropic|chatgpt|copilot|ai assistant|coding agent|as an ai"  # must print nothing
   git ls-files | grep -E "^(\.claude|data|runs|\.cache)/|refsol\.py|\.sqlite$"             # must print nothing
   ```

   If anything is listed, remove it (`git rm` or `git rm --cached`) or reword it.
2. **Merge.** Commit `chore: remove the compute instructions`, open a PR with a one-line
   description, wait for CI, then squash-merge and delete the branch.
3. **Leave the repository tidy:**
   - `git ls-remote --heads origin` lists only `main`, and merged local branches are deleted.
   - `git status` is clean.
   - Keep the log, the smoke and ablation runs, and the artifacts zip.
4. **Services.** Leave vLLM and FHIR running, and ask in the report whether to stop them.

## Step 10: report

The report goes in the chat, not the repository. Every number comes from `summary.json` or
`bb check`. Cover:

- **Setup:** GPU, driver, OS, vLLM version and image digest, the model build (AWQ 4-bit), the
  commit of `main` that ran, start and end times, total runtime.
- **Scale:** tasks per group and sessions in total, against the brief's 500 per group.
- **Problems:** everything fixed, with PR links, and anything left unfixed.
- **Run health:** the final `bb check` output.
- **Results,** overall and per benchmark, for each group:
  - convergence success with 95% CI;
  - deadlock and recovery rates;
  - Ultra-Strong / Strong share;
  - tokens per instance, live vs sandbox;
  - McNemar results against the control group.
- **Counterfactual example:** the trial id, or that none occurred.
- **Locations:** `results/ablation-quick-qwen2.5-7b-awq/` on `main`, the artifacts zip path and
  size, and the PDF.
- **Cleanup:** this file is removed, the checks printed nothing, and only `main` remains.
- **Still open:** for example:
  - the Discussion and the author line;
  - whether to stop the services;
  - the full-scale run (`ablation-awq.toml`, about 3 to 8 hours on this card) if GPU time turns
    up.

**Last: delete your copy of this file.** Once the report is sent, run
`rm ~/instructions_to_compute.md`; Step 9 already removed it from `main`. Keep the log.

## Time budget on the RTX 5060 Ti

These estimates come from the Mac smoke run's token counts and the card's specs:
- 448 GB/s of memory bandwidth;
- about 0.5 s of GPU time per model call with the AWQ build under load.

The smoke run in Step 5 gives the real figure.

| Stage | Time |
| --- | --- |
| Step 1–2: driver, Docker, installs, data (about 1 GB) | 1–2 h, mostly downloads; no GPU load |
| Step 3: the two PRs, including CI | 30–60 min |
| Step 4: vLLM image and the AWQ model (5.5 GB), FHIR | 20–40 min |
| Step 5: smoke run (20 sessions) and reading sessions | 30–45 min, of which 10–20 min on the GPU |
| Step 6: reduced-scale ablation (160 sessions), started by the human | **15–30 min on the GPU** |
| Steps 7–10: results, paper, cleanup | 1–2 h |

The run's length depends mostly on how often sessions deadlock:

- **Without deadlocks:** a session is a few model calls, and the response cache lets the four
  groups share them.
- **With a deadlock:** each deadlocked session in the counterfactual groups replays up to about
  150 extra calls in its sandboxes.

The full design (2,000 sessions) would take about 3 to 8 hours on this card.

## Progress

- [ ] Step 1: hardware confirmed, tools installed
- [ ] Step 2: tests, ruff, web and mock session pass; data and `refsol.py` in place
- [ ] Step 3: MedAgentBench fix merged; AWQ and reduced-scale configs merged
- [ ] Step 4: services up, build recorded
- [ ] Step 5: smoke OK, sessions read, run size confirmed
- [ ] Step 6: run script written, state logged, handed over; the human started the run
- [ ] Step 7: all planned trials done, `bb check` OK; results PR merged; artifacts zipped
- [ ] Step 8: Discussion decided, PDF built
- [ ] Step 9: cleanup PR merged, only `main` left
- [ ] Step 10: report sent, `~/instructions_to_compute.md` deleted
