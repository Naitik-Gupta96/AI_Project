# Architecture

Status of each component: [README.md#project-status](README.md#project-status).

## Components and data flow

```
pipeline.run_task(task, cf_agents, provider)
│
├─ Blackboard.initialize_task(question, {options})        public task info only
├─ build_team(task, provider)                             each agent gets its own evidence
├─ Scheduler(board, agents, PriorityPolicy, config).run()
│     loop: policy.select(context) → agent.act(board) → board.publish_message(msg)
│           → detect_consensus → detect_deadlock
│
└─ if DEADLOCK: CounterfactualResolver.resolve(...)
      for each message by a counterfactual-capable agent, latest first:
          agent.reflect(task, options, full history, own message) → revised decision | None
          engine.run_counterfactual(snapshot, original, agents, Intervention(...))
              create_branch: new Blackboard, re-publish history before step k,
                             publish the revised message at step k
              replay:        a new Scheduler with the same agents/policy/config
              compare:       statuses, predictions, shared prefix, divergence step
          stop at the first branch that reaches CONSENSUS
```

The UI (`ui/adapter.py` → `frontend/app.py`), the CLI demo and the pilot
experiment all call `run_task`; none of them reimplements any of these steps.

## One agent decision

```
board ─► AgentContext ─► prompt (llm/prompts/act.md) ─► LLMProvider.generate(LLMRequest)
                                                             │ JSON text
            PXPMessage ◄─ AgentDecision ◄─ normalize ◄─ AgentDecisionParser
```

- `AgentContext`: what the agent sees (task, options, its private evidence,
  status, standing proposal, history; for reflection also the message under review).
- `AgentDecision`: what it decides (tag, prediction, explanation, confidence, metadata).
- `PXPMessage`: what is published (decision + agent id + iteration + id + timestamp).

`MockLLMProvider` reads the structured context and applies the role rules
documented in `llm/mock.py`. `OllamaProvider` sends the rendered prompt to a
local model. The agent code is identical for both. Normalization holds model
output to PXP semantics (e.g. a REFUTE must name the standing proposal).

## PXP semantics

| Tag | Meaning | Effect on the standing proposal |
|---|---|---|
| RATIFY X | I support X (or open with X) | becomes X if nothing was proposed or X differs |
| REVISE X | I replace the proposal with X | becomes X |
| REFUTE X | I object to X, the standing proposal; alternative in `metadata.alternative` | unchanged |
| REJECT | No option can be accepted | unchanged; objects to whatever stands |

The *standing proposal* is derived from history (`deadlock.stances`), not from
`BlackboardState.current_prediction`, which is simply the latest message's prediction.

## Blackboard status

```
INITIALIZED → RUNNING → CONSENSUS
                 │
                 └──→ DEADLOCK      (terminal for a run; a counterfactual uses a new board)
any → FAILED     (agent or provider error during a run)
```

`set_status` enforces these transitions; the Scheduler is the only component
that sets CONSENSUS, DEADLOCK or FAILED.

## Termination rules

- **Consensus**: every registered agent's latest message supports the current
  prediction, with at least `min_supporters` (2) supporters.
- **Deadlock**, either rule:
  - *repeated disagreement*: the standing proposal was objected to
    `max_disagreement_cycles` (2) times since it was introduced, and someone still objects;
  - *stagnation*: no never-before-seen proposal for `max_stagnant_steps` (6)
    messages while someone still does not support the proposal.
- **Budget**: `max_steps` (12) agent actions; the run stops with status RUNNING
  and `stop_reason = "max_steps"`. This is not called a deadlock.

## Isolation guarantees

- The Blackboard validates a message before changing any state.
- `HistoryEvent` is frozen; `get_history()` and `snapshot()` return copies.
- A counterfactual branch is a new Blackboard built by re-publishing history
  (with message metadata), so the Blackboard itself recomputes iteration and
  state. The original board is read only through `snapshot()`.

## Module map

| Path | Responsibility |
|---|---|
| `protocol/` | `PXPMessage`, `PXPTag`, `PXPValidator` |
| `blackboard/` | `Blackboard`, `BlackboardState`, `HistoryEvent`, `BlackboardSnapshot` |
| `tasks.py` | `DecisionTask`, `Evidence`, `flash_talk_task`, `generate_tasks` |
| `agents/` | `AgentContext`, `AgentDecision`, `BaseAgent`, role classes, `build_team` |
| `llm/` | `LLMProvider`, `MockLLMProvider`, `OllamaProvider`, parser, prompt templates |
| `scheduler/` | `Scheduler`, `RoundRobinPolicy`, `PriorityPolicy`, consensus, trace; test doubles |
| `deadlock/` | stance analysis, `detect_deadlock`, `DeadlockConfig` |
| `counterfactual/` | `CounterfactualEngine`, `Intervention`, `CounterfactualResolver` |
| `pipeline.py` | `run_task`, `RunConfig`, `PipelineRun` |
| `experiment.py` | pilot runner, results format, descriptive summary |
| `ui/` | UI data models and adapter |

Design rationale: [docs/decisions.md](docs/decisions.md).
