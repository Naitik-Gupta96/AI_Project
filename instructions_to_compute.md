# Instructions to compute

24 Nov 2026

These are the steps for running the AI_Project experiments on the **RTX 5060 Ti (16 GB)** machine
and finishing the project: setup, two small PRs, the smoke run, the full ablation, the results,
the paper and cleanup. **When every step below is done, this file is deleted** (Step 9).

## How to use this file

Download it outside the repository and work from that copy. Step 3 checks out a branch that is
older than this file, which would remove it from the working tree.

```bash
curl -fsSL https://raw.githubusercontent.com/Naitik-Gupta96/AI_Project/main/instructions_to_compute.md \
  -o ~/instructions_to_compute.md
```

Then work through Steps 1 to 10 in order. If someone else is running the steps, give them that
copy.

**Read first, in the repository:** `strictly_follow.md` (the project brief; follow it strictly),
`README.md`, `docs/experiments.md`, `scripts/gpu_runbook.md`, `docs/architecture.md`.

**Keep a log** outside the repository (`~/compute_log.md`). Record start and end times, commands,
PR links, numbers and problems. Step 10's report is built from it.

**Stop points.** Stop, report, and wait for an explicit answer when:

1. The GPU is not an NVIDIA card with at least 16 GB (Step 1).
2. `refsol.py` cannot be downloaded (Step 2).
3. **The smoke gate:** the smoke run is done. Report its numbers, deadlock rate and runtime
   estimate, then wait for a go (Step 5).
4. A code bug turns up during the full run (Step 6).
5. Anything would change the experimental design (Rules).
6. Before drafting any paper section the team owns (Step 8).

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
  - group fractions, sample sizes and seeds;
  - session settings: message budget, k, τ, interventions, apply mode, tool calls;
  - scoring thresholds, including MSCoRe's 0.3 ROUGE-L.

  If something forces a change, stop and ask. Parallelism (`workers`, `max_in_flight`) and vLLM
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

## Why the AWQ build on this card

Qwen2.5-7B-Instruct has 7.6 B parameters. In bf16 its weights alone take 15.2 GB, which leaves
nothing on a 16 GB card for the KV cache, the CUDA context or the display. Qwen's official 4-bit
AWQ release, `Qwen/Qwen2.5-7B-Instruct-AWQ`, needs about 5.5 GB. That leaves 7 to 8 GB of KV cache,
enough for the 24 parallel sessions of the ablation config. It is still Qwen2.5-7B-Instruct, the
spec's local 7B model. The Results and the paper state the build as "AWQ 4-bit".

The existing `smoke.toml` and `ablation.toml` name the bf16 model, so Step 3 adds AWQ copies of
them. Only the model name and the run name differ.

## Where the project stands

- **Code:** all four spec deliverables are done on `main`, PRs #1 to #16 are merged, and CI is
  green.
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
- **Still to do:** the real-model ablation and its results, the paper's Introduction,
  Architecture and Discussion (currently `%` comments in `paper/main.tex`), and cleanup.

**Decisions already taken (do not reopen):**

- The full run goes ahead even if the smoke run shows no deadlocks. The Results then report the
  null result plainly; the design is not changed to force deadlocks.
- MSCoRe runs as designed. Expect accuracy near 0% in every group: answers are 50 to 250
  characters, while references have a median of about 1,100. Report it plainly with the ROUGE-L
  values, and say why.
- The artifacts zip (session logs and cache) stays on this machine.

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

**PR 2: AWQ configs for a 16 GB GPU.** Do this on branch `exp/awq-configs` from the updated
`main`:

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
3. **`tests/experiments/test_experiments.py`:** parametrize
   `test_ollama_ablation_has_the_same_design_as_the_spec_ablation` over `ablation-ollama.toml` and
   `ablation-awq.toml`, and rename it to match. For `ablation-awq.toml`, also assert that the
   provider and the KramaBench judge name the AWQ model.
