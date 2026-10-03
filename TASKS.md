# Tasks

Status of components: [README.md#project-status](README.md#project-status). The
history of how the foundation was built is in the git log.

## Done

- [x] Blackboard + PXP protocol, validation, history, snapshots, thread safety
- [x] Agents behind one provider pipeline; deterministic mock provider with documented role rules
- [x] Optional local-model provider (Ollama) using the same prompts
- [x] Scheduler with replaceable policies, consensus and deadlock detection
- [x] Counterfactual branching, replay and comparison
- [x] Counterfactual agents: reflection → intervention → replay
- [x] End-to-end pipeline shared by UI, CLI demo and experiments
- [x] End-to-end pilot experiment with reproducible results and descriptive analysis
- [x] Streamlit UI: Flash Talk, Run Explorer, Evaluation
- [x] CLI fallback demo for the flash talk
- [x] Determinism verified across processes (tests run the demo under several `PYTHONHASHSEED` values)

## Before the flash talk

- [ ] Run `python -m pytest` and both demo commands on the presentation machine
- [ ] Take a screenshot of the CLI replay as an offline backup
- [ ] Rehearse the flow in [FLASH_TALK.md](FLASH_TALK.md) (3-4 minutes)

## After the flash talk (planned)

- [ ] LLM-agent experiments with a local model; record model, seed and token usage
      (`python experiments/run_experiment.py --provider ollama`). Check first that the
      model follows each role's instructions: in one trial run `qwen3:4b` did not.
- [ ] Baselines from the proposal: majority vote without explanations; message passing
      without a shared Blackboard
- [ ] Ablation: counterfactual replay vs. simply re-running after a deadlock
- [ ] Benchmark adaptation (KramaBench, MSCoRe, MedAgentBench): define how a benchmark
      item becomes a `DecisionTask` and where ground truth comes from
- [ ] Measure intelligibility with people (e.g. can a reader identify why a run deadlocked
      from the UI?) before claiming anything about it
- [ ] Persistence for long experiments (results files are enough for now)
