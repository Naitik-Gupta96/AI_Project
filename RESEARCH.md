# Research Documentation

## Research Question
How can a structured Blackboard architecture with counterfactual reasoning improve multi-agent AI system intelligibility, deadlock resolution, and decision quality compared to traditional message-passing architectures?

## Hypotheses
1. **H1**: Structured PXP messages (prediction + explanation + tag) improve traceability of agent reasoning compared to free-form message passing.
2. **H2**: Centralized Blackboard with full history enables effective counterfactual replay for deadlock resolution.
3. **H3**: Deterministic scheduler + counterfactual engine reduces deadlock resolution time vs. heuristic approaches.
4. **H4**: Real-time visualization of Blackboard state improves human understanding of multi-agent dynamics.

## Baselines
- Traditional message-passing multi-agent systems (e.g., CAMEL, AutoGen)
- Single-agent LLM with chain-of-thought
- Majority voting without explanation tracking

## Metrics
- **Deadlock Rate**: % of tasks reaching DEADLOCK status
- **Resolution Time**: Steps/time to reach CONSENSUS from DEADLOCK
- **Decision Quality**: Correctness of final prediction (benchmark-dependent)
- **Traceability Score**: Human evaluator rating of reasoning trace clarity
- **Counterfactual Effectiveness**: Improvement in decision quality after replay

## Experiments
1. **Flash Talk Demo** (Oct 6): Vertical slice with 2 agents, manual disagreement
2. **Scheduler Integration** (Person 3): Deterministic turn-taking with 3-4 agents
3. **Deadlock Detection** (Person 3): Pattern-based detection from history
4. **Counterfactual Replay** (Person 3): Branch from snapshot, test alternative agent choices
5. **Benchmark Evaluation** (Person 4): KramaBench, MSCoRe, MedAgentBench
6. **Ablation Studies**: With/without explanations, with/without counterfactuals

## Benchmarks
- **KramaBench**: Multi-agent reasoning tasks
- **MSCoRe**: Multi-step collaborative reasoning
- **MedAgentBench**: Medical decision-making (if applicable)

## Limitations
- In-memory Blackboard only (no persistence)
- No LLM integration yet (mock agents for demo)
- Counterfactual engine not yet implemented
- Visualization not yet implemented
- Small team (4 undergraduates), limited compute
- Prototype scope - not production system

## Future Work
- Persistent backend (Redis/PostgreSQL) behind same interface
- LLM agent implementations with structured output prompting
- Advanced deadlock detection (graph-based, ML-based)
- Automated counterfactual generation
- Web-based real-time visualization
- Comprehensive benchmark suite
- Credit assignment optimization for agent contributions