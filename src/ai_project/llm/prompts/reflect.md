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
Propose up to $max_candidates alternatives to message $j. Each may change the prediction, the
wording of the explanation, or both. Use only your own evidence and what the session made public.
Judge each candidate against the peer message and previous position shown above (as things stood
at message $j):
$judgments

$tag_rule
For each candidate give a one-sentence rationale. Also write one lesson: a short instruction to
yourself for the rest of this session. If no alternative would help, return an empty list.
$feedback
## Output
Return one JSON object and nothing else:
{"candidates": [{"prediction": "...", "explanation": "...", "confidence": <0..1>,
  "explanation_agrees": true|false|null, "prediction_matches": true|false|null,
  "changed": true|false|null, "rationale": "..."}], "lesson": "..."}
