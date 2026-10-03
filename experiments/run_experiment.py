#!/usr/bin/env python
"""
Run the end-to-end pilot and write a results file.

Every trial executes the real pipeline (Blackboard, agents, Scheduler,
deadlock detection, counterfactual branching and replay). With the default
deterministic mock provider the output is reproducible from the seed.

Usage:
    python experiments/run_experiment.py                      # 100 tasks, seed 42
    python experiments/run_experiment.py --tasks 200 --seed 7
    python experiments/run_experiment.py --provider ollama --model qwen3:4b --tasks 5
"""

import argparse
import sys
import time
from pathlib import Path

from ai_project.experiment import run_pilot, save_results
from ai_project.llm import MockLLMProvider, OllamaProvider

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the end-to-end pilot experiment.")
    parser.add_argument("--tasks", type=int, default=100, help="number of generated tasks")
    parser.add_argument("--seed", type=int, default=42, help="task-generation seed")
    parser.add_argument("--options", type=int, default=3, help="options per task")
    parser.add_argument("--objection-rate", type=float, default=0.3)
    parser.add_argument("--provider", choices=["mock", "ollama"], default="mock")
    parser.add_argument("--model", default="qwen3:4b", help="Ollama model (with --provider ollama)")
    parser.add_argument("--out", type=Path, help="output path (default: experiments/results/...)")
    args = parser.parse_args()

    if args.provider == "ollama":
        provider = OllamaProvider(model=args.model, seed=args.seed)
        if not provider.is_available():
            print(f"Ollama model '{args.model}' is not available at {provider.host}.")
            return 1
    else:
        provider = MockLLMProvider()

    out = args.out or RESULTS_DIR / f"pilot_{args.provider}_seed{args.seed}_n{args.tasks}.json"

    def progress(done: int, total: int) -> None:
        if done == total or done % max(1, total // 10) == 0:
            print(f"  {done}/{total} trials", flush=True)

    start = time.perf_counter()
    doc = run_pilot(
        n_tasks=args.tasks,
        seed=args.seed,
        n_options=args.options,
        objection_rate=args.objection_rate,
        provider=provider,
        progress=progress,
    )
    save_results(doc, out)
    print(f"{doc['mode']}")
    print(f"{len(doc['trials'])} trials in {time.perf_counter() - start:.1f}s -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
