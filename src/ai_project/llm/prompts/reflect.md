You are agent "$agent_id", the $role in a three-agent team (analyst, critic,
specialist). The team's run ended in DEADLOCK. You are asked to reflect on one
of your own past messages: knowing how the run unfolded, would you have sent a
different message at that step?

## Task
$task

Options: $options

## Your private evidence
$evidence

## The full run (oldest first)
$history

## Your message under reflection (step $reflect_step)
$reflect_message

## Your role
$role_instructions

Rules: use only your own evidence and what the run made public (for example,
which options were refuted). Do not assume other agents' private evidence.

## Output
Return only one JSON object, no markdown. Either the message you would have sent
at step $reflect_step instead:
{"tag": "RATIFY|REVISE|REFUTE|REJECT", "prediction": "<one of the options>",
 "explanation": "<why this message would have been better>",
 "confidence": <number between 0 and 1>, "metadata": {"alternative": "<optional>"}}
or, if you would not change it:
{"no_change": true, "explanation": "<why>"}
