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

## Limitations

- **Model.** One model family at one size. Results may not carry over to larger or
  instruction-tuned-for-debate models.
- **Judgments.** The model makes the explanation-agreement and reasoning-change judgments
  itself. The tag rule is applied exactly, but the judgments behind it are only as good as the
  model.
- **Data.** The MSCoRe items were generated with GLM-4 and expert-reviewed (see the dataset
  card). The KramaBench and MedAgentBench samples are 100 tasks each, so per-benchmark intervals
  are wide.
