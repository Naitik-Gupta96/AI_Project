#!/usr/bin/env python
"""
Scheduler + Deadlock + Counterfactual Demo

Every line below is printed from real Scheduler / Blackboard state:

1. Initialize a task on the Blackboard
2. Create deterministic mock agents (analyst, critic, specialist)
3. The Scheduler runs them
4. Disagreement appears
5. Deadlock is detected
6. A snapshot of the original run is taken
7. A counterfactual branch changes one earlier message
8. The branch is replayed by the same agents, policy and config
9. The different outcome is shown
10. The original run is verified unchanged

Usage:
    python examples/scheduler_demo.py
    python examples/scheduler_demo.py --json run.json   # also export structured results
"""

import argparse
import json
import sys
from collections.abc import Iterable

from ai_project.counterfactual import CounterfactualEngine
from ai_project.counterfactual.scenarios import demo_intervention
from ai_project.scheduler import TraceEntry
from ai_project.scheduler.scenarios import deadlock_scenario

RULE = "=" * 70
MARKERS = {"inherited": "   (inherited from original)", "intervention": "   (COUNTERFACTUAL)"}


def print_steps(entries: Iterable[TraceEntry]) -> None:
    for entry in entries:
        if entry.kind in ("agent_action", "inherited", "intervention"):
            marker = MARKERS.get(entry.kind, "")
            action = f"{entry.agent:<10} -> {entry.event:<6} {entry.prediction}"
            print(f"Step {entry.step}: {action}{marker}")
            if entry.kind == "agent_action":
                print(f"        selected: {entry.reason}")
                print(f"        says:     {entry.explanation}")
        else:
            print(f"Status: {entry.event}")
            print(f"        {entry.reason}")


def fingerprint(board) -> dict:
    return {
        "state": board.get_state().to_dict(),
        "history": [e.to_dict() for e in board.get_history()],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--json", metavar="PATH", help="write structured results to PATH")
    args = parser.parse_args()

    print(RULE)
    print("SCHEDULER + DEADLOCK + COUNTERFACTUAL DEMO")
    print(RULE)

    # 1-2. Task and agents
    scenario = deadlock_scenario()
    scheduler = scenario.new_scheduler()
    board = scheduler.board
    print(f"\n[1] Task: {board.get_state().task}")
    print("[2] Agents:")
    for agent in scheduler.registry:
        objects_to = ", ".join(agent.objections) or "-"
        prefers = agent.preferred or "-"
        print(f"      {agent.agent_id:<10} prefers: {prefers:<9} objects to: {objects_to}")
    print(f"    Policy:   {scenario.policy.describe()}")
    print(f"    Deadlock: {scenario.config.deadlock.to_dict()}")

    # 3-5. Original run
    print("\n=== ORIGINAL RUN ===")
    original = scheduler.run()
    print_steps(original.trace)

    # 6. Snapshot
    before = fingerprint(board)
    snapshot = board.snapshot()
    print(
        f"\n[6] Snapshot taken: iteration {snapshot.state.iteration}, "
        f"{len(snapshot.history)} events, status {snapshot.state.status.value}"
    )

    # 7-8. Counterfactual branch + replay
    engine = CounterfactualEngine()
    intervention = demo_intervention()
    branch = engine.create_branch(snapshot, intervention)
    replaced = branch.replaced_event

    print("\n=== COUNTERFACTUAL ===")
    print(f"Branch: {branch.branch_id}")
    print(
        f"Changed event: Step {branch.branch_point} "
        f"({replaced.agent_id} {replaced.tag} {replaced.prediction})"
    )
    print(f"  original: {replaced.explanation}")
    print(f"  changed:  {intervention.explanation}")
    print(f"  why:      {intervention.description}")
    print("Branch before replay:")
    print_steps(branch.setup_trace)
    print("Replay...")
    cf_result = engine.replay(branch, scenario.agents, scenario.policy, scenario.config)
    print_steps(cf_result.trace)

    # 9. Comparison
    comparison = engine.compare(original, branch)
    print("\n=== COMPARISON ===")
    print(
        f"Original:       {comparison.original_status} on {comparison.original_prediction} "
        f"after {comparison.original_iterations} iterations"
    )
    print(
        f"Counterfactual: {comparison.counterfactual_status} on "
        f"{comparison.counterfactual_prediction} after {comparison.counterfactual_iterations} "
        f"iterations"
    )
    print(
        f"Diverged at iteration {comparison.divergence_iteration} "
        f"(shared prefix: {comparison.shared_prefix} event(s))"
    )

    # 10. Original preserved
    print("\n=== ORIGINAL PRESERVED ===")
    unchanged = fingerprint(board) == before
    history = [f"{e.agent_id} {e.tag} {e.prediction}" for e in board.get_history()]
    print(f"Original status:  {board.get_state().status.value}")
    print(f"Original history: {history}")
    print(f"Original state and history unchanged: {'[OK]' if unchanged else '[FAILED]'}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(
                {
                    "scenario": scenario.describe(),
                    "original": original.to_dict(),
                    "counterfactual": {
                        "branch": branch.to_dict(),
                        "comparison": comparison.to_dict(),
                    },
                },
                f,
                indent=2,
            )
        print(f"\nStructured results written to {args.json}")

    print("\n" + RULE)
    return 0 if unchanged else 1


if __name__ == "__main__":
    sys.exit(main())
