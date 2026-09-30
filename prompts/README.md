# Prompts Directory

This directory contains prompt templates for LLM-based agents (Person 2).

## Structure
```
prompts/
├── README.md              # This file
├── templates/             # Prompt templates
│   ├── base_agent.txt     # Base agent prompt
│   ├── ratify.txt         # RATIFY reasoning prompt
│   ├── revise.txt         # REVISE reasoning prompt
│   ├── refute.txt         # REFUTE reasoning prompt
│   └── reject.txt         # REJECT reasoning prompt
└── examples/              # Example filled prompts
```

## Prompt Design Guidelines

Each agent prompt should produce structured output:
1. **Prediction**: The agent's decision/answer
2. **Explanation**: Step-by-step reasoning
3. **Confidence**: Self-assessed confidence (0.0-1.0)

### Example Template (base_agent.txt)

```
You are Agent {agent_id} in a multi-agent system using the PXP protocol.

Task: {task}

Previous Discussion:
{history}

Your role: {role_description}

Analyze the task and previous discussion. Provide your response in this exact format:

PREDICTION: <your decision>
EXPLANATION: <your reasoning>
CONFIDENCE: <0.0-1.0>
TAG: <RATIFY|REVISE|REFUTE|REJECT>
```

## Integration with Person 2's Agents

Person 2's agents will:
1. Load prompt template
2. Fill in `{task}`, `{history}`, `{agent_id}`, `{role_description}`
3. Call LLM
4. Parse structured output
5. Create `PXPMessage` and publish to Blackboard

## Tag Selection Logic

| Situation | Tag |
|-----------|-----|
| Agree with current prediction | RATIFY |
| Agree but with modifications | REVISE |
| Disagree with current prediction | REFUTE |
| Task is fundamentally flawed | REJECT |