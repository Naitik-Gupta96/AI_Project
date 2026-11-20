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
## How to tag your message (PXP, Algorithm 1)
First decide your current answer: prediction y and explanation e.
Then judge, comparing the PEER message with YOUR PREVIOUS position (not with your new answer):
- prediction_matches: does the peer's prediction match your previous prediction?
- explanation_agrees: do you agree with the peer's explanation, given your previous explanation?
- changed: does your new answer differ from your previous position? (On your first reply your
  previous position is your new answer, so this is false.)
The tag follows from the judgment, with k = $reject_after:
- message 1 is INIT (no judgment);
- matches and agrees -> RATIFY;
- exactly one of the two -> REVISE if changed, else REFUTE;
- neither, and message number > k -> REJECT;
- neither, and message number <= k -> REVISE if changed, else REFUTE.
$feedback
## Output
Return one JSON object and nothing else:
{"tag": "...", "prediction": "...", "explanation": "<2-4 sentences grounded in your evidence>",
 "confidence": <0..1>, "judgment": {"prediction_matches": bool, "explanation_agrees": bool,
 "changed": bool} or null for INIT, "metadata": {}}