4. **`docker-compose.yml`:** change `--gpu-memory-utilization 0.90` to
   `--gpu-memory-utilization ${GPU_MEMORY_UTILIZATION:-0.90}`.
5. **`scripts/gpu_runbook.md`:**
   - **Hardware table:**
     - NVIDIA 24 GB+ uses bf16 (`smoke.toml`, `ablation.toml`).
     - NVIDIA 12 to 23 GB (e.g. RTX 5060 Ti 16 GB) uses `Qwen/Qwen2.5-7B-Instruct-AWQ`
       (`smoke-awq.toml`, `ablation-awq.toml`). Give the reason: bf16 weights alone are 15.2 GB.
     - Apple Silicon is unchanged.
   - **Start command:** replace the "copies of the configs" text with
     `MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ docker compose up -d vllm fhir`, plus a note that
     `GPU_MEMORY_UTILIZATION=0.85` helps when the card also drives a display.
   - **Stale note:** delete the paragraph that says the MedAgentBench adapter "has not been run
     against the real `refsol.py`" (#12 checked it). Keep the advice that grader errors mostly mean
     FHIR is down.
6. **`README.md`:**
   - In the layout block, list the configs as
     `ablation(-awq|-ollama).toml, smoke(-awq|-ollama).toml, mock-synthetic.toml`.
   - In "Real runs", mention the AWQ build for GPUs under 24 GB.
7. **Check, commit and merge.** Run `python -m pytest && ruff check src tests scripts`. Commit
   `exp: add AWQ run configs for GPUs under 24 GB`, open the PR, wait for CI and squash-merge.

## Step 4: start the services

1. **Pull vLLM once,** and never again until the full run is finished: one image means one build.

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

1. **Run it on the merged `main`:**

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
   `git rev-parse HEAD`: the full run uses this commit.
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
3. **STOP: the smoke gate.** Report the following, then wait for an explicit go:
   - **Numbers:** the smoke numbers per group and benchmark, copied from `summary.json`.
   - **Deadlocks:** the deadlock rate and the number of interventions in the 100% group. If both
     are 0, say plainly that the groups will probably not differ. This alone does not block the
     go (decided).
   - **Runtime estimate:** the smoke elapsed time ÷ 20 × 2,000.
     - This is a ceiling: the full run has 24 workers instead of 8, and the cache shares calls
       across four groups instead of two. Expect roughly half of it.
     - Compare it with the time budget at the end of this file.
   - **Fixes:** the PR links of any fixes.

## Step 6: the full ablation

The design is 4 groups (0, 33, 67 and 100% counterfactual-capable agents) × 500 tasks (300 MSCoRe
+ 100 KramaBench + 100 MedAgentBench) = 2,000 sessions. It runs from
`experiments/configs/ablation-awq.toml` into `runs/experiments/ablation-qwen2.5-7b-awq`. Start it
only after the go.

1. **Before starting:**
   - `git rev-parse HEAD` equals the commit from Step 5, and `git status` is clean.
   - `docker compose ps` shows vLLM and FHIR up.
   - There is enough disk: about 100 × `du -sh runs/experiments/smoke-qwen2.5-7b-awq`.
2. **Run it detached and kept awake,** and log the start time:

   ```bash
   tmux new -s ablation
   source .venv/bin/activate
   systemd-inhibit --what=sleep:idle bb ablate experiments/configs/ablation-awq.toml 2>&1 | tee -a ~/ablation.log
   ```

   On Windows (WSL2), run the same inside `tmux` but without `systemd-inhibit`; the power plan
   already prevents sleep.
3. **Freeze the setup until it finishes.** No `docker compose pull`, no driver or OS updates, no
   `git pull`, and no code changes in this checkout.
4. **If it stops** (a crash, a reboot or a service going down), bring the services back and run
   the same command again. Finished trials are kept. Never pass `--restart` unless asked.
