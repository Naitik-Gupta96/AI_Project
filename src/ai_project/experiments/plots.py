"""
Figures and LaTeX tables for an ablation run (``bb report``; needs ``pip install -e ".[plots]"``).

    figures/convergence.svg     convergence success vs share of counterfactual-capable agents,
                                one line per benchmark plus the pooled result, 95% Wilson intervals
    figures/intelligibility.svg share of sessions at each intelligibility level, per group
    figures/tokens.svg          mean tokens per instance, live board vs counterfactual sandbox
    tables/groups.tex           the main metrics per group and benchmark

Colours: benchmarks use the first three slots of the validated categorical palette (blue,
orange, aqua); the pooled line is neutral ink; intelligibility levels use one ordinal blue ramp.
"""

from pathlib import Path
from typing import Any

INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
SERIES = {"mscore": "#2a78d6", "kramabench": "#eb6834", "medagentbench": "#1baf7a",
          "synthetic": "#4a3aa7"}
NAMES = {"mscore": "MSCoRe", "kramabench": "KramaBench", "medagentbench": "MedAgentBench",
         "synthetic": "Synthetic", "all": "All benchmarks"}
LEVEL_COLORS = {"none": "#cde2fb", "one_way": "#86b6ef", "strong": "#2a78d6",
                "ultra_strong": "#0d366b"}
LEVEL_NAMES = {"none": "None", "one_way": "One-Way", "strong": "Strong",
               "ultra_strong": "Ultra-Strong"}


def _style(plt: Any) -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.edgecolor": "#c3c2b7",
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "legend.frameon": False,
        "svg.fonttype": "none",
    })


def _rows(summary: dict[str, Any], benchmark: str) -> list[dict[str, Any]]:
    rows = [r for r in summary["groups"] if r["benchmark"] == benchmark]
    return sorted(rows, key=lambda r: r["cf_fraction"])


def _pooled(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """The "all" rows, or the only benchmark's rows when there is just one."""
    return _rows(summary, "all") or _rows(summary, summary["groups"][0]["benchmark"])


def convergence(summary: dict[str, Any], out: Path, plt: Any) -> Path:
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.set_axisbelow(True)
    series = [b for b in ("mscore", "kramabench", "medagentbench", "synthetic", "all")
              if _rows(summary, b)]
    handles, ends = [], []
    for bench in series:
        rows = _rows(summary, bench)
        x = [100 * r["cf_fraction"] for r in rows]
        y = [r["convergence_success"] for r in rows]
        lo = [r["convergence_success"] - r["convergence_ci"][0] for r in rows]
        hi = [r["convergence_ci"][1] - r["convergence_success"] for r in rows]
        color = INK if bench == "all" else SERIES[bench]
        width = 2.4 if bench == "all" else 1.8
        ax.errorbar(x, y, yerr=[lo, hi], color=color, linewidth=width, marker="o", markersize=5,
                    markeredgecolor=SURFACE, markeredgewidth=1.2, capsize=0, elinewidth=1)
        handles.append(Line2D([], [], color=color, linewidth=width, marker="o", markersize=5,
                              markeredgecolor=SURFACE, label=NAMES[bench]))
        ends.append([y[-1], x[-1], NAMES[bench]])
    # direct labels at the line ends, nudged apart so they never overlap
    ends.sort()
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 0.055)
    for y_end, x_end, name in ends:
        ax.annotate(name, (x_end, y_end), xytext=(10, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK_2)
    ax.set_xticks([0, 33, 67, 100], ["0%", "33%", "67%", "100%"])
    ax.set_xlim(-6, 140)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_xlabel("Counterfactual-capable agents")
    ax.set_ylabel("Convergence success (95% CI)")
    if len(handles) > 1:
        ax.legend(handles=handles, loc="upper left", fontsize=8.5, ncols=2)
    path = out / "convergence.svg"
    fig.tight_layout()
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"), dpi=200)
    plt.close(fig)
    return path


def intelligibility(summary: dict[str, Any], out: Path, plt: Any) -> Path:
    rows = _pooled(summary)
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.set_axisbelow(True)
    labels = [f"{round(100 * r['cf_fraction'])}%" for r in rows]
    left = [0.0] * len(rows)
    for level in ("ultra_strong", "strong", "one_way", "none"):
        values = [r.get(level, 0.0) for r in rows]
        bars = ax.barh(labels, values, left=left, color=LEVEL_COLORS[level], height=0.62,
                       edgecolor=SURFACE, linewidth=2, label=LEVEL_NAMES[level])
        for bar, v in zip(bars, values, strict=True):
            if v >= 0.07:
                dark = level in ("strong", "ultra_strong")
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2,
                        f"{v:.0%}", ha="center", va="center", fontsize=8.5,
                        color=SURFACE if dark else INK)
        left = [a + b for a, b in zip(left, values, strict=True)]
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel("Share of sessions (whole-session intelligibility)")
    ax.set_ylabel("Counterfactual-capable")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncols=4, fontsize=8.5)
    path = out / "intelligibility.svg"
    fig.tight_layout()
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"), dpi=200)
    plt.close(fig)
    return path


