# PXP on a blackboard

This project uses the Two-Way Intelligibility Protocol (PXP) of Baskar et al.
([arXiv 2301.01819](https://arxiv.org/abs/2301.01819)) in the procedural form given by
Mestha et al. ([arXiv 2410.20600](https://arxiv.org/abs/2410.20600), Algorithms 1 and 3,
Definitions 1 and 2). The papers describe two agents exchanging messages. This page states
exactly how we carry the protocol over to three or more agents sharing a blackboard, and which
rules are ours.

Code: `src/ai_project/protocol/` (`pxp.py`, `grammar.py`, `intelligibility.py`).

## Messages

Every message carries the sender's own prediction `y` and explanation `e`, a confidence, and a
tag. The tag is not chosen freely. It follows from three judgments the sender makes:

| Symbol | Meaning on the blackboard |
|---|---|
| `(y', e')` | the **peer message**: the latest message on the board from another agent |
| `(y'', e'')` | the sender's **previous position**: its last message, or a context revision recorded by a counterfactual intervention. On its first reply there is none, and the paper sets it to the sender's current output. |
| `(y, e)` | the sender's **current output** |

```
prediction_matches = MATCH(y', y'')
explanation_agrees = AGREE(e', e'')
changed            = not MATCH(y, y'') or not AGREE(e, e'')
```

## Tag rule (Algorithm 1)

| Message number `j` | match | agree | Tag |
|---|---|---|---|
| 1 | | | `INIT` |
| > 1 | yes | yes | `RATIFY` |
| > 1 | exactly one of the two | | `REVISE` if changed, else `REFUTE` |
| > k | no | no | `REJECT` |
| ≤ k | no | no | `REVISE` if changed, else `REFUTE` |

`k` (`reject_after`, default 3) is the message number after which `REJECT` may be sent. The
spec lists four tags; the paper also has `INIT` for the opening message, and we keep it.

## Who decides what

Algorithm 1 is a procedure, and so is our agent (`agents/procedure.py`). The model (or the
mock) answers one turn with what needs understanding:
- its prediction and explanation;
- `explanation_agrees`;
- `changed` for its reasoning;
- `prediction_matches`, only for free-form answers.

The procedure then:
1. computes MATCH itself when the task lists options (string equality);
2. sets `changed` when the prediction moved;
3. assigns the tag from the table above.

A first live run with a 4B model showed why. Asked to apply the tag table itself, the model
tagged RATIFY while judging that it disagreed with the peer's explanation.

## What the grammar checks

`PXPGrammar.check` runs on every commit. A failing message is rejected, never repaired. The
agent gets the violations back in its prompt and may retry once. The agent procedure always
produces grammatical messages; the grammar is the board's guarantee against any other writer.

1. **Structure.** Agent id, prediction and explanation are non-empty, and confidence is in [0, 1].
2. **Position in the session.** `INIT` is message 1 and only message 1. A reply needs a peer
   message and a judgment.
3. **Options.** When the task lists options, the prediction is one of them.
4. **Verifiable judgments.** With listed options, MATCH is string equality, so the grammar
   recomputes `prediction_matches` and the prediction part of `changed`. On a first reply,
   `changed` must be false. Explanation agreement is the agent's own judgment.
5. **Tag.** The tag equals the Algorithm 1 tag for the stated judgment.
6. **RATIFY content (our rule).** The spec defines RATIFY as aligning with the board's
   prediction and explanation. So with listed options, a RATIFY must carry the peer's
   prediction. Algorithm 1 alone would accept "RATIFY A" in reply to B whenever the sender's
   *previous* position matched B.

## Adaptations for more than two agents

These are our choices. The papers do not cover them.

- **Peer message.** "The other agent's last message" becomes the latest message by any other
  agent. This matches the blackboard paradigm: agents react to the shared state, not to a
  private channel.
- **Termination.** Algorithm 3 stops when both agents' latest tags are RATIFY, on a REJECT,
  or after `n` messages. On the blackboard:
  - **Consensus:** every agent's latest message is a RATIFY of the same thesis. Voting weights
    can relax this; see below.
  - **Deadlock:** a REJECT, or a REFUTE loop, or stagnation. A deadlock is where a
    counterfactual agent may step in.
  - **Budget:** `max_messages` (default 12).
- **Agreement chains and weights.** A RATIFY agrees with the message it answered
  (`in_reply_to`). If that message is itself a RATIFY, the agreement follows the chain back to
  the first non-RATIFY message, the *anchor*. Consensus holds when the weighted share of
  agents ratifying the same anchor reaches τ (default 0.75), with at least two supporters. With
  equal weights and three agents, that means unanimity.
- **Context revision.** After a counterfactual intervention, the agent's previous position
  becomes the alternative it found. This is recorded as a `context_revision` event, not as a
  message. It is how the agent "alters its own local prompt context" (the spec's description
  of REVISE) without rewriting history.

## Intelligibility (Definitions 1 and 2)

For agent `m`, let `T_m` be the tags `m` sent, with `INIT` excluded. The paper counts
⟨INIT_m, RATIFY_h, RATIFY_m⟩ as Strong for `m`, so `INIT` does not enter the "every
element" test.

| Level | Condition on `T_m` |
|---|---|
| One-Way | contains a RATIFY or REVISE, and no REJECT |
| Strong | non-empty, and every element is RATIFY or REVISE |
| Ultra-Strong | Strong, and at least one REVISE |

The session level is the weakest level among agents that sent a non-INIT message. Two-way
intelligibility is one-way for both agents, and this generalises it to n agents.

Experiments report this whole-session level. They also report, separately, the same
classification over the messages after the last counterfactual intervention. That second
measure is ours and is labelled as such.
