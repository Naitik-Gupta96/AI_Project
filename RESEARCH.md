# Research

## Question

When agents that coordinate through a shared Blackboard with structured PXP
messages deadlock, can counterfactual replay of their recorded history (an
agent revising one of its own past messages, then replaying the future)
identify the message responsible and lead the team to agreement?

## Hypotheses (not yet tested with language-model agents)

- **H1** Structured PXP messages on a shared Blackboard make the cause of a
  disagreement traceable from the history alone.
- **H2** Counterfactual replay from recorded history resolves deadlocks that
  arise from information an agent had but did not communicate.
- **H3** Giving more agents counterfactual capability resolves more deadlocks,
  at the cost of more replayed branches.
- **H4** A timeline that marks the counterfactual divergence helps people
  understand why a multi-agent run failed.

## What has been done

| Item | Status | Notes |
|---|---|---|
| Mechanism (Blackboard, PXP, scheduler, deadlock, counterfactual) | implemented, tested | see README |
| Flash Talk scenario | demonstrated | deterministic mock agents |
| Pilot over 100 synthetic tasks × 8 conditions | end-to-end pilot | [docs/evaluation.md](docs/evaluation.md) |
| LLM-agent experiments | not done | runner supports `--provider ollama` |
| Baselines (message passing, majority vote, CoT) | not done | |
| Benchmarks (KramaBench, MSCoRe, MedAgentBench) | not integrated | named in the proposal only |
| Human study for H4 | not done | |

The pilot is consistent with H2 and H3 *for rule-based agents*: recovery among
feasible deadlocks rises from 0/19 (no capable agents) to 19/19 (all three).
Because the agents follow fixed rules, these numbers show that the mechanism
works as designed. They do not test whether it helps language-model agents,
and they are not a validation of the hypotheses.

## Metrics

| Metric | Measured now? | Definition |
|---|---|---|
| Deadlock rate | yes (pilot) | share of original runs where the deadlock detector fired |
| Recovery rate | yes (pilot) | share of deadlocked runs where some counterfactual branch reached consensus; also reported only over feasible tasks |
| Best-decision rate | yes (pilot) | run ends in consensus on the best feasible option (task ground truth) |
| Iterations, branches replayed, runtime | yes (pilot) | per trial |
| Token cost | only with a model provider | recorded when the provider reports it; never estimated |
| Intelligibility | no | needs a human study; no proxy number is reported |
| Decision quality on benchmarks | no | no benchmark integrated |

## Limitations

- The agents are deterministic rules, not language models. Pilot results follow
  from those rules and from the task generator's parameters.
- Tasks are synthetic: options with role-partitioned objections and scores.
- One manual run with a 4B local model completed end to end but stayed
  deadlocked. Model behaviour is uncharacterised.
- The Blackboard is in memory; runs are single-process.
- Counterfactual search is one intervention per branch, on messages by
  counterfactual-capable agents, latest first.

## Future work

See the "planned" items in [TASKS.md](TASKS.md).
