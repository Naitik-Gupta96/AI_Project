"""
Summaries of an ablation run (``trials.jsonl`` -> ``summary.json`` and ``groups.csv``).

Per group (share of counterfactual-capable agents), per benchmark and overall:

    convergence_success  consensus within the message budget AND an accurate answer
                         (the spec's Convergence Success Rate), with a 95% Wilson interval
    consensus, accuracy  the two parts separately
    deadlock             sessions that deadlocked at least once
    recovered            share of deadlocked sessions that still reached consensus
    intelligibility      share of sessions at each level (Ultra-Strong, Strong, One-Way, None),
                         whole session, as defined in Mestha et al.
    tokens               mean prompt + completion tokens per instance, all phases, with a
                         95% bootstrap interval; also live-board and sandbox tokens separately

Each counterfactual group is compared with the control group (0%) on the same
tasks with an exact McNemar test on convergence success. For MSCoRe the
accuracy at several ROUGE-L thresholds is reported as well.
"""

import csv
import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

LEVELS = ("Ultra-Strong", "Strong", "One-Way", "None")
MSCORE_THRESHOLDS = (0.2, 0.3, 0.4)


def load_trials(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_mean(values: Sequence[float], seed: int = 0,
                   rounds: int = 2000) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(rounds))
    return (means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1])


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _tokens(row: dict[str, Any], phase: str = "total") -> float | None:
    usage = (row.get("usage") or {}).get(phase) or {}
    if not usage.get("reported"):
        return None
    return float(usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))


def _calls(row: dict[str, Any]) -> int:
    return int(((row.get("usage") or {}).get("total") or {}).get("calls", 0))


def _rate(rows: Iterable[dict[str, Any]], key: str) -> float:
    rows = list(rows)
    return sum(1 for r in rows if r.get(key)) / len(rows) if rows else 0.0


def group_row(group: str, benchmark: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if not r.get("failed")]
    n = len(ok)
    success = sum(1 for r in ok if r.get("convergence_success"))
    deadlocked = [r for r in ok if r.get("deadlocked")]
    levels = defaultdict(int)
    for r in ok:
        levels[(r.get("intelligibility") or {}).get("session", "None")] += 1
    totals = [t for t in (_tokens(r) for r in ok) if t is not None]
    live = [t for t in (_tokens(r, "live") for r in ok) if t is not None]
    sandbox = [t for t in (_tokens(r, "sandbox") for r in ok) if t is not None]
    row = {
        "group": group,
        "cf_fraction": ok[0]["cf_fraction"] if ok else None,
        "benchmark": benchmark,
        "trials": n,
        "errors": len(rows) - n,
        "convergence_success": success / n if n else 0.0,
        "convergence_ci": list(wilson(success, n)),
        "consensus": _rate(ok, "consensus"),
        "accuracy": sum(1 for r in ok if (r.get("score") or {}).get("correct")) / n if n else 0.0,
        "score_mean": (sum((r.get("score") or {}).get("value", 0.0) for r in ok) / n) if n else 0.0,
        "deadlock": len(deadlocked) / n if n else 0.0,
        "recovered": (sum(1 for r in deadlocked if r.get("recovered")) / len(deadlocked)
                      if deadlocked else 0.0),
        "messages_mean": sum(r.get("messages", 0) for r in ok) / n if n else 0.0,
        "tokens_mean": sum(totals) / len(totals) if totals else None,
        "tokens_ci": list(bootstrap_mean(totals)) if totals else None,
        "live_tokens_mean": sum(live) / len(live) if live else None,
        "sandbox_tokens_mean": sum(sandbox) / len(sandbox) if sandbox else None,
        "calls_mean": (sum(_calls(r) for r in ok) / n if n else 0.0),
    }
    for level in LEVELS:
        row[level.lower().replace("-", "_")] = levels[level] / n if n else 0.0
    if benchmark == "mscore":
        for t in MSCORE_THRESHOLDS:
            hits = sum(1 for r in ok if r.get("consensus")
                       and ((r.get("score") or {}).get("value") or 0) >= t)
            row[f"success_at_{t}"] = hits / n if n else 0.0
    return row


