# Project: Intelligible Blackboard Architecture with Counterfactual Agents

## Project Title
Intelligible Blackboard Architecture with Counterfactual Agents

## Problem Statement
Multi-agent AI systems often suffer from opaque decision-making, difficulty in debugging agent interactions, and deadlock situations where agents cannot reach consensus. Traditional message-passing architectures create long chains that are hard to trace and replay.

## Research Motivation
We propose a structured Blackboard architecture where:
1. All agents communicate through a central, globally shared Blackboard
2. Interactions follow the PXP protocol (RATIFY, REVISE, REFUTE, REJECT)
3. Full history enables counterfactual replay for deadlock resolution
4. Structured outputs (prediction + explanation) enable intelligibility

## Current Prototype Goal (Flash Talk - Oct 6)
A working vertical slice demonstrating:
- Multiple agents publishing PXP messages to the Blackboard
- Structured disagreement (REFUTE/REJECT) leading to deadlock
- History log capturing all interactions
- Snapshot capability for counterfactual branching
- Clean integration points for scheduler, counterfactual engine, and UI

## Eventual Project Direction
- Full multi-agent system with LLM-based agents (Person 2)
- Deterministic scheduler with deadlock detection (Person 3)
- Counterfactual reasoning engine for automatic resolution (Person 3)
- Real-time visualization of agent interactions (Person 4)
- Evaluation on benchmarks (KramaBench, MSCoRe, MedAgentBench)

## Team Roles

### Person 1: Foundational Architecture / Blackboard / PXP (Current)
- Blackboard core with thread-safe state management
- PXP message protocol and validation
- History/event logging
- Snapshot and serialization
- Integration contracts for teammates

### Person 2: PEX Agents + LLM Integration
- Agent implementations that produce PXP messages
- LLM prompt engineering for prediction + explanation
- Agent orchestration logic

### Person 3: Scheduler + Deadlock Detection + Counterfactual Reasoning
- Deterministic scheduler controlling agent turns
- Deadlock detection from Blackboard history
- Counterfactual replay engine using snapshots
- Resolution strategies

### Person 4: Visualization + Evaluation/Experiments
- Real-time UI for Blackboard state and history
- Experiment framework and benchmarking
- Results analysis and reporting