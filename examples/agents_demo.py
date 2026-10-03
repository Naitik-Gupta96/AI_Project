#!/usr/bin/env python
"""
Agents demo: what happens inside one agent decision.

For each of analyst, critic and specialist (in that order, on the Flash
Talk task) this prints the pipeline every decision goes through:

    AgentContext -> prompt -> provider -> raw JSON -> AgentDecision -> PXPMessage

and publishes the message to the Blackboard. No scheduler here: the order
is fixed so the pipeline is easy to follow. See flash_talk_demo.py for the
full system.

Usage:
    python examples/agents_demo.py
    python examples/agents_demo.py --show-prompt     # also print the full prompt
"""

import argparse
import textwrap

from ai_project.agents import build_team
from ai_project.blackboard import Blackboard
from ai_project.llm import LLMRequest
from ai_project.tasks import flash_talk_task

RULE = "-" * 72


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent decision pipeline demo.")
    parser.add_argument("--show-prompt", action="store_true", help="print each full prompt")
    args = parser.parse_args()

    task = flash_talk_task()
    board = Blackboard()
    board.initialize_task(task.question, task.board_metadata())
    print(f"Task: {task.question}\nProvider: deterministic mock (rule-based, no model)\n")

    for agent in build_team(task):
        print(RULE)
        print(f"{agent.agent_id.upper()}  ({agent.description})")
        context = agent.build_context(board)
        print(f"  context:  iteration={context.iteration} proposal={context.proposal} "
              f"history={len(context.history)} event(s)")
        print(f"  evidence: {agent.evidence.to_dict()}")

        prompt = agent.render_prompt(context)
        if args.show_prompt:
            print(textwrap.indent(prompt, "    | "))
        else:
            print(f"  prompt:   {len(prompt)} characters (--show-prompt to print)")

        raw = agent.llm_provider.generate(LLMRequest(prompt, context)).text
        print(f"  raw:      {raw}")
        decision = agent.decide(context)
        message = decision.to_pxp_message(agent.agent_id, board.get_iteration() + 1)
        board.publish_message(message)
        print(f"  message:  {message.tag.value} {message.prediction} "
              f"(confidence {message.confidence:.2f}, rule '{message.metadata['rule']}')")

    print(RULE)
    state = board.get_state()
    print(f"Board: iteration {state.iteration}, status {state.status.value}, "
          f"current prediction {state.current_prediction}")
    for e in board.get_history():
        print(f"  {e.iteration}. {e.agent_id:<10} {e.tag:<6} {e.prediction}")


if __name__ == "__main__":
    main()
