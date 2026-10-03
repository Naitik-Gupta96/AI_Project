# Counterfactual API

> What would have happened if one earlier reasoning step had been different?

`ai_project.counterfactual` branches a finished (or running) Blackboard,
replaces one historical message, replays the future with the same agents,
policy and configuration, and compares the two outcomes. Scheduler, consensus
and deadlock are documented in [scheduler_api.md](scheduler_api.md).

---

## Quick start

```python
from ai_project.counterfactual import CounterfactualEngine, Intervention
from ai_project.protocol import PXPTag
from ai_project.scheduler.scenarios import deadlock_scenario

scenario = deadlock_scenario()
board, _, original = scenario.run()                 # DEADLOCK on "Option A"

engine = CounterfactualEngine()
branch = engine.create_branch(board, Intervention(
    iteration=2,                                     # the critic's refutation
    tag=PXPTag.REFUTE,
    prediction="Option A",
    explanation="Option A violates C3. Option B avoids this problem.",
    metadata={"alternative": "Option B"},
    description="Critic also names Option B",
))
cf = engine.replay(branch, scenario.agents, scenario.policy, scenario.config)
comparison = engine.compare(original, branch)

comparison.original_status          # "DEADLOCK"
comparison.counterfactual_status    # "CONSENSUS"
comparison.counterfactual_prediction  # "Option B"
```

One call does the same: `engine.run_counterfactual(board, original, agents, intervention, policy=..., config=...)`.

The full Scenario C is `ai_project.counterfactual.scenarios.run_deadlock_counterfactual()`.

---

## How a branch is built (isolation guarantee)

```
original board ──snapshot()──► isolated deep copy (BlackboardSnapshot)
                                 │
                                 ▼
                       NEW Blackboard for the branch
                       1. initialize_task(same task, metadata + "counterfactual" info)
                       2. re-publish every event with iteration < branch point
                       3. publish the intervention as the branch-point message
                                 │
                                 ▼
                       Scheduler.run() on the branch board  (replay)
```

- The original board is read only through `snapshot()` and is never mutated.
  Its state, history and status are identical before and after branching and
  replay (tested).
- Each branch has its own Blackboard, so branches are isolated from each other.
- History is re-published through `publish_message`, so Person 1's Blackboard
  recomputes iteration, current prediction and latest message itself. Nothing
  bypasses validation.
- Only the branch-point message is scripted. Everything after it is produced
  by the agents reacting to the altered context.

**Limitation:** `HistoryEvent` does not store message metadata, so inherited
(pre-branch) events are re-published with empty metadata. The intervention
message carries its own metadata.

---

## `Intervention`

```python
Intervention(
    iteration: int,             # event to replace = branch point (>= 1)
    tag: PXPTag | str,
    prediction: str,
    explanation: str,
    agent_id: str | None = None,   # default: author of the replaced event
    confidence: float | None = None,
    metadata: dict = {},
    description: str = "",         # shown in the trace / UI
)
```

The published intervention message gets id `"<branch_id>-it<NNN>"` and
metadata `counterfactual: True`, `branch_id`, `replaces_message_id`.

---

## `CounterfactualEngine`

| Method | Description |
|---|---|
| `create_branch(source, intervention=None, *, branch_point=None, branch_id=None)` | `source` is a `Blackboard` or `BlackboardSnapshot`. With an intervention, its iteration is the branch point and exactly one event must exist there. Without one, `branch_point` (1 … last iteration + 1) gives a **pure replay**: events before it are inherited and the rest is re-run unchanged. Ids default to `cf-1`, `cf-2`, … |
| `replay(branch, agents, policy=None, config=None, max_steps=None)` | Runs a `Scheduler` on the branch board and stores `branch.result`. A branch can be replayed once; create another branch to replay again |
| `compare(original_result, branch)` | `BranchComparison` (branch must be replayed) |
| `run_counterfactual(source, original_result, agents, intervention=None, *, branch_point=None, policy=None, config=None)` | create + replay + compare; returns `CounterfactualOutcome(branch, result, comparison)` |
| `branches`, `get_branch(id)` | branches created by this engine |

Raises `CounterfactualError` for invalid iterations, a missing branch point,
conflicting `branch_point`/`intervention.iteration`, duplicate ids, double
replay, or comparing an un-replayed branch.

Use the **same** agents, policy and config as the original run so the only
difference is the intervention. A pure replay (`branch_point=k`, no
intervention) reproduces the original outcome exactly. This is a useful check
that agents and policy are deterministic.

---

## `CounterfactualBranch`

| Field | Meaning |
|---|---|
| `branch_id`, `branch_point` | identity |
| `intervention` | the `Intervention` (or `None` for pure replay) |
| `board` | the branch's own Blackboard |
| `source_snapshot` | isolated snapshot the branch was built from |
| `replaced_event` | original `HistoryEvent` at the branch point |
| `setup_trace` | `inherited` + `intervention` trace entries |
| `initial_state`, `initial_history` | branch state/history right after setup, before replay |
| `result` | `SchedulerResult` of the replay |

`branch.get_trace()` = setup entries followed by the replay's scheduler entries.

### Replay record: `branch.to_dict()`