5. **Every few hours,** run `bb check runs/experiments/ablation-qwen2.5-7b-awq` and log the
   progress line.
   - Grader errors usually mean FHIR is down. Stop with Ctrl-C, restart FHIR, then resume.
   - A code bug mid-run is a stop point: a fix would put two commits into one run.
   - If `docker compose logs vllm` keeps warning about preempted sequences, stop, set
     `workers = 16` and `max_in_flight = 32` in `ablation-awq.toml` through a PR, and resume.
     Those settings are parallelism, not design. Note it in the log.
6. **Find a counterfactual example.** After a few hundred trials, look in the 100% group for a
   deadlocked session with an applied intervention, and note its trial id for the Results.
7. **When it finishes,** log the end time and the total runtime, then run `bb check` once more.

## Step 7: the results PR

One PR, `exp/ablation-qwen2.5-7b-awq`, carries the results, the figures, the docs' Results section,
the paper's Results text and the README status. Every number in it is copied from
`summary.json`.

1. **Generate:**

   ```bash
   R=runs/experiments/ablation-qwen2.5-7b-awq
   bb check $R | tee $R/health.txt          # must end with OK
   bb report $R                             # figures/, tables/, summary.json, groups.csv
   ```

2. **Add the files:**
   - **`results/ablation-qwen2.5-7b-awq/`:** `meta.json`, `summary.json`, `groups.csv`,
     `health.txt`, `figures/`, `tables/`, and `trials.jsonl.gz` (`gzip -k trials.jsonl`). Leave out
     the `.gz` if it is over 50 MB, and say so.
   - **`paper/figures/` and `paper/tables/`:** copies of the run's `figures/` and `tables/`.
     `paper/main.tex` already includes `tables/groups.tex`, `figures/convergence.png`,
     `figures/intelligibility.png` and `figures/tokens.png`.
3. **`docs/experiments.md`:**
   - In Design, change the model line to "Qwen2.5-7B-Instruct (official AWQ 4-bit build) served by
     vLLM".
   - Add a `## Results` section before `## Limitations`:
     - **Setup facts:** model and build, vLLM version and image digest, GPU and driver, the commit
       of `main`, run dates and total runtime.
     - **Per-group table:** convergence success with 95% Wilson intervals, and McNemar p-values
       against the control group, overall and per benchmark.
     - **Paragraphs:** one short paragraph each on convergence success, intelligibility depth
       (Ultra-Strong / Strong share) and token cost (live vs sandbox), saying only what the numbers
       show. Include the deadlock and recovery rates.
     - **MSCoRe:** accuracy at 0.3 is near 0% in every group. Give the ROUGE-L F1 values and the
       reason: 50 to 250 characters against references of about 1,100.
     - **Counterfactual example:** the trial id from Step 6, or the statement that none occurred.
4. **`paper/main.tex`:**
   - In "Model and sessions", write "Qwen2.5-7B-Instruct (AWQ 4-bit)".
   - Replace the comment `% Serving stack, model build, hardware and run dates: added with the
     results.` with one sentence of those facts.
   - Write the Results text around the existing table and figures, in the style of the
     Experimental setup.
   - Do not touch the Introduction, Architecture or Discussion.
5. **`README.md` and `docs/team.md`:**
   - In the README, replace the Status section with the run name, the headline numbers and a link
     to `results/ablation-qwen2.5-7b-awq/`.
   - In `docs/team.md`, mark Milestone 4 as done, with a link to the results.
6. **Commit and merge.** Run `ruff` and `pytest`, commit
   `exp: add the ablation-qwen2.5-7b-awq results`, open the PR, wait for CI and squash-merge.
7. **Zip the large artifacts** (never committed; they stay on this machine):

   ```bash
   cd runs/experiments && zip -r ~/ablation-qwen2.5-7b-awq-artifacts.zip \
     ablation-qwen2.5-7b-awq/sessions ablation-qwen2.5-7b-awq/cache.sqlite
   ls -lh ~/ablation-qwen2.5-7b-awq-artifacts.zip
   ```

