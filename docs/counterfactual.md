# Counterfactual agents

Code: `src/ai_project/counterfactual/` (`sandbox.py`, `resolver.py`) and `Agent.reflect`.

When the live board deadlocks, every counterfactual-capable agent asks: *if I had sent
something else at one of my past messages, would the board be closer to consensus now?* It
answers by simulation, not by guessing.

## Steps

1. **Isolate.** Take a deep-copied snapshot of the live board. The live board is never written
   to during the search.
2. **Reflect.** For each of its last `messages_per_agent` messages (default 3), the agent sees
   the whole session and the board as it was at that message: the peer message and its own
   previous position then. It proposes up to `max_candidates` alternatives. An alternative may
   be:
   - a different prediction;
   - a differently worded explanation;
   - both.

   The AGENT procedure tags each one as of that point, the grammar checks it, and candidates
   identical to the original are dropped. The reflection also produces a lesson.
3. **Replay.** For each candidate:
   1. Rebuild a sandbox board from the events before the target message (in its own
      `MemoryStore`).
   2. Commit the candidate in place of the target.
   3. Let a scheduler drive *clones* of the agents to the end of the budget.

   Clones share the provider, so their tokens are counted as sandbox usage, but the live
   agents' lessons are not touched.
4. **Credit.** `credit = proximity(sandbox end) − proximity(live board at the deadlock)`.
   Proximity is the weighted share of the largest group of agents ratifying one thesis: 1.0 at
   consensus, 1/3 when one of three agents ratifies.
5. **Apply** the best candidate over all capable agents (highest credit; ties go to the later
   message, then to team order), if its credit is positive:
   - **prompt**: the lesson is added to the agent's system prompt for the rest of the session,
     and a `context_revision` event sets its position to the candidate's. This is how the
     agent "alters its local prompt context". Its next live message is then judged against the
     revised position.
   - **weight**: `w ← max(w_min, w · (1 − η · credit))`, with defaults η = 0.5 and w_min = 0.25.
     The more the agent's own message is to blame for the deadlock, the less its continued
     dissent counts. With equal weights and τ = 0.75, three agents must all agree. With one
     weight at 0.67, the other two carry the decision (2 / 2.67 = 0.75).
   - **both** (default).

   The board then goes from DEADLOCK back to RUNNING, and the agent is scheduled first. One
   `intervention` event records the search: every reflection, every branch with its messages,
   its credit, and what was applied.
6. Repeat on the next deadlock, up to `max_interventions` (default 2). If no candidate has
   positive credit, the session ends deadlocked.

## Worked example (`architecture` task, deterministic mock)

The analyst ranks Option A higher. The critic and the specialist each know a reason to rule A
out. Option B is acceptable to everyone.

| # | Agent | Tag | Prediction | Why |
|---|---|---|---|---|
| 1 | analyst | INIT | Option A | best benefit (0.82) |
| 2 | critic | REFUTE | Option B | A breaks constraint C3; first reply, unchanged |
| 3 | specialist | RATIFY | Option B | agrees with the critic |
| 4 | analyst | REJECT | Option A | disagrees with both, message 4 > k = 3 |

At the deadlock the analyst (counterfactual-capable) tries two branches:

| Branch | Replaces | Candidate | Sandbox ends | Credit |
|---|---|---|---|---|
| 1 | #4 REJECT A | REJECT B | DEADLOCK (the rule forces REJECT at #4) | 0.00 |
| 2 | #1 INIT A | INIT B | CONSENSUS on B | +0.67 |

Branch 2 is applied. The analyst's lesson goes into its prompt, its position becomes B, and its
weight drops from 1.00 to 0.67. The live board resumes:

| # | Agent | Tag | Prediction |
|---|---|---|---|
| 5 | analyst | RATIFY | Option B |
| 6 | critic | RATIFY | Option B → consensus (weighted share 1.00) |

Run it yourself:

```bash
bb run --cf analyst      # or open the UI and run the default session
```

When only the critic or the specialist is capable, no candidate earns credit and the session
stays deadlocked. Which agent can reflect matters, and the ablation measures exactly that.

## Settings (`CounterfactualConfig`)

| Setting | Default | Meaning |
|---|---|---|
| `max_interventions` | 2 | applied interventions per session |
| `messages_per_agent` | 3 | own messages each agent reconsiders |
| `max_candidates` | 3 | alternatives per message |
| `eta`, `min_weight` | 0.5, 0.25 | weight update |
| `apply` | both | prompt, weight or both |
