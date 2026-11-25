# Server API

`bb serve` (default http://127.0.0.1:8765). Code: `src/ai_project/server/`.

## REST

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health` | | `{"status": "ok"}` |
| GET | `/api/catalog` | | benchmarks, each with `available` and its first tasks (id, question, options, domain, roles, and each role's private `evidence` where the task has any) |
| GET | `/api/providers` | | providers reachable now: `mock`, plus models found on Ollama and vLLM |
| POST | `/api/sessions` | `benchmark`, `task_id`, `provider`, `cf_agents`, `pace`, `max_messages`, `reject_after`, `max_concurrent_agents`, `apply`, `start_paused` | session summary (`id`, `state`, `paused`, `status`, …) |
| GET | `/api/sessions` | | live sessions, then stored ones |
| GET | `/api/sessions/{id}` | | summary; `result` once finished |
| GET | `/api/sessions/{id}/events` | `since` (seq) | board events after `since` |
| GET | `/api/sessions/{id}/state` | `at` (version) | board state after the first `at` events (current if omitted) |
| POST | `/api/sessions/{id}/control` | `{"action": "pause" \| "resume" \| "step" \| "stop"}` | summary |
| GET | `/api/experiments` | | runs that have a `summary.json` |
| GET | `/api/experiments/{name}` | | `{name, meta, groups: [...], tests: [...]}` (see [experiments.md](experiments.md)) |

## WebSocket `/ws/sessions/{id}`

On connect the server sends everything so far, then live messages, each exactly once.

```json
{"type": "board", "event": {"seq": 7, "kind": "message", "data": {"message": {...}}, "timestamp": "..."}}
{"type": "cf", "kind": "cf.start",        "data": {"cf_agents": [...], "proximity": 0.33, "at_iteration": 4}}
{"type": "cf", "kind": "cf.branch_start", "data": {"branch_id": "...", "agent_id": "...", "target": {...}, "candidate": {...}}}
{"type": "cf", "kind": "cf.branch_event", "data": {"branch_id": "...", "event": {...}}}
{"type": "cf", "kind": "cf.branch_end",   "data": {"branch_id": "...", "status": "CONSENSUS", "credit": 0.67, "messages": [...]}}
{"type": "cf", "kind": "cf.applied",      "data": {...intervention...}}      // or "cf.none"
{"type": "end", "result": {...SessionResult...}}
{"type": "error", "message": "..."}
```

For a stored session (no longer live), the socket sends the stored board events and then
`{"type": "end", "result": null, "stored": true}`.

## Event kinds

`task`, `message`, `status`, `weight`, `context_revision` change the board state. The other
kinds only record what happened:
- `activation`: the arbiter's ranked queue for one round;
- `intervention`: the full counterfactual search;
- `tool`: an agent's tool call and its result;
- `format_error`: a rejected attempt;
- `collision`: a draft written against a stale board.

The state transition is `apply_event` in `blackboard/models.py`.
