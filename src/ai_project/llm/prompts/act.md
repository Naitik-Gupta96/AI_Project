## Task
$task

$options_block
$context_block
## Your private evidence
Only you can see this. Do not invent facts beyond it and the board.
$evidence

## Blackboard (message $j is yours)
$history

## What you are answering
Peer message (the latest message from another agent):
$peer

Your previous position:
$own
$tool_block
## Your turn
Decide your current answer (prediction) and explain it in 2-4 sentences grounded in your evidence
and the board. Then give these judgments:
$judgments

$tag_rule
$feedback
## Output
Return one JSON object and nothing else:
{"prediction": "...", "explanation": "...", "confidence": <0..1>,
 "explanation_agrees": true|false|null, "prediction_matches": true|false|null, "changed": true|false|null}
