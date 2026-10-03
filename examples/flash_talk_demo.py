#!/usr/bin/env python
"""
Flash Talk demo without a browser: the same backend path as the UI's
Flash Talk tab (``ai_project.ui.flash_talk_demo``), printed as text.

Usage:
    python examples/flash_talk_demo.py                      # critic is counterfactual-capable
    python examples/flash_talk_demo.py --cf analyst critic specialist
    python examples/flash_talk_demo.py --cf                 # nobody: the deadlock stands
    python examples/flash_talk_demo.py --provider ollama --model qwen3:4b
    python examples/flash_talk_demo.py --json run.json      # also export the full run
"""

import argparse
import json
import sys
import textwrap

from ai_project.llm import MockLLMProvider, OllamaProvider
from ai_project.tasks import ROLES, flash_talk_task
from ai_project.ui import FLASH_TALK_CF_AGENTS, RunEvent, flash_talk_demo

RULE = "-" * 72
NOTES = {"inherited": "  (inherited)", "intervention": "  (COUNTERFACTUAL REVISION)"}


def show(events: list[RunEvent]) -> None:
    for e in events:
        if not e.is_message:
            print(f"\n{'':>14}[ {e.tag} ]  {e.reason}\n")
            continue
        alt = f" -> names {e.alternative}" if e.alternative else ""
        conf = f"{e.confidence:.2f}" if e.confidence is not None else "-"
        print(f"  {e.step:02d}  {e.agent_id:<10} {e.tag:<6} {e.prediction}{alt}"
              f"  [conf {conf}]{NOTES.get(e.kind, '')}")
        for line in textwrap.wrap(e.explanation or "", 62):
            print(f"{'':>8}{line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Flash Talk demo (CLI fallback).")
    parser.add_argument("--cf", nargs="*", choices=ROLES, default=list(FLASH_TALK_CF_AGENTS),
                        help="counterfactual-capable agents (default: critic)")
    parser.add_argument("--provider", choices=["mock", "ollama"], default="mock")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--json", metavar="PATH", help="write the full run to PATH")
    args = parser.parse_args()

    provider = MockLLMProvider() if args.provider == "mock" else OllamaProvider(args.model)
    if not provider.is_available():
        print(f"Provider '{args.provider}' ({args.model}) is not available.")
        return 1

    demo = flash_talk_demo(args.cf, provider)
    print(RULE)
    print(f"MODE: {demo.original.mode}  (provider: {provider.describe()})")
    print("Real Blackboard, Scheduler, deadlock detector and counterfactual engine.")
    print(RULE)
    print("TASK")
    for line in textwrap.wrap(flash_talk_task().question, 70):
        print(f"  {line}")
    print(f"Counterfactual-capable agents: {', '.join(demo.cf_agents) or 'none'}")

    print(f"\n{RULE}\nORIGINAL RUN\n")
    show(demo.original.events)

    if demo.deadlocked:
        print(f"{RULE}\nCOUNTERFACTUAL REFLECTION\n")
        if not demo.reflections:
            print("  No counterfactual-capable agent: the deadlock stands.")
        for r in demo.reflections:
            verdict = f"would have sent {r.revised}" if r.revised else "would not change it"
            replay = f" -> replayed: {r.outcome}" if r.replayed else ""
            print(f"  {r.agent_id} on step {r.step} ({r.original}): {verdict}{replay}")

        cf = demo.shown_branch
        if cf is not None:
            print(f"\n{RULE}\nREPLAY (branch at step {cf.branch_point})\n")
            show(cf.branch.events)
            print(RULE)
            print(f"original        {demo.original.outcome.status} on "
                  f"{demo.original.outcome.prediction} after {demo.original.outcome.iterations} steps")
            print(f"counterfactual  {cf.branch.outcome.status} on {cf.branch.outcome.prediction} "
                  f"after {cf.branch.outcome.iterations} steps")
            print(f"diverged at     step {cf.divergence_step}")
    print(f"original board  {'unchanged' if demo.original_preserved else 'CHANGED (bug)'}")
    print(RULE)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(demo.to_dict(), f, indent=2)
        print(f"Full run written to {args.json}")
    return 0 if demo.original_preserved else 1


if __name__ == "__main__":
    sys.exit(main())
