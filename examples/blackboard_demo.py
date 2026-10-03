#!/usr/bin/env python
"""
Blackboard Demo

Demonstrates the core Blackboard + PXP functionality:
1. Create a Blackboard
2. Initialize a task
3. Agent A publishes a RATIFY message
4. Agent B publishes a REFUTE message
5. Print current board state
6. Print history
7. Create a snapshot
8. Mutate the snapshot
9. Show that the live board did not change
"""

import dataclasses

from ai_project.protocol import PXPMessage, PXPTag
from ai_project.blackboard import Blackboard, BlackboardStatus


def main() -> None:
    print("=" * 60)
    print("BLACKBOARD + PXP DEMONSTRATION")
    print("=" * 60)

    # 1. Create a Blackboard
    print("\n[1] Creating Blackboard...")
    board = Blackboard()

    # 2. Initialize a task
    print("\n[2] Initializing task...")
    board.initialize_task(
        task="Select the best approach for the AI project architecture",
        metadata={"project": "AI_Project", "team_size": 4}
    )
    print(f"    Task: {board.get_state().task}")
    print(f"    Status: {board.get_state().status.value}")
    print(f"    Iteration: {board.get_iteration()}")

    # 3. Create a valid PXP message from Agent A (RATIFY)
    print("\n[3] Agent A -> RATIFY")
    msg_a = PXPMessage.create(
        agent_id="agent_A",
        tag=PXPTag.RATIFY,
        prediction="Blackboard Architecture with PXP Protocol",
        explanation="Provides structured communication, full history for counterfactual reasoning, and clean integration points for all team members.",
        confidence=0.85,
        iteration=1,
    )
    board.publish_message(msg_a)
    print(f"    Agent: {msg_a.agent_id}")
    print(f"    Tag: {msg_a.tag.value}")
    print(f"    Prediction: {msg_a.prediction}")
    print(f"    Explanation: {msg_a.explanation}")
    print(f"    Confidence: {msg_a.confidence}")

    # 4. Create a second message from Agent B (REFUTE)
    print("\n[4] Agent B -> REFUTE")
    msg_b = PXPMessage.create(
        agent_id="agent_B",
        tag=PXPTag.REFUTE,
        prediction="Blackboard Architecture with PXP Protocol",
        explanation="While structured, the PXP protocol may be too rigid for creative exploration. Suggest adding a BRAINSTORM tag.",
        confidence=0.72,
        iteration=2,
    )
    board.publish_message(msg_b)
    print(f"    Agent: {msg_b.agent_id}")
    print(f"    Tag: {msg_b.tag.value}")
    print(f"    Prediction: {msg_b.prediction}")
    print(f"    Explanation: {msg_b.explanation}")
    print(f"    Confidence: {msg_b.confidence}")

    # 5. Print current board state
    print("\n[5] Current Board State:")
    state = board.get_state()
    print(f"    Task: {state.task}")
    print(f"    Status: {state.status.value}")
    print(f"    Iteration: {state.iteration}")
    print(f"    Current Prediction: {state.current_prediction}")
    print(f"    Current Explanation: {state.current_explanation}")
    print(f"    Latest Message: {state.latest_message['agent_id']} -> {state.latest_message['tag']}")

    # 6. Print history
    print("\n[6] History:")
    history = board.get_history()
    for i, event in enumerate(history, 1):
        print(f"    {i}. Iteration {event.iteration}: {event.agent_id} {event.tag} \"{event.prediction[:40]}...\"")

    # 7. Create a snapshot
    print("\n[7] Creating snapshot...")
    snapshot = board.snapshot()
    print(f"    Snapshot created at: {snapshot.timestamp}")
    print(f"    Snapshot iteration: {snapshot.state.iteration}")
    print(f"    Snapshot history length: {len(snapshot.history)}")

    # 8. Mutate the snapshot
    print("\n[8] Mutating snapshot (simulating counterfactual branch)...")
    original_prediction = snapshot.state.current_prediction
    snapshot.state.current_prediction = "Modified: Hybrid Approach with Flexible Tags"
    snapshot.state.iteration = 999
    snapshot.state.metadata["counterfactual"] = True
    # History events are frozen: editing one in place is refused outright...
    try:
        snapshot.history[0].agent_id = "MODIFIED_AGENT"
    except dataclasses.FrozenInstanceError:
        print("    History events are immutable: in-place edit refused")
    # ...so a branch replaces events in its own copy of the list instead
    snapshot.history[0] = dataclasses.replace(snapshot.history[0], agent_id="MODIFIED_AGENT")
    print(f"    Snapshot prediction changed to: {snapshot.state.current_prediction}")
    print(f"    Snapshot iteration changed to: {snapshot.state.iteration}")
    print(f"    Snapshot history[0] agent_id changed to: {snapshot.history[0].agent_id}")

    # 9. Show that the live board did not change
    print("\n[9] Verifying live Blackboard unchanged:")
    live_state = board.get_state()
    live_history = board.get_history()

    print(f"    Live prediction: {live_state.current_prediction}")
    print(f"    Snapshot prediction: {snapshot.state.current_prediction}")
    assert live_state.current_prediction == original_prediction, "Live prediction was modified!"
    print("    [OK] Live prediction unchanged")

    print(f"    Live iteration: {live_state.iteration}")
    print(f"    Snapshot iteration: {snapshot.state.iteration}")
    assert live_state.iteration == 2, "Live iteration was modified!"
    print("    [OK] Live iteration unchanged")

    print(f"    Live history[0] agent_id: {live_history[0].agent_id}")
    print(f"    Snapshot history[0] agent_id: {snapshot.history[0].agent_id}")
    assert live_history[0].agent_id == "agent_A", "Live history was modified!"
    print("    [OK] Live history unchanged")

    # 10. Demonstrate serialization
    print("\n[10] Serialization demo:")
    state_dict = board.get_state().to_dict()
    print(f"    State serialized to dict: {len(str(state_dict))} chars")

    history_dicts = [e.to_dict() for e in board.get_history()]
    print(f"    History serialized: {len(history_dicts)} events")

    snapshot_dict = snapshot.to_dict()
    print(f"    Snapshot serialized: {len(str(snapshot_dict))} chars")

    # 11. Demonstrate status management
    print("\n[11] Status management:")
    board.set_status(BlackboardStatus.DEADLOCK)
    print(f"    Status set to: {board.get_state().status.value}")
    board.set_status(BlackboardStatus.RUNNING)
    print(f"    Status set to: {board.get_state().status.value}")

    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE - ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()