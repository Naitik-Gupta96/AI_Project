"""
Command line: ``bb <command>``.

    bb run      run one session and print its transcript
    bb serve    start the API server and the web UI
    bb fetch    download benchmark data
    bb ablate   run an ablation experiment from a TOML config
    bb report   summary, figures and LaTeX tables for an experiment run
    bb check    health checks for an experiment run (exit code 1 on problems)
"""

import argparse
import json
import sys
import textwrap
import time
from collections.abc import Sequence

from ai_project.agents import build_team
from ai_project.benchmarks import registry
from ai_project.benchmarks.base import Benchmark, Task
from ai_project.blackboard import JsonStore
from ai_project.blackboard.models import INTERVENTION, MESSAGE
from ai_project.counterfactual import CounterfactualConfig
from ai_project.llm.factory import make_provider
from ai_project.scheduler import SchedulerConfig
from ai_project.session import Session, SessionConfig

WIDTH = 96
PROVIDER_HELP = "mock | ollama:<model> | vllm:<model> | openai:<model>@<url> | hf:<model>"


def _task(benchmark: str, task_id: str | None) -> tuple[Task, Benchmark]:
    bench = registry.get_benchmark(benchmark)
    try:
        if task_id:
            return bench.get(task_id), bench
        return bench.load(1, seed=0)[0], bench
    except (KeyError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from None


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
    task, bench = _task(args.benchmark, args.task_id)
    provider = make_provider(args.provider, cache=args.cache, max_in_flight=args.concurrency)
    team = build_team(task, provider, tools=registry.tool_factory(bench), max_tool_calls=4)
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


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn

        from ai_project.server.app import create_app
    except ImportError:
        raise SystemExit('The server needs: pip install -e ".[server]"') from None
    print(f"Serving on http://{args.host}:{args.port}  (runs in {args.runs})")
    app = create_app(args.runs, experiments_root=args.experiments)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from ai_project.benchmarks.fetch import FETCHERS
    for name in args.benchmarks:
        print(f"{name}:")
        path = FETCHERS[name](small=args.small)
        print(f"  -> {path}")
    return 0


def cmd_ablate(args: argparse.Namespace) -> int:
    from ai_project.experiments import ExperimentConfig, ExperimentRunner, write_report

    config = ExperimentConfig.load(args.config)
    start = time.perf_counter()

    def progress(done: int, total: int, row: dict) -> None:
        if done % args.every == 0 or done == total:
            rate = done / max(1e-9, time.perf_counter() - start)
            status = row.get("status") or f"failed: {row.get('error')}"
            print(f"  {done}/{total}  {row['trial_id']}: {status}  ({rate:.1f} trials/s)")

    runner = ExperimentRunner(config, args.out, progress=progress)
    print(f"{config.name}: provider {config.provider}, results in {runner.out}")
    runner.run(resume=not args.restart)
    summary = write_report(runner.out)
    _print_summary(summary)
    if not args.no_plots:
        _plots(summary, runner.out)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from ai_project.experiments import write_report
    summary = write_report(args.run)
    _print_summary(summary)
    if not args.no_plots:
        _plots(summary, args.run)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from ai_project.experiments.analysis import health
    report = health(args.run)
    print(f"{args.run}: {report['trials']} trials"
          + (f" of {report['planned']}" if report["planned"] else "")
          + f", provider {report['provider'] or '?'}")
    for bench, row in report["benchmarks"].items():
        statuses = ", ".join(f"{k} {v}" for k, v in sorted(row["statuses"].items()))
        print(f"  {bench:<14} {row['trials']:>4} trials  {statuses}  "
              f"format errors/session {row['format_errors_mean']}  "
              f"failed sessions {row['failed_sessions']}  grader errors {row['grader_errors']}  "
              f"judge fallbacks {row['judge_fallbacks']}")
    for w in report["warnings"]:
        print(f"WARNING  {w}")
    for p in report["problems"]:
        print(f"PROBLEM  {p}")
    print("OK" if not report["problems"] else "NOT OK: fix the problems before reporting results")
    return 1 if report["problems"] else 0


def _plots(summary: dict, run_dir) -> None:
    from ai_project.experiments.plots import make_figures
    try:
        for path in make_figures(summary, run_dir):
            print(f"  wrote {path}")
    except RuntimeError as exc:
        print(f"  no figures: {exc}")


def _print_summary(summary: dict) -> None:
    print(f"\n{'group':<7}{'benchmark':<15}{'n':>5}{'converge':>10}{'consensus':>11}"
          f"{'accuracy':>10}{'deadlock':>10}{'recover':>9}{'ultra':>7}{'tokens':>10}")
    for r in summary["groups"]:
        tokens = "-" if r.get("tokens_mean") is None else f"{r['tokens_mean']:,.0f}"
        print(f"{r['group']:<7}{r['benchmark']:<15}{r['trials']:>5}{r['convergence_success']:>10.2f}"
              f"{r['consensus']:>11.2f}{r['accuracy']:>10.2f}{r['deadlock']:>10.2f}"
              f"{r['recovered']:>9.2f}{r['ultra_strong']:>7.2f}{tokens:>10}")
    for t in summary["tests"]:
        print(f"  {t['comparison']} on {t['benchmark']}: McNemar b={t['b']} c={t['c']} "
              f"p={t['p_value']:.3g} ({t['pairs']} pairs)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bb", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one session and print its transcript")
    run.add_argument("--benchmark", default="synthetic", choices=registry.names())
    run.add_argument("--task-id", default="architecture",
                     help="task id (synthetic: 'architecture' or 'syn-s<seed>-<index>'); "
                          "omit for the benchmark's first task")
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

    serve = sub.add_parser("serve", help="start the API and web UI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--runs", default="runs", help="directory for session logs and caches")
    serve.add_argument("--experiments", default="runs/experiments",
                       help="where bb ablate writes experiment runs")
    serve.set_defaults(func=cmd_serve)

    fetch = sub.add_parser("fetch", help="download benchmark data into $BB_DATA_DIR (data/)")
    fetch.add_argument("benchmarks", nargs="+", choices=["mscore", "kramabench", "medagentbench"])
    fetch.add_argument("--small", action="store_true", help="a small subset for development")
    fetch.set_defaults(func=cmd_fetch)

    ablate = sub.add_parser("ablate", help="run an ablation experiment")
    ablate.add_argument("config", help="TOML config, e.g. experiments/configs/ablation.toml")
    ablate.add_argument("--out", default="runs/experiments")
    ablate.add_argument("--restart", action="store_true", help="discard finished trials")
    ablate.add_argument("--every", type=int, default=25, help="print progress every N trials")
    ablate.add_argument("--no-plots", action="store_true")
    ablate.set_defaults(func=cmd_ablate)

    report = sub.add_parser("report", help="summarize an experiment run")
    report.add_argument("run", help="run directory, e.g. runs/experiments/ablation-qwen2.5-7b")
    report.add_argument("--no-plots", action="store_true")
    report.set_defaults(func=cmd_report)

    check = sub.add_parser("check", help="health checks for an experiment run")
    check.add_argument("run", help="run directory")
    check.set_defaults(func=cmd_check)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
