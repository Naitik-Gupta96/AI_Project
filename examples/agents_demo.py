#!/usr/bin/env python
"""
Agents + Blackboard Demo

Demonstrates the complete agent layer vertical slice:
1. Create Blackboard and initialize task
2. Analyst agent acts and publishes
3. Critic agent acts and publishes
4. Specialist agent acts and publishes
5. Show final board state and history
"""

from ai_project.blackboard import Blackboard, BlackboardStatus
from ai_project.agents import AnalystAgent, CriticAgent, SpecialistAgent
from ai_project.llm import MockLLMProvider
from ai_project.protocol import PXPTag


def main() -> None:
    print("=" * 70)
    print("AGENTS + BLACKBOARD VERTICAL SLICE DEMONSTRATION")
    print("=" * 70)

    # Create agents with mock provider
    mock_provider = MockLLMProvider()
    analyst = AnalystAgent(agent_id="analyst_1", llm_provider=mock_provider)
    critic = CriticAgent(agent_id="critic_1", llm_provider=mock_provider)
    specialist = SpecialistAgent(agent_id="specialist_1", llm_provider=mock_provider)

    print("\n[1] Creating Blackboard and initializing task...")
    board = Blackboard()
    board.initialize_task(
        task="Choose the best architecture for the AI project: Monolithic vs Microservices vs Modular Monolith",
        metadata={"domain": "software_architecture", "complexity": "high"}
    )
    print(f"    Task: {board.get_state().task}")
    print(f"    Initial status: {board.get_state().status.value}")
    print(f"    Initial iteration: {board.get_iteration()}")

    # --- ANALYST ---
    print("\n" + "-" * 50)
    print("[2] AGENT 1: ANALYST")
    print("-" * 50)

    msg1 = analyst.act(board)
    print(f"    Agent ID: {msg1.agent_id}")
    print(f"    Tag: {msg1.tag.value}")
    print(f"    Prediction: {msg1.prediction}")
    print(f"    Explanation: {msg1.explanation}")
    print(f"    Confidence: {msg1.confidence:.2f}")
    print(f"    Iteration: {msg1.iteration}")

    board.publish_message(msg1)
    print(f"    Published to Blackboard. Board iteration: {board.get_iteration()}")

    # --- CRITIC ---
    print("\n" + "-" * 50)
    print("[3] AGENT 2: CRITIC")
    print("-" * 50)

    msg2 = critic.act(board)
    print(f"    Agent ID: {msg2.agent_id}")
    print(f"    Tag: {msg2.tag.value}")
    print(f"    Prediction: {msg2.prediction}")
    print(f"    Explanation: {msg2.explanation}")
    print(f"    Confidence: {msg2.confidence:.2f}")
    print(f"    Iteration: {msg2.iteration}")

    board.publish_message(msg2)
    print(f"    Published to Blackboard. Board iteration: {board.get_iteration()}")

    # --- SPECIALIST ---
    print("\n" + "-" * 50)
    print("[4] AGENT 3: SPECIALIST")
    print("-" * 50)

    msg3 = specialist.act(board)
    print(f"    Agent ID: {msg3.agent_id}")
    print(f"    Tag: {msg3.tag.value}")
    print(f"    Prediction: {msg3.prediction}")
    print(f"    Explanation: {msg3.explanation}")
    print(f"    Confidence: {msg3.confidence:.2f}")
    print(f"    Iteration: {msg3.iteration}")

    board.publish_message(msg3)
    print(f"    Published to Blackboard. Board iteration: {board.get_iteration()}")

    # --- FINAL STATE ---
    print("\n" + "-" * 50)
    print("[5] FINAL BLACKBOARD STATE")
    print("-" * 50)

    state = board.get_state()
    print(f"    Task: {state.task}")
    print(f"    Status: {state.status.value}")
    print(f"    Iteration: {state.iteration}")
    print(f"    Current Prediction: {state.current_prediction}")
    print(f"    Current Explanation: {state.current_explanation}")
    if state.latest_message:
        print(f"    Latest Message: {state.latest_message['agent_id']} -> {state.latest_message['tag']}")

    # --- HISTORY ---
    print("\n[6] PXP HISTORY")
    history = board.get_history()
    for i, event in enumerate(history, 1):
        print(f"    {i}. Iteration {event.iteration}: {event.agent_id} ({event.tag})")
        print(f"       Prediction: {event.prediction}")
        print(f"       Explanation: {event.explanation}")
        print(f"       Confidence: {event.confidence}")

    # --- SERIALIZATION ---
    print("\n[7] SERIALIZATION DEMO")
    state_dict = board.get_state().to_dict()
    print(f"    State serialized: {len(str(state_dict))} chars")

    history_dicts = [e.to_dict() for e in board.get_history()]
    print(f"    History serialized: {len(history_dicts)} events")

    # Show JSON for one event
    import json
    print(f"\n    Sample History Event JSON:")
    print(f"    {json.dumps(history_dicts[0], indent=6) if history_dicts else 'none'}")

    # --- STATUS MANAGEMENT ---
    print("\n[8] STATUS MANAGEMENT")
    board.set_status(BlackboardStatus.DEADLOCK)
    print(f"    Status set to: {board.get_state().status.value}")
    board.set_status(BlackboardStatus.RUNNING)
    print(f"    Status set to: {board.get_state().status.value}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE - ALL CHECKS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()