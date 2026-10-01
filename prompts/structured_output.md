# Structured Output Format

All agents must return responses in this exact JSON format:

```json
{
  "tag": "RATIFY",
  "prediction": "Option A",
  "explanation": "The task requires selecting the best option based on evidence. Option A provides the strongest support because...",
  "confidence": 0.85,
  "metadata": {}
}
```

## Field Requirements

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| tag | string | Yes | Must be one of: RATIFY, REVISE, REFUTE, REJECT |
| prediction | string | Yes | Non-empty, concrete decision |
| explanation | string | Yes | Non-empty, reasoning trace |
| confidence | number | Yes | 0.0 <= confidence <= 1.0 |
| metadata | object | No | Additional structured data |

## Tag Semantics

- **RATIFY**: Agree with current prediction (or propose new one if first agent)
- **REVISE**: Agree with direction but modify the specific prediction
- **REFUTE**: Disagree with current prediction; provide alternative
- **REJECT**: Task/approach is fundamentally flawed; cannot proceed

## Examples

### Analyst (first agent, no prior prediction)
```json
{
  "tag": "RATIFY",
  "prediction": "Option B",
  "explanation": "Based on the task requirements...",
  "confidence": 0.82
}
```

### Critic (challenging)
```json
{
  "tag": "REFUTE",
  "prediction": "Option B",
  "explanation": "The current reasoning for Option A overlooks constraint C3...",
  "confidence": 0.78
}
```

### Specialist (independent perspective)
```json
{
  "tag": "REVISE",
  "prediction": "Option C",
  "explanation": "From a systems perspective, Option C offers better scalability...",
  "confidence": 0.88
}
```

## Anti-Patterns to Avoid

❌ Missing fields
❌ Invalid tag values
❌ Empty prediction or explanation
❌ Confidence outside [0, 1]
❌ Markdown formatting around JSON
❌ Extra conversational text
❌ Vague predictions like "It depends"