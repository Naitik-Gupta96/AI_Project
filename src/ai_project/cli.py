"""
Command line: ``bb <command>``.

    bb run      run one session and print its transcript
"""

import argparse
import json
import sys
import textwrap
from collections.abc import Sequence

from ai_project.agents import build_team
from ai_project.benchmarks import SyntheticBenchmark, architecture_task
from ai_project.benchmarks.base import Task
from ai_project.blackboard import JsonStore
from ai_project.blackboard.models import INTERVENTION, MESSAGE
from ai_project.counterfactual import CounterfactualConfig
from ai_project.llm.factory import make_provider
from ai_project.scheduler import SchedulerConfig
from ai_project.session import Session, SessionConfig

WIDTH = 96
PROVIDER_HELP = "mock | ollama:<model> | vllm:<model> | openai:<model>@<url> | hf:<model>"


def _task(spec: str) -> tuple[Task, SyntheticBenchmark]:
    if spec == "architecture":
        return architecture_task(), SyntheticBenchmark()
    if spec.startswith("synthetic:"):
        seed, _, index = spec.removeprefix("synthetic:").partition("/")
        bench = SyntheticBenchmark()
        return bench.load(int(index or 0) + 1, seed=int(seed or 0))[-1], bench
    raise SystemExit(f"Unknown task '{spec}'. Use 'architecture' or 'synthetic:<seed>/<index>'.")


def _wrap(text: str, indent: int) -> str:
    return textwrap.fill(text, WIDTH, initial_indent=" " * indent, subsequent_indent=" " * indent)


def print_transcript(session: Session, result) -> None:
    print("=" * WIDTH)
    print(_wrap(session.task.question, 0))
    print(f"options: {', '.join(session.task.options) or '(free-form)'}"
          f"   counterfactual agents: {', '.join(session.cf_agents) or 'none'}")
    print("-" * WIDTH)
    for event in session.board.get_events():
        if event.kind == MESSAGE:
            m = event.data["message"]
            j = m["judgment"]
            judged = "" if j is None else (
                f"  [match={'y' if j['prediction_matches'] else 'n'} "
                f"agree={'y' if j['explanation_agrees'] else 'n'} "
                f"changed={'y' if j['changed'] else 'n'}]")
            print(f"#{m['iteration']:<3}{m['agent_id']:<12}{m['tag']:<8}{m['prediction']}{judged}")
            print(_wrap(m["explanation"], 15))
        elif event.kind == "status" and event.data["status"] in ("DEADLOCK", "CONSENSUS"):
            print(f"{'':>15}[{event.data['status']}] {event.data['reason']}")
        elif event.kind == INTERVENTION:
            data = event.data
            branches = data.get("branches", [])
            print(f"{'':>15}counterfactual: {len(branches)} sandbox branch(es)")
            for b in branches:
                c = b["candidate"]
                print(f"{'':>17}{b['agent_id']} #{b['target']['iteration']} "
                      f"{b['target']['tag']} {b['target']['prediction']} -> {c['tag']} "
                      f"{c['prediction']}: {b['status']}, credit {b['credit']:+.2f}")
            if data["applied"]:
                print(f"{'':>15}applied: {data['reason']}; weight "
                      f"{data['weight_before']} -> {data['weight_after']}")
            else:
                print(f"{'':>15}not applied: {data['reason']}")
    print("-" * WIDTH)
    score = result.score.to_dict() if result.score else None
    print(f"status {result.status}   answer {result.final_prediction}   "
          f"correct {score['correct'] if score else '-'}   messages {result.messages}   "
          f"intelligibility {result.intelligibility['session']}")
    usage = result.usage["total"]
    tokens = (f"{usage['prompt_tokens']}+{usage['completion_tokens']} tokens"
              if usage["reported"] else "no token counts (mock)")
    print(f"provider calls {usage['calls']}   {tokens}   {result.runtime_ms / 1000:.1f}s")


def cmd_run(args: argparse.Namespace) -> int:
    task, bench = _task(args.task)
    provider = make_provider(args.provider, cache=args.cache, max_in_flight=args.concurrency)
    team = build_team(task, provider)
    config = SessionConfig(
        scheduler=SchedulerConfig(max_messages=args.max_messages,
                                  max_concurrent_agents=args.concurrency_agents),
        reject_after=args.reject_after,
        counterfactual=CounterfactualConfig(apply=args.apply),
    )
    store = JsonStore(args.store) if args.store else None
    session = Session(task, team, args.cf, config, store=store, benchmark=bench)
    result = session.run()
    if args.json:
        json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        print_transcript(session, result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bb", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one session and print its transcript")
    run.add_argument("--task", default="architecture",
                     help="'architecture' or 'synthetic:<seed>/<index>'")
    run.add_argument("--provider", default="mock", help=PROVIDER_HELP)
    run.add_argument("--cf", nargs="*", default=[], metavar="AGENT",
                     help="counterfactual-capable agents")
    run.add_argument("--apply", default="both", choices=["prompt", "weight", "both"])
    run.add_argument("--max-messages", type=int, default=12)
    run.add_argument("--reject-after", type=int, default=3)
    run.add_argument("--concurrency", type=int, default=4, help="model requests in flight")
    run.add_argument("--concurrency-agents", type=int, default=1,
                     help="agents drafting in parallel per round")
    run.add_argument("--cache", default=None, help="SQLite response cache path")
    run.add_argument("--store", default=None, help="directory for the session's event log")
    run.add_argument("--json", action="store_true", help="print the full result as JSON")
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