def tokens(summary: dict[str, Any], out: Path, plt: Any) -> Path | None:
    rows = _pooled(summary)
    if not rows or rows[0].get("tokens_mean") is None:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.set_axisbelow(True)
    labels = [f"{round(100 * r['cf_fraction'])}%" for r in rows]
    live = [r.get("live_tokens_mean") or 0 for r in rows]
    sandbox = [r.get("sandbox_tokens_mean") or 0 for r in rows]
    ax.bar(labels, live, color=SERIES["mscore"], width=0.56, edgecolor=SURFACE, linewidth=2,
           label="Live board")
    ax.bar(labels, sandbox, bottom=live, color=SERIES["kramabench"], width=0.56,
           edgecolor=SURFACE, linewidth=2, label="Counterfactual sandbox")
    for i, r in enumerate(rows):
        lo, hi = r["tokens_ci"]
        ax.vlines(i, lo, hi, color=INK_2, linewidth=1)
        ax.text(i, hi, f" {r['tokens_mean']:,.0f}", ha="center", va="bottom", fontsize=8.5,
                color=INK_2)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.set_xlabel("Counterfactual-capable agents")
    ax.set_ylabel("Tokens per instance (mean)")
    ax.legend(loc="upper left", fontsize=8.5)
    path = out / "tokens.svg"
    fig.tight_layout()
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"), dpi=200)
    plt.close(fig)
    return path


def latex_table(summary: dict[str, Any], path: Path) -> Path:
    lines = [
        r"\begin{tabular}{llrrrrrr}",
        r"\toprule",
        r"Benchmark & CF share & $n$ & Convergence & Consensus & Accuracy & Ultra-Strong"
        r" & Tokens \\",
        r"\midrule",
    ]
    order = ["mscore", "kramabench", "medagentbench", "synthetic", "all"]
    for bench in order:
        for r in _rows(summary, bench):
            tok = "--" if r.get("tokens_mean") is None else f"{r['tokens_mean']:,.0f}"
            lo, hi = r["convergence_ci"]
            lines.append(
                f"{NAMES[bench]} & {round(100 * r['cf_fraction'])}\\% & {r['trials']} & "
                f"{r['convergence_success']:.2f} [{lo:.2f}, {hi:.2f}] & {r['consensus']:.2f} & "
                f"{r['accuracy']:.2f} & {r['ultra_strong']:.2f} & {tok} \\\\")
        if _rows(summary, bench):
            lines.append(r"\midrule" if bench != "all" else r"\bottomrule")
    lines.append(r"\end{tabular}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_figures(summary: dict[str, Any], run_dir: str | Path) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError('Plots need matplotlib: pip install -e ".[plots]"') from exc
    _style(plt)
    run = Path(run_dir)
    figures = run / "figures"
    tables = run / "tables"
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    made = [convergence(summary, figures, plt), intelligibility(summary, figures, plt),
            tokens(summary, figures, plt), latex_table(summary, tables / "groups.tex")]
    return [p for p in made if p is not None]
