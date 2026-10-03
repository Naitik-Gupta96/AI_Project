# Scheduler, Consensus and Deadlock API

Person 3 layer: decides which agent acts next, detects consensus and deadlock,
and records a structured trace. Counterfactual branching/replay is documented
in [counterfactual_api.md](counterfactual_api.md).

Everything here uses only the public Blackboard API (`get_state`,
`get_history`, `get_iteration`, `get_latest_message`, `publish_message`,
`set_status`, `snapshot`). A test enforces that no private Blackboard
attribute is accessed.

```
src/ai_project/scheduler/       Scheduler, policies, registry, consensus, trace,
                                deterministic mock agents, scenarios
src/ai_project/deadlock/        stance analysis + deadlock detection
src/ai_project/counterfactual/  branching, replay, comparison
```

---

## Quick start

```python
from ai_project.blackboard import Blackboard
from ai_project.scheduler import PriorityPolicy, Scheduler, SchedulerConfig

board = Blackboard()
board.initialize_task("Choose Option A or Option B")

scheduler = Scheduler(
    board,
    {"analyst": analyst, "critic": critic, "specialist": specialist},
    policy=PriorityPolicy(proposer="analyst", critic="critic", resolver="specialist"),
    config=SchedulerConfig(max_steps=10),
)
result = scheduler.run()

result.status            # "CONSENSUS" | "DEADLOCK" | "FAILED" | "RUNNING"
result.final_prediction  # agreed prediction (consensus) or contested one (deadlock)
scheduler.get_trace()    # list[dict] for the UI
```

Ready-made deterministic runs:

```python
from ai_project.scheduler.scenarios import consensus_scenario, deadlock_scenario
board, scheduler, result = deadlock_scenario().run()   # -> DEADLOCK
```

---

## Agent contract

The Scheduler accepts any object with:

```python
agent.agent_id: str
agent.act(board: Blackboard) -> PXPMessage   # the Scheduler publishes it
```

This is exactly Person 2's `BaseAgent.act(board)` contract, so `AnalystAgent`,
`CriticAgent` and `SpecialistAgent` plug in directly. The structural type is
`ai_project.scheduler.SchedulableAgent`.

Rules enforced by the Scheduler:

- the returned message's `agent_id` must equal the agent's `agent_id`;
- the message goes through `board.publish_message`, so Person 1's validator
  applies (invalid messages never touch the board);
- an exception from `act` or `publish_message` sets the board to `FAILED` and
  is recorded in the trace (or re-raised if `raise_on_agent_error=True`).

For deterministic replay, an agent's decision should depend only on the board.

### AgentRegistry

```python
AgentRegistry({"analyst": a, "critic": c})   # mapping: key must equal agent.agent_id
AgentRegistry([a, c])                        # iterable
registry.agent_ids                           # ("analyst", "critic"), registration order
registry.get("critic")
```

Registration order breaks ties in every policy, which keeps scheduling deterministic.

---

## Scheduler

```python
Scheduler(board, agents, policy=None, config=None)
```

| Argument | Meaning |
|---|---|
| `board` | Initialized `Blackboard` (raises `BlackboardNotInitializedError` otherwise) |
| `agents` | `AgentRegistry`, `{agent_id: agent}` or iterable of agents (at least one) |
| `policy` | `SchedulingPolicy`; default `RoundRobinPolicy()` |
| `config` | `SchedulerConfig`; default `SchedulerConfig()` |

### What one `step()` does

1. If the board is `CONSENSUS`, `DEADLOCK` or `FAILED`, return `None`.
2. If the board is `INITIALIZED`, set it to `RUNNING`.
3. Check consensus, then deadlock. If either holds, set the status, record
   the trace entry, and return it.
4. Ask the policy which agent acts (`Selection`: agent id, rule, reason).
5. Call `agent.act(board)` and `board.publish_message(message)`.
6. Record an `agent_action` trace entry, then check consensus/deadlock again.

### Methods and properties

| Member | Returns |
|---|---|
| `step()` | `TraceEntry` produced, or `None` if already terminal |
| `run(max_steps=None)` | `SchedulerResult`; runs until terminal or `max_steps` agent actions (default `config.max_steps`). On budget exhaustion the board stays `RUNNING`, `stop_reason == "max_steps"`, and `run()` can be called again |
| `get_status()` | JSON-safe dict (see UI contract) |
| `get_trace()` | `list[dict]` of trace entries |
| `get_trace_entries()` | `list[TraceEntry]` |
| `get_result()` | `SchedulerResult` for the board right now |
| `check_consensus()` | `ConsensusResult` (no side effects) |
| `check_deadlock()` | `DeadlockReport` (no side effects) |
| `finished` | `True` once status is CONSENSUS / DEADLOCK / FAILED |
| `stop_reason` | `"consensus"`, `"deadlock"`, `"error"`, `"max_steps"` or `None` |
| `steps` | agent actions performed by this scheduler |
| `board`, `registry`, `policy`, `config` | the configured objects |

