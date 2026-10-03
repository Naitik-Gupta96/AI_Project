#!/usr/bin/env python
"""
Summarize a pilot results file (descriptive statistics only).

Usage:
    python experiments/analyze_results.py            # newest file in experiments/results/
    python experiments/analyze_results.py PATH.json  # a specific file

Writes PATH_summary.csv next to the results file and prints both tables.
"""

import csv
import sys
from pathlib import Path

from ai_project.experiment import load_results, summarize

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, tuple):
        return f"[{value[0]:.2f}, {value[1]:.2f}]"
    return str(value)


def print_table(rows, columns) -> None:
    widths = [max(len(c), *(len(_fmt(r.get(c))) for r in rows)) for c in columns]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths, strict=True)))
    for r in rows:
        print("  ".join(_fmt(r.get(c)).ljust(w) for c, w in zip(columns, widths, strict=True)))


def main() -> int:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        files = sorted(RESULTS_DIR.glob("pilot_*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            print("No results found. Run: python experiments/run_experiment.py")
            return 1
        path = files[-1]

    doc = load_results(path)
    summary = summarize(doc)
    p = doc["parameters"]
    print(f"{path}\n{doc['mode']}")
    print(f"seed={p['seed']} tasks={p['n_tasks']} options={p['n_options']} "
          f"provider={doc['provider']['name']} commit={doc['git_commit']}\n")

    print("By counterfactual fraction (pooled over agent subsets; trials share tasks):")
    print_table(summary["by_fraction"], [
        "cf_fraction", "trials", "deadlock_rate", "deadlocked", "deadlocked_feasible",
        "recovery_rate", "recovery_rate_feasible", "final_consensus_rate",
        "best_decision_rate", "mean_iterations"])
    print("\nBy condition (one subset of counterfactual-capable agents):")
    print_table(summary["by_condition"], [
        "cf_agents", "trials", "deadlocked_feasible", "recovered",
        "recovery_rate_feasible", "recovery_rate_feasible_ci95", "mean_branches_replayed"])
    print("\nDescriptive results of a deterministic pilot over synthetic tasks; "
          "not a validated research finding.")

    csv_path = path.with_name(path.stem + "_summary.csv")
    rows = summary["by_condition"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(v) if isinstance(v, tuple) else v for k, v in row.items()})
    print(f"\nPer-condition summary written to {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
