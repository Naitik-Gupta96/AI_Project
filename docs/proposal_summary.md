# Proposal Summary

What the original proposal set out to build. What exists today is tracked in
[README.md#project-status](../README.md#project-status); this page does not track status.

## Core idea

Replace long direct message-passing chains with a globally shared, structured
Blackboard on which agents communicate through the PXP protocol (RATIFY,
REVISE, REFUTE, REJECT), every message carrying a prediction and an explanation.

## Layers

1. **PXP-governed Blackboard**: central, thread-safe state with validated
   structured messages and a full history.
2. **Deterministic scheduler**: controls agent turns and the task lifecycle.
3. **Retrospective counterfactual reasoning**: detect deadlock from interaction
   patterns, branch history, and replay alternatives to resolve it.
4. **Visualization**: show Blackboard state, the interaction timeline and
   counterfactual divergence.

## Evaluation proposed

- Metrics: deadlock rate, resolution time, decision quality, traceability,
  counterfactual effectiveness.
- Benchmarks named: KramaBench, MSCoRe, MedAgentBench. None is integrated yet.
- Baselines named: message-passing systems (e.g. CAMEL, AutoGen), single-agent
  chain of thought, majority voting.

## Flash Talk target (Oct 6)

A working vertical slice: agents → Blackboard → structured PXP interaction →
deadlock → counterfactual resolution. See [FLASH_TALK.md](../FLASH_TALK.md).