def summarize(trials: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    names = sorted({r["benchmark"] for r in trials})
    pooled = len(names) > 1  # an "all" row only adds information with several benchmarks
    for r in trials:
        by[(r["group"], r["benchmark"])].append(r)
        if pooled:
            by[(r["group"], "all")].append(r)
    groups = sorted({r["group"] for r in trials}, key=lambda g: int(g.removeprefix("cf")))
    benchmarks = names + (["all"] if pooled else [])
    rows = [group_row(g, b, by[(g, b)]) for g in groups for b in benchmarks if by[(g, b)]]

    tests = []
    control = groups[0] if groups else None
    for b in benchmarks:
        base = {r["task_id"]: r for r in by.get((control, b), []) if not r.get("failed")}
        for g in groups[1:]:
            pairs = [(base[r["task_id"]], r) for r in by.get((g, b), [])
                     if r["task_id"] in base and not r.get("failed")]
            if not pairs:
                continue
            worse = sum(1 for c, x in pairs if c.get("convergence_success")
                        and not x.get("convergence_success"))
            better = sum(1 for c, x in pairs if not c.get("convergence_success")
                         and x.get("convergence_success"))
            tests.append({"comparison": f"{g} vs {control}", "benchmark": b, "pairs": len(pairs),
                          "b": worse, "c": better, "p_value": mcnemar_exact(worse, better)})
    return {"groups": rows, "tests": tests}


def health(run_dir: str | Path) -> dict[str, Any]:
    """
    Problems that make a run's numbers untrustworthy (``bb check``).

    ``problems`` must be empty before results are reported; ``warnings`` need a look.
    """
    run = Path(run_dir)
    trials = load_trials(run / "trials.jsonl")
    meta_path = run / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    planned = meta.get("trials")
    provider = (meta.get("config") or {}).get("provider", "")
    problems: list[str] = []
    warnings: list[str] = []
    failed = [r for r in trials if r.get("failed")]
    ok = [r for r in trials if not r.get("failed")]
    if planned is not None and len(trials) < planned:
        warnings.append(f"{len(trials)} of {planned} planned trials are done (rerun to resume)")
    if failed:
        problems.append(f"{len(failed)} trial(s) crashed, e.g. {failed[0]['trial_id']}: "
                        f"{failed[0].get('error')}")
    per_bench: dict[str, dict[str, Any]] = {}
    for bench in sorted({r["benchmark"] for r in ok}):
        rows = [r for r in ok if r["benchmark"] == bench]
        statuses: dict[str, int] = defaultdict(int)
        for r in rows:
            statuses[r["status"]] += 1
        session_failed = sum(1 for r in rows if r.get("stop_reason") == "failed")
        format_mean = sum(r.get("format_errors", 0) for r in rows) / len(rows)
        grader_errors = [r for r in rows if ((r.get("score") or {}).get("detail") or {})
                         .get("grader_error")]
        fallback = [r for r in rows if "rouge-1" in str(((r.get("score") or {}).get("detail")
                                                          or {}).get("judge", ""))]
        per_bench[bench] = {"trials": len(rows), "statuses": dict(statuses),
                            "failed_sessions": session_failed,
                            "format_errors_mean": round(format_mean, 2),
                            "grader_errors": len(grader_errors),
                            "judge_fallbacks": len(fallback)}
        if session_failed / len(rows) > 0.05:
            problems.append(f"{bench}: {session_failed}/{len(rows)} sessions failed because an "
                            "agent produced no valid message (see format_error events)")
        if format_mean > 1.0:
            warnings.append(f"{bench}: {format_mean:.2f} rejected attempts per session on average")
        if grader_errors:
            detail = grader_errors[0]["score"]["detail"]["grader_error"]
            problems.append(f"{bench}: the grader raised on {len(grader_errors)} trial(s), e.g. "
                            f"{grader_errors[0]['trial_id']}: {detail}")
        if fallback:
            warnings.append(f"{bench}: {len(fallback)} string_approximate answer(s) scored by "
                            "ROUGE-1 because the judge was unavailable")
    if provider and provider != "mock":
        unreported = [r for r in ok
                      if not ((r.get("usage") or {}).get("total") or {}).get("reported")]
        if unreported:
            problems.append(f"{len(unreported)} trial(s) have no token counts from the provider")
    return {"trials": len(trials), "planned": planned, "provider": provider,
            "benchmarks": per_bench, "problems": problems, "warnings": warnings}


def write_report(run_dir: str | Path) -> dict[str, Any]:
    """Recompute summary.json and groups.csv for a run directory; returns the summary."""
    run = Path(run_dir)
    trials = load_trials(run / "trials.jsonl")
    meta_path = run / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    summary = {"name": run.name, "meta": meta, **summarize(trials)}
    (run / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    first = summary["groups"][0] if summary["groups"] else {}
    columns = [k for k, v in first.items() if not isinstance(v, list)]
    with open(run / "groups.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary["groups"])
    return summary
