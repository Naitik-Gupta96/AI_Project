# Project: Intelligible Blackboard Architecture with Counterfactual Agents

## Problem

Multi-agent systems built from long chains of direct messages are hard to
inspect: it is unclear who knew what, why the agents disagreed, and which
message could have changed the outcome. When the agents cannot agree
(deadlock), there is usually no principled way to find out why.

## Approach

1. Agents communicate only through a shared, structured **Blackboard**.
2. Every contribution is a **PXP** message: tag (RATIFY, REVISE, REFUTE,
   REJECT), prediction, explanation, confidence. The full history is kept and
   can be snapshotted.
3. A **Scheduler** decides who acts and detects consensus and deadlock with
   explicit rules.
4. After a deadlock, **counterfactual agents** reconsider their own past
   messages; the **counterfactual engine** branches history at that message and
   replays the future. A branch that reaches consensus points to the message
   that, said differently, would have unblocked the team.

## Scope of the current prototype

A working vertical slice with deterministic rule-based agents, a hand-written
Flash Talk task, a pilot over generated tasks, and a UI. What is implemented,
demonstrated, piloted and planned is tracked in one place:
[README.md#project-status](README.md#project-status). Research framing and
limitations: [RESEARCH.md](RESEARCH.md).

## Team

Roles and deliverables: [TEAM.md](TEAM.md).