### SchedulerConfig

```python
SchedulerConfig(
    max_steps=20,                        # default action budget for run()
    consensus=ConsensusConfig(min_supporters=2),
    deadlock=DeadlockConfig(max_disagreement_cycles=2, max_stagnant_steps=6),
    seed=None,                           # recorded only; built-ins are deterministic
    raise_on_agent_error=False,
)
```

The config is serialized into every result (`result.config`) so a run can be reproduced.

---

## Scheduling policies (replaceable)

```python
class SchedulingPolicy(ABC):
    name: str
    def select(self, context: SchedulingContext) -> Selection: ...
    def describe(self) -> dict: ...
```

`SchedulingContext` gives the policy `state`, `history` (tuple), `agent_ids`
(registration order), `step`, plus `last_event` / `last_agent`.
`Selection(agent_id, rule, reason)` explains the choice; `reason` appears in
the trace.

The built-in policies are **stateless**: the choice depends only on the context.
That is what makes counterfactual replay deterministic.

### `RoundRobinPolicy()`

The agent after the last speaker, in registration order (first agent if nobody
has spoken yet).

### `PriorityPolicy(proposer, critic, resolver)`

Rules are checked in order. A rule is skipped if its agent is not registered or
just acted (no agent speaks twice in a row while others are available).

| # | Rule (`selection.rule`) | Condition | Selected |
|---|---|---|---|
| 1 | `no_proposal` | nothing proposed yet | `proposer` |
| 2 | `after_disagreement` | last message is REFUTE / REJECT | `resolver` |
| 3 | `after_new_proposal` | last message introduced a new proposal | `critic` |
| 4 | `pending_agreement` | some agent's latest stance does not support the standing proposal (silent agents included) | first such agent |
| 5 | `fallback` | none of the above | round robin after last speaker |

To experiment with a different policy (confidence-based, randomized with an
explicit seed, learned), subclass `SchedulingPolicy` and pass it to the
Scheduler. Nothing else changes.

---

## Shared vocabulary (`ai_project.deadlock.stances`)

| Term | Definition |
|---|---|
| support | `RATIFY X` or `REVISE X` supports X |
| objection | `REFUTE X` objects to X; `REJECT` objects to whatever proposal is standing |
| standing proposal | prediction of the latest RATIFY/REVISE whose prediction differs from the previous proposal. Objections never change it |
| proposal epoch | the history since the standing proposal was introduced |
| latest stance | an agent's most recent message |

Helpers: `current_proposal(history)`, `proposal_epoch(history)`,
`latest_stances(history)`, `objections_in_epoch(history)`,
`last_novel_proposal_index(history)`, `supports`,
`objects_to`.

---

## Consensus — `detect_consensus(state, history, config=None, agent_ids=None)`

Let **X = `state.current_prediction`**. Consensus on X holds if and only if:

1. X is non-empty,
2. **every participant's latest message supports X** (RATIFY X or REVISE X), so
   no unresolved REFUTE/REJECT and nobody backing a different prediction, and
3. at least `config.min_supporters` (default 2) distinct agents support X.

Participants are `agent_ids` when given, otherwise every agent in history. The
Scheduler always passes its registry, so **every registered agent must agree**
(a silent agent blocks consensus).

Returns `ConsensusResult(reached, prediction, supporters, blockers, reason)`.

---

## Deadlock — `detect_deadlock(history, config=None)`

Two rules, checked in order, both thresholds in `DeadlockConfig`:

1. **`repeated_disagreement`**: the standing proposal has been objected to at
   least `max_disagreement_cycles` times (default **2**) since it was introduced,
   **and** at least one agent's latest stance still objects to it. Each
   objection against an unchanged proposal is one *disagreement cycle*.
2. **`stagnation`**: no *novel* proposal (a prediction never proposed before)
   for `max_stagnant_steps` messages (default **6**, `None` disables) while
   some agent still does not support the standing proposal. Re-proposing an
   earlier prediction is not progress, so proposals that oscillate
   A -> B -> A -> B (a livelock) are caught here.

A new proposal (RATIFY/REVISE with a different prediction) starts a new epoch
and resets the disagreement-cycle count; only a novel proposal resets the
stagnation count. Objections that were later withdrawn (the objector
ratified) do not deadlock.

Examples with `max_disagreement_cycles=2`:

```
analyst RATIFY A, critic REFUTE A, specialist REFUTE A      -> DEADLOCK at 3
analyst RATIFY A, critic REFUTE A, analyst RATIFY A,
critic REFUTE A                                             -> DEADLOCK at 4 (not at 2)
analyst RATIFY A, critic REFUTE A, specialist REVISE B      -> no deadlock (new epoch)
a REVISE A, b REVISE B, a REVISE A, ... (8 messages)        -> DEADLOCK (stagnation, threshold 6)
```

