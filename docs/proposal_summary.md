# Proposal Summary

## Original Proposal: Intelligible Blackboard Architecture with Counterfactual Agents

### Core Idea
Replace long direct message-passing chains with a globally shared structured Blackboard where agents communicate through a standardized PXP protocol (RATIFY, REVISE, REFUTE, REJECT).

### Key Layers
1. **PXP-Governed Blackboard** (Person 1 - IMPLEMENTED)
   - Thread-safe central state store
   - Structured PXP message validation
   - Historical state information
   - State serialization

2. **Retrospective Counterfactual Reasoning** (Person 3 - FUTURE)
   - Deadlock detection from interaction patterns
   - Counterfactual replay using snapshots
   - Automated resolution strategies

3. **Deterministic Scheduler** (Person 3 - FUTURE)
   - Controls agent turn order
   - Manages task lifecycle
   - Integrates with Blackboard status

4. **Real-Time Visualization** (Person 4 - FUTURE)
   - Live Blackboard state display
   - History timeline
   - Agent interaction graph

### Agent Output Format
Every agent produces structured output containing:
- **Prediction**: The agent's proposed answer/decision
- **Explanation**: Reasoning supporting the prediction

### PXP Interaction Tags
- **RATIFY**: Agree with current prediction
- **REVISE**: Agree but with modifications
- **REFUTE**: Disagree with current prediction
- **REJECT**: Reject the entire task/approach

### Flash Talk Target (Oct 6)
Small working vertical slice demonstrating:
- Agents → Blackboard → structured PXP interaction
- Disagreement → eventual integration with deadlock/counterfactual components