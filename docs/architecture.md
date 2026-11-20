# Architecture

The spec describes four layers. Each one is a package, and the layers meet only through the
Blackboard's event log.

```
                ┌───────────────────────────── UI layer ─────────────────────────────┐
                │ web/ (React + D3)  ⇄  server/ (FastAPI REST + one WebSocket/session) │
                └───────────────▲──────────────────────────────────────────▲──────────┘
                                │ board events, cf.* progress              │ pause/step/stop
┌──────────────── control layer ┴──────────────────┐                       │
│ Scheduler (event-driven rounds)                   │◄──────────────────────┘
│   PriorityArbiter → activation queue              │
│   consensus (weighted RATIFY chains) · deadlock   │
└───────▲───────────────────────────┬───────────────┘
        │ events                    │ act(board) → Draft      commit(message, expected_version)
┌───────┴──────────── communication layer ──────────▼──────────────────────────────────────┐
│ Blackboard: event-sourced state, PXP grammar on every commit, optimistic versioning,      │
│ subscribers, stores (memory / JSON lines / Redis streams)                                 │
└───────▲───────────────────────────────────────────────────────────────────────────────────┘
        │ snapshot (read only)                           context revision, weight, resume
┌───────┴──────────── reasoning layer ──────────────────────────────────────────────────────┐
│ Agents: context → prompt (persona, lessons) → provider → turn → AGENT procedure → message  │
│ CounterfactualResolver: reflect → sandbox replay per candidate → credit → apply best       │
│ Providers: Broker (concurrency, retries) → cache → vLLM / Ollama / transformers / mock     │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

## Communication layer: `blackboard/`, `protocol/`

- **Event log.** Every change is a `BoardEvent`, and the state is the fold of the log through
  `apply_event`. Live writes and replays use that same function, so `state_at(version)` and a
  reloaded session are identical to the live board.
- **State-changing events:**
  - `task`
  - `message`
  - `status`
  - `weight`
  - `context_revision`
- **Record-only events:**
  - `activation`: the arbiter's ranked queue
  - `intervention`: everything a counterfactual resolution did
  - `tool`: an agent's tool call and its result
  - `format_error`: a rejected attempt
  - `collision`: a stale write
- **Writes.** All writes are serialized by one lock.
  - `commit(message, expected_version)` runs the PXP grammar (see [pxp.md](pxp.md)), then
    checks the version: if the board has moved since the agent read it, the write raises
    `VersionConflict` instead of overwriting.
  - Each event is persisted before subscribers are told. Subscribers run outside the lock, and
    a failing subscriber is logged, not propagated.
- **Stores:**
  - `MemoryStore` is used for tests and counterfactual sandboxes.
  - `JsonStore` writes one directory per session: `events.jsonl` is appended and fsynced per
    event, and a torn last line is ignored on load. `meta.json` is written to a temporary file
    and renamed.
  - `RedisStore` uses one stream per session.

## Control layer: `scheduler/`, `deadlock/`

- **Wake-ups.** The scheduler subscribes to the board. State-changing events wake it, and bursts
  are coalesced into one round.
- **One round:**
  1. Check consensus, then deadlock.
  2. Rank the agents.
  3. Record the activation.
  4. Let the top `max_concurrent_agents` agents draft in parallel against the same version.
  5. Commit the drafts in rank order; later drafts collide and are recorded.
- **Priority arbiter.** An agent is eligible when there is something new for it to answer. Its
  score adds:
  - a pending intervention: +10
  - has not spoken yet: +3
  - new messages since its last post: +2
  - its latest tag is not RATIFY: +1
  - a role bias for the latest tag

  Ties go to registration order, so a replay selects the same agents.
- **Consensus.** A RATIFY agrees with the message it answered. Following `in_reply_to` through
  RATIFYs leads to an anchor. Consensus holds when the agents ratifying one anchor hold at least
  τ of the voting weight (default 0.75) and there are at least two of them.
- **Deadlock** (within the current epoch, i.e. since the last applied intervention):
  - a REJECT;
  - three REFUTEs in a row;
  - six messages with no new prediction.
- **`RunControl`** pauses, steps or stops a session across all of its schedulers. `pace` slows
  rounds down for viewing.

## Reasoning layer: `agents/`, `llm/`, `counterfactual/`

- **Agents.** An agent builds its context from the board:
  - task, options, answer format and public context;
  - its private evidence;
  - the peer message and its own previous position;
  - the history (older messages clipped);
  - its lessons and voting weight.

  It renders the system prompt (persona from `llm/prompts/matrix.json`, plus lessons) and the
  turn prompt, and sends them with a JSON schema built for the task. With listed options, the
  prediction becomes an enum. The provider's answer is a turn; the AGENT procedure assigns the
  tag (see [pxp.md](pxp.md)), and the grammar checks it. Tools (KramaBench's `list_files` and
  `python`, MedAgentBench's `fhir_get`) are called before the agent posts, and are recorded
  after the commit.
- **Providers.**
  - `vllm` / `openai` (OpenAI-compatible) and `ollama` use constrained decoding.
  - `hf` runs transformers in process, with a batching worker thread.
  - `mock` applies deterministic rules, for tests and offline runs.
  - `Broker` bounds the requests in flight and retries. The SQLite cache makes reruns free, and
    lets the ablation groups share their calls up to the first deadlock.
- **Counterfactual layer.** See [counterfactual.md](counterfactual.md).

## UI layer: `server/`, `web/`

- **Server.** It runs each session in a worker thread and streams over one WebSocket per
  session: board events, the sandbox's `cf.*` progress, and the result. A late subscriber gets
  the backlog first, then live messages, each exactly once. REST endpoints serve the catalog,
  the providers, sessions, events, `state_at`, control and experiment summaries. See
  [api.md](api.md).
- **UI.** The UI folds the same event log with a TypeScript `applyEvent`, which is tested
  against states produced by the Python board. See [../web/README.md](../web/README.md) for
  the views.

## One session (`session.py`)

```
Session.run():
    loop:
        Scheduler(board, agents, arbiter, config, pending, control).run()
        if DEADLOCK and some agents are counterfactual-capable and interventions remain:
            CounterfactualResolver.intervene(board, agents, cf_agents)
            if applied: pending = {agent}; continue      # the board is RUNNING again
        break
    → SessionResult: status, answer, score, intelligibility (whole session and after the
      intervention), tokens per phase, interventions, collisions, format errors
```
