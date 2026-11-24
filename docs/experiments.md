# Experiments

## Question

Does giving a share of the agents counterfactual capability change how often a PXP blackboard
team converges on an accurate answer, how intelligible its sessions are, and what it costs in
tokens?

## Design (`experiments/configs/ablation.toml`)

| Group | Counterfactual-capable agents |
|---|---|
| Control | 0 of 3 |
| A | 1 of 3 (33%) |
| B | 2 of 3 (67%) |
| C | 3 of 3 (100%) |

- **Trials.** 500 trials per group: 300 MSCoRe, 100 KramaBench and 100 MedAgentBench, sampled
  with seed 0. That is 2,000 sessions in all.
- **Pairing.** Every task runs in every group, so groups are compared on the same tasks.
- **Rotation.** In groups A and B, which agents are capable rotates with the trial index, so
  each role is capable equally often.
- **Model.** Qwen2.5-7B-Instruct served by vLLM, temperature 0, seed 0, constrained JSON output.
- **Reported run.** The results below come from a reduced-scale run of this design (25 tasks
  per group) on a Mac with Ollama; see [Results](#results).
- **Session.**

  | Setting | Value |
  |---|---|
  | message budget | 12 |
  | k (REJECT allowed from) | 3 |
  | τ (consensus threshold) | 0.75 |
  | interventions | at most 2 |
  | apply | prompt change and voting weight |
  | tool calls | 4 per turn |

- **Cache.** The SQLite response cache lets the four groups share every model call up to the
  first deadlock, since nothing differs before it. Token costs are still counted per group as
  if each group had run alone; `cached_calls` is recorded separately.

## Benchmarks and how they are adapted

| Benchmark | Sample | Team (prompt matrix) | Answer | Accurate when |
|---|---|---|---|---|
| MSCoRe (value-chain QA, Chinese) | 300, stratified by chain × difficulty | three stage experts per chain | free-form, ≤ ~500 characters | ROUGE-L F1 ≥ 0.3 (also reported at 0.2 and 0.4) |
| KramaBench (data lakes) | 100 of 104 | data engineer, analyst, verifier, with `list_files` and sandboxed `python` | per answer type | KramaBench's metric: exact types must match; approximate ≥ 0.9 |
| MedAgentBench (FHIR) | 100, 10 per task type | retriever, clinician, safety reviewer, with `fhir_get` | `{"answer": [...], "posts": [...]}` | the official `refsol` grader returns true |

**Adaptation choices that affect results:**
- **MSCoRe answers are length-capped**, so the prompts stay within the context window; the
  references are long essays. ROUGE-L F1 is therefore lower than for unconstrained single-model
  answers. It is the same for every group, so group comparisons are unaffected.
- **KramaBench `string_approximate` answers** (10 of the 100) need a paraphrase judge. Without
  one configured, they are scored by ROUGE-1 and labelled that way in each trial's `score.detail`.
- **MedAgentBench POSTs** are graded from the transcript, as in the original harness. The team's
  agreed prediction is converted into that transcript.

## Metrics (`bb report`)

| Metric | Definition |
|---|---|
| Convergence success | consensus within the message budget **and** an accurate answer (95% Wilson interval) |
| Consensus, accuracy | the two parts separately |
| Deadlocked | sessions that deadlocked at least once |
| Recovered | deadlocked sessions that still reached consensus |
| Intelligibility depth | share of sessions that are Ultra-Strong, Strong, One-Way or None, whole session (Mestha et al. Def. 1–2, see [pxp.md](pxp.md)); the level after the last intervention is recorded per trial as our addition |
| Token cost | mean prompt + completion tokens per instance, live board and sandbox separately (95% bootstrap interval) |
| Paired test | exact McNemar on convergence success, each group against control, per benchmark |

Each trial line in `trials.jsonl` records:
- the group and the counterfactual-capable agents;
- status, answer and score;
- interventions and branches;
- message, collision and format-error counts;
- intelligibility (per agent and per session);
- token usage per phase;
- runtime.

## Running

The steps for the GPU machine are in [../scripts/gpu_runbook.md](../scripts/gpu_runbook.md).
Offline, `bb ablate experiments/configs/mock-synthetic.toml` runs the same 4 × 500 design on
synthetic tasks with the deterministic mock in about 10 seconds. Its numbers describe the mock's
rules, not language models, and are only a pipeline check.

## Results

Run `ablation-quick-ollama-qwen2.5-7b`, files in
[`results/ablation-quick-ollama-qwen2.5-7b/`](../results/ablation-quick-ollama-qwen2.5-7b/).

**Scale.** This is a reduced-scale run: 25 tasks per group (10 MSCoRe, 5 KramaBench and 10
MedAgentBench, one per task type), 100 sessions in all. The brief specifies 500 tasks per group
(2,000 sessions). Only a laptop was available for the final run, and the full design would take
many hours on it. `ablation.toml` (vLLM) and `ablation-ollama.toml` run the full design
unchanged. At this size the intervals are wide.

| Setup | |
|---|---|
| model | Qwen2.5-7B-Instruct, 4-bit (Q4_K_M), served by Ollama 0.40.3 with 4 parallel slots and an 8,192-token context |
| machine | Apple M5, 16 GB, macOS 27.0.1; FHIR server in Docker 29.7.2 under x86 emulation |
| config | `experiments/configs/ablation-quick-ollama.toml`, commit `45c0edb` of `main` |
| run | 24 Nov 2026, 22:45 to 23:23 (37 min) |
| health | `bb check`: 100 of 100 trials; no failed sessions, format errors, grader errors or judge fallbacks |

**Convergence success** with 95% Wilson intervals. The four groups gave the same result on every
task:

| Benchmark | n | Control (0%) | A (33%) | B (67%) | C (100%) |
|---|---|---|---|---|---|
| MSCoRe | 10 | 0.00 [0.00, 0.28] | 0.00 [0.00, 0.28] | 0.00 [0.00, 0.28] | 0.00 [0.00, 0.28] |
| KramaBench | 5 | 0.20 [0.04, 0.62] | 0.20 [0.04, 0.62] | 0.20 [0.04, 0.62] | 0.20 [0.04, 0.62] |
| MedAgentBench | 10 | 0.30 [0.11, 0.60] | 0.30 [0.11, 0.60] | 0.30 [0.11, 0.60] | 0.30 [0.11, 0.60] |
| All | 25 | 0.16 [0.06, 0.35] | 0.16 [0.06, 0.35] | 0.16 [0.06, 0.35] | 0.16 [0.06, 0.35] |

Every exact McNemar test against the control group, overall and per benchmark, has no discordant
pairs (b = c = 0, p = 1).

- **Convergence.** Every session in every group reached consensus in 4 messages: an INIT and then
  a RATIFY from each of the other two agents. Convergence success therefore equals accuracy. No
  session deadlocked (the deadlock and recovery rates are 0 in every group), so no counterfactual
  intervention ran, and the final answers were the same in all four groups on all 25 tasks. The
  run shows no effect of the share of counterfactual-capable agents, because the situation they
  act on never arose.
- **Intelligibility depth.** Every session is Strong; none is Ultra-Strong, One-Way or None.
  Ultra-Strong needs at least one REVISE, and every reply ratified the opening message.
- **Token cost.** Mean tokens per instance on the live board, over all tasks: 8,869 (0%), 8,758
  (33%), 8,886 (67%) and 8,867 (100%); per benchmark about 3,593 for MSCoRe, 8,960 for
  KramaBench and 13,823 to 14,142 for MedAgentBench. Sandbox tokens are zero, since no replay ran.
  The small MedAgentBench differences come from the FHIR server, which gives every search bundle a
  new id: later groups saw slightly different tool results and made those model calls again
  instead of reading them from the cache.
- **MSCoRe.** Accuracy at the 0.3 ROUGE-L threshold is 0 in every group. The answers are short (49
  to 91 characters, median 65) against long reference essays: mean ROUGE-L precision is 0.69 but
  recall 0.04, so F1 averages 0.08 (at most 0.12).
- **KramaBench and MedAgentBench.** KramaBench solved 1 of 5 tasks (`wildfire-easy-15`).
  MedAgentBench solved 3 of 10 (task types 4, 5 and 9), with the POST functions listed in the
  answer format.
- **Counterfactual example.** None: no session in the 100% group deadlocked. The intervention path
  is shown by the mock session (`bb run --cf analyst`) and the tests, not by this run.

## Limitations

- **Model.** One model family at one size. Results may not carry over to larger or
  instruction-tuned-for-debate models.
- **Judgments.** The model makes the explanation-agreement and reasoning-change judgments
  itself. The tag rule is applied exactly, but the judgments behind it are only as good as the
  model.
- **Data.** The MSCoRe items were generated with GLM-4 and expert-reviewed (see the dataset
  card). The KramaBench and MedAgentBench samples are 100 tasks each, so per-benchmark intervals
  are wide.
- **Scale of the reported run.** 25 tasks per group (100 sessions) instead of the specified 500
  (2,000), for lack of compute time. Per-benchmark intervals are up to 58 points wide, and
  KramaBench has only 5 tasks.
- **Build of the reported run.** A 4-bit (Q4_K_M) build through Ollama on a laptop, not the bf16
  vLLM build of the design. Ollama does not guarantee identical outputs across runs at
  temperature 0.
- **No deadlocks.** No session deadlocked in the reported run, so it cannot show whether
  counterfactual agents help. It shows that the pipeline runs end to end, and that without
  deadlocks the groups behave the same.