```json
{
  "branch_id": "cf-1",
  "branch_point": 2,
  "intervention": {"iteration": 2, "tag": "REFUTE", "prediction": "Option A", "explanation": "...",
                   "agent_id": null, "confidence": 0.8, "metadata": {"alternative": "Option B"},
                   "description": "..."},
  "replaced_event": {"iteration": 2, "agent_id": "critic", "tag": "REFUTE",
                     "prediction": "Option A", "explanation": "...", "confidence": 0.8},
  "source": {"task": "...", "status": "DEADLOCK", "iteration": 3},
  "initial_state": { "...": "BlackboardState.to_dict() after setup" },
  "initial_history": [ "...HistoryEvent.to_dict()..." ],
  "replayed": true,
  "config": {"max_steps": 10, "consensus": {"min_supporters": 2},
             "deadlock": {"max_disagreement_cycles": 2, "max_stagnant_steps": 6},
             "seed": null, "raise_on_agent_error": false},
  "policy": {"name": "priority", "proposer": "analyst", "critic": "critic", "resolver": "specialist"},
  "trace": [ "...inherited, intervention, agent_action..., consensus..." ],
  "result": { "...": "SchedulerResult.to_dict()" }
}
```

This records the configuration/seed, initial state, event sequence, the agent
invoked and message produced at each step, state transitions (`changes`), and
the final status.

The `intervention` trace entry's `changes` field shows exactly what was
altered relative to the original event, and `details.replaced` holds the
original event.

---

## `BranchComparison`

```json
{
  "branch_id": "cf-1",
  "branch_point": 2,
  "intervention": {"...": "..."},
  "original_status": "DEADLOCK",          "counterfactual_status": "CONSENSUS",
  "original_prediction": "Option A",      "counterfactual_prediction": "Option B",
  "original_iterations": 3,               "counterfactual_iterations": 5,
  "original_deadlocked": true,            "counterfactual_deadlocked": false,
  "original_consensus": false,            "counterfactual_consensus": true,
  "status_changed": true,
  "prediction_changed": true,
  "shared_prefix": 1,
  "divergence_iteration": 2,
  "summary": "Changing iteration 2 (critic REFUTE 'Option A'): original DEADLOCK on 'Option A' after 3 iteration(s); counterfactual CONSENSUS on 'Option B' after 5 iteration(s)."
}
```

- `*_prediction` is the standing proposal at the end (agreed or contested).
- `shared_prefix` counts leading history events that are identical in both
  runs (agent, tag, prediction, explanation, confidence).
- `divergence_iteration` is the first iteration that differs (`null` if the
  histories are identical).

---

## Scenario C (the flash-talk demo)

```
ORIGINAL                                   COUNTERFACTUAL (branch point = 2)
1 analyst    RATIFY Option A               1 analyst    RATIFY Option A   (inherited)
2 critic     REFUTE Option A               2 critic     REFUTE Option A + "Option B avoids this"  (changed)
3 specialist REFUTE Option A               3 specialist REVISE Option B   (sees the alternative)
-> DEADLOCK (2 disagreement cycles)        4 critic     RATIFY Option B
                                           5 analyst    RATIFY Option B
                                           -> CONSENSUS on Option B
```

This scenario uses the scheduler's scripted test-double agents and a hand-written
intervention. The Flash Talk demo produces the same trajectory with the real role
agents, where the critic's own reflection generates the intervention (see below).
Either way it demonstrates the mechanism; it is not an empirical result.

---

## Determinism

- No randomness, network access or LLM calls in the scheduler, policies, mock
  agents or engine. `SchedulerConfig.seed` is recorded for when randomized
  policies are added.
- Traces contain no wall-clock timestamps, so two runs of the same scenario
  produce identical traces and comparisons (tested). `HistoryEvent.timestamp`
  values naturally differ between runs.
- Replay is only as deterministic as the agents. The role agents with
  `MockLLMProvider` and the `RuleBasedMockAgent` test doubles are pure
  functions of the board, so runs are identical across processes (a test runs
  the Flash Talk demo under three `PYTHONHASHSEED` values and compares output).
  A model-backed provider (`OllamaProvider`) is not guaranteed deterministic.
- Inherited events are re-published with their original message metadata
  (e.g. a named alternative), so a pure replay reproduces the original run.

---

## Counterfactual agents: `CounterfactualResolver` (`counterfactual/resolver.py`)

Scenario C above scripts the intervention. In the full system the intervention
comes from the agents themselves:

```python
from ai_project.pipeline import run_task
from ai_project.tasks import flash_talk_task

run = run_task(flash_talk_task(), cf_agents=("critic",))
run.original.status            # "DEADLOCK"
for r in run.resolution.reflections:
    r.agent_id, r.iteration, r.revised, r.recovered
run.final.status               # "CONSENSUS" (the recovering branch's result)
```

After a deadlock, each *counterfactual-capable* agent is shown the full run and
one of its own past messages (`BaseAgent.reflect`) and answers with the message
it would have sent instead, or "no change". It may use what the run made
public (which options were refuted) and its own evidence, never another
agent's private evidence. Each revision becomes an `Intervention`; the engine
branches the original at that step and replays with the same agents, policy and
config. Candidates are tried latest message first (the smallest change to
history) and resolution stops at the first branch that reaches CONSENSUS.
Every attempted branch is kept in `Resolution.reflections`. A replay that
fails (e.g. a provider error) is recorded as a FAILED branch, not raised.
