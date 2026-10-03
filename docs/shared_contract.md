# Contract Between Layers

Each layer talks to the next only through the interfaces below. Details are in
the per-layer API documents.

```
tasks ─► agents ─► Blackboard ◄─ Scheduler ◄─ counterfactual ◄─ pipeline ◄─ ui / experiment
```

## Blackboard (public API only)

Everything outside `blackboard/` uses only: `initialize_task`, `publish_message`,
`get_state`, `get_history`, `get_iteration`, `get_latest_message`,
`set_status`, `snapshot`. A test enforces that the scheduler and
counterfactual packages access no private attribute. `get_state()`,
`get_history()`, `get_latest_message()` and `snapshot()` return copies;
`HistoryEvent` is frozen. [blackboard_api.md](blackboard_api.md)

## Agent → Scheduler

Any object with `agent_id: str` and `act(board) -> PXPMessage` can be scheduled
(`scheduler.registry.SchedulableAgent`). The agent returns a message; the
Scheduler publishes it. Agents that also implement
`reflect(task, options, history, own_event) -> AgentDecision | None` can be
counterfactual-capable. [agents_api.md](agents_api.md)

## Message semantics

`prediction` always names the option a tag is about. REFUTE names the standing
proposal; an alternative goes in `metadata["alternative"]`. Consensus, deadlock
and scheduling policies rely on this ([ARCHITECTURE.md](../ARCHITECTURE.md#pxp-semantics)).

## Scheduler → callers

`Scheduler(board, agents, policy, config).run() -> SchedulerResult` with status,
stop reason, final prediction, consensus and deadlock reports, a trace without
wall-clock timestamps, and serialized state/history/config.
[scheduler_api.md](scheduler_api.md)

## Counterfactual → callers

`CounterfactualEngine.run_counterfactual(source, original, agents, intervention, ...)`
→ `CounterfactualOutcome(branch, result, comparison)`.
`CounterfactualResolver.resolve(board, original, agents, cf_agents, ...)` → `Resolution`.
[counterfactual_api.md](counterfactual_api.md)

## Pipeline → UI and experiments

`pipeline.run_task(task, cf_agents, provider, config) -> PipelineRun`. The UI
adapter turns it into views ([ui_api.md](ui_api.md)); the experiment turns it
into trial records ([evaluation.md](evaluation.md)).

## Rules

- Never mutate a board you did not create; branch it.
- Never publish a message on behalf of another agent; the Scheduler rejects it.
- Record configuration with results (`describe()` / `to_dict()` exist for this).
- Label results by mode (deterministic mock, local model, end-to-end pilot).
