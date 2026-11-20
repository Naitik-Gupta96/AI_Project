## Counterfactual reflection
The session is deadlocked. You are looking back at one of your own past messages, knowing how
the whole session unfolded. Would a different message at that point have moved the team closer
to agreement?

## Task
$task

$options_block
$context_block
## Your private evidence
$evidence

## The whole session (oldest first)
$hindsight

## The message you are reconsidering (message $j)
$target

At that point the peer message was:
$peer

and your previous position was:
$own

## Instructions
Propose up to $max_candidates alternative messages for message $j. Each may change the
prediction, the explanation's wording, or both; use only your own evidence and what the session
made public. Tag each candidate by the same PXP rule (k = $reject_after), judging the peer message
above against your previous position above:
- message 1 is INIT; matches and agrees -> RATIFY; exactly one -> REVISE if changed else REFUTE;
  neither -> REJECT if message number > k, else REVISE if changed else REFUTE.
Also write one lesson: a short instruction to yourself for the rest of this session.
If no alternative would help, return an empty candidate list.
$feedback
## Output
Return one JSON object and nothing else:
{"candidates": [{"tag": "...", "prediction": "...", "explanation": "...", "confidence": <0..1>,
  "judgment": {...} or null, "rationale": "<why this would have helped>", "metadata": {}}],
 "lesson": "..."}