## Step 8: the team's paper sections and the PDF

Three sections of `paper/main.tex` are still one-line `%` comments, and they belong to the team.
Ask before writing any of them (stop point 6).

| Section | Material to draw on |
| --- | --- |
| Introduction | `README.md`, `docs/pxp.md`, `docs/counterfactual.md` |
| Architecture | `docs/architecture.md` |
| Discussion and limitations | the results; `docs/experiments.md` Limitations |

1. **If asked to draft them:**
   - Use branch `docs/paper-sections`, only the repository's docs and the results, and only
     citations already in `paper/references.bib`.
   - Open the PR for the team to review, and merge it only when the team has approved.
2. **Author line.** The proposal is Naitik Gupta, Malay Neema, Mayank Sharma, Yash Singh
   (alphabetical by surname). Ask whether the team has confirmed it; never change names or order
   on your own.
3. **Abstract.** Offer to add one sentence with the headline numbers.
4. **Build the PDF** after the results PR:

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
- **Problems:** everything fixed, with PR links, and anything left unfixed.
- **Run health:** the final `bb check` output.
- **Results,** overall and per benchmark, for each group:
  - convergence success with 95% CI;
  - deadlock and recovery rates;
  - Ultra-Strong / Strong share;
  - tokens per instance, live vs sandbox;
  - McNemar results against the control group.
- **Counterfactual example:** the trial id, or that none occurred.
- **Locations:** `results/ablation-qwen2.5-7b-awq/` on `main`, the artifacts zip path and size,
  and the PDF.
- **Cleanup:** this file is removed, the checks printed nothing, and only `main` remains.
- **Still open:** for example the team's paper sections, the author line, and whether to stop the
  services.

**Last: delete your copy of this file.** Once the report is sent, run
`rm ~/instructions_to_compute.md`; Step 9 already removed it from `main`. Keep the log.

## Time budget on the RTX 5060 Ti

These estimates come from the Mac smoke run's token counts and the card's specs:
- 448 GB/s of memory bandwidth;
- about 0.5 s of GPU time per model call with the AWQ build under load.

The smoke run in Step 5 gives the real figure.

| Stage | Time |
| --- | --- |
| Step 1–2: driver, Docker, installs, data (about 1 GB) | 1–2 h, mostly downloads |
| Step 3: the two PRs, including CI | 30–60 min |
| Step 4: vLLM image and the AWQ model (5.5 GB), FHIR | 20–40 min |
| Step 5: smoke run (20 sessions) and reading sessions | 30–45 min |
| Step 6: full ablation (2,000 sessions) | **3–8 h expected; up to about 24 h worst case** |
| Steps 7–10: results, paper, cleanup | 1–3 h |

The full run's length depends almost entirely on how often sessions deadlock:

- **Without deadlocks:** a session is a few model calls, and the response cache lets the four
  groups share them, so most of the GPU work is in the control group.
- **With a deadlock:** each deadlocked session in the counterfactual groups replays up to about
  150 extra calls in its sandboxes.

The estimates by deadlock rate:

- **Few deadlocks (as on the Mac):** about 3 h.
- **About a third of sessions deadlock:** 8 to 12 h.
- **Most sessions deadlock:** about a day.

Start the full run in the evening and it should be done by the next morning.

## Progress

- [ ] Step 1: hardware confirmed, tools installed
- [ ] Step 2: tests, ruff, web and mock session pass; data and `refsol.py` in place
- [ ] Step 3: MedAgentBench fix merged; AWQ configs merged
- [ ] Step 4: services up, build recorded
- [ ] Step 5: smoke OK, sessions read, go received
- [ ] Step 6: 2,000 trials finished, `bb check` OK
- [ ] Step 7: results PR merged, artifacts zipped
- [ ] Step 8: paper sections decided, PDF built
- [ ] Step 9: cleanup PR merged, only `main` left
- [ ] Step 10: report sent, `~/instructions_to_compute.md` deleted