Returns `DeadlockReport(deadlocked, rule, reason, contested_prediction,
disagreement_cycles, stagnant_steps, objecting_agents, dissenting_agents)`.
`DeadlockDetector(config).detect(history)` is the configured equivalent.

---

## Scheduler test doubles and scenarios

These exist to test the scheduler, deadlock detector and counterfactual engine
in isolation. The demo and experiments use the real role agents
(`ai_project.agents`, see [agents_api.md](agents_api.md)).

`RuleBasedMockAgent(agent_id, role, preferred, objections, suggests, adopts_alternatives, confidence)`
is a test double with explicit rules (first match wins):

1. `open`: no proposal yet -> RATIFY `preferred` (REJECT if none)
2. `adopt_alternative`: if `adopts_alternatives` and the latest message is an
   objection whose metadata names an `alternative` it does not object to -> REVISE to it
3. `object`: standing proposal in `objections` -> REFUTE it (offering `suggests`)
4. `endorse`: otherwise RATIFY the standing proposal

No randomness, no hidden state. Message ids are `"<agent_id>-it<NNN>"`.

`ai_project.scheduler.scenarios`:

| Factory | Outcome |
|---|---|
| `consensus_scenario()` | analyst proposes B, critic and specialist ratify -> CONSENSUS at iteration 3 |
| `deadlock_scenario()` | analyst proposes A, critic and specialist refute -> DEADLOCK at iteration 3 |
| `alternating_deadlock_scenario(n)` | analyst/critic RATIFY/REFUTE ping-pong -> DEADLOCK at iteration 2n |

`Scenario.run()` returns `(board, scheduler, result)`; `Scenario.describe()` is JSON-safe.

---

## UI contract (Person 4)

All structures below are JSON-serializable. No timestamps appear in the trace,
so identical runs produce identical traces.

### `scheduler.get_status()`

```json
{
  "status": "DEADLOCK", "finished": true, "stop_reason": "deadlock",
  "iteration": 3, "steps": 3,
  "current_prediction": "Option A", "current_proposal": "Option A",
  "last_agent": "specialist",
  "agents": ["analyst", "critic", "specialist"],
  "policy": {"name": "priority", "proposer": "analyst", "critic": "critic", "resolver": "specialist"},
  "consensus": {"reached": false, "prediction": "Option A", "supporters": ["analyst"], "blockers": ["critic", "specialist"], "reason": "..."},
  "deadlock": {"deadlocked": true, "rule": "repeated_disagreement", "...": "..."},
  "error": null
}
```

### Trace entry (`scheduler.get_trace()[i]`)

| Field | Meaning |
|---|---|
| `step` | board iteration the entry refers to |
| `kind` | `agent_action`, `consensus`, `deadlock`, `max_steps`, `error`; counterfactual branches add `inherited`, `intervention` |
| `event` | PXP tag for messages; `CONSENSUS` / `DEADLOCK` / `MAX_STEPS` / `ERROR` otherwise |
| `agent` | acting agent (null for status entries) |
| `prediction`, `explanation`, `confidence`, `message_id` | the published message |
| `reason` | why this agent was selected, or why the status was set |
| `policy` | policy name |
| `status` | board status after the entry |
| `changes` | `{field: {"before", "after"}}` for `iteration`, `status`, `current_prediction`, `proposal` |
| `details` | `{"rule": ...}` for actions; full `consensus` / `deadlock` report for status entries |

Example (from `deadlock_scenario`):

```json
{
  "step": 2, "kind": "agent_action", "event": "REFUTE", "agent": "critic",
  "prediction": "Option A",
  "explanation": "Option A is unacceptable: it violates constraint C3 (runs must be reproducible).",
  "confidence": 0.8, "message_id": "critic-it002",
  "reason": "New proposal 'Option A' from analyst; critic reviews it",
  "policy": "priority", "status": "RUNNING",
  "changes": {"iteration": {"before": 1, "after": 2}},
  "details": {"rule": "after_new_proposal"}
}
```

### `SchedulerResult.to_dict()`

Keys: `status`, `stop_reason`, `final_prediction`, `iterations`, `steps`,
`consensus_reached`, `deadlocked`, `consensus` (ConsensusResult dict),
`deadlock` (DeadlockReport dict), `trace` (list of entries), `state`
(`BlackboardState.to_dict()`), `history` (list of `HistoryEvent.to_dict()`),
`config`, `policy`, `error`.

### Status values

`INITIALIZED`, `RUNNING`, `CONSENSUS`, `DEADLOCK`, `FAILED`: Person 1's
`BlackboardStatus`. The Scheduler only uses its valid transitions
(`INITIALIZED -> RUNNING`, `RUNNING -> CONSENSUS | DEADLOCK | FAILED`).

---

## Demo

```bash
python examples/scheduler_demo.py                  # test doubles + scripted intervention
python examples/scheduler_demo.py --json run.json  # also export all structured results
```
