"""
Streamlit frontend.

    python -m streamlit run frontend/app.py

Tabs:
    Flash Talk   one end-to-end run: task -> agents -> deadlock -> counterfactual -> replay
    Run Explorer inspect any run (Flash Talk task or a recorded pilot trial) step by step
    Evaluation   pilot results and how they were produced

All data comes from ``ai_project.ui`` (real runs and results files). This file
only renders; it makes no scheduling, deadlock or counterfactual decisions.
"""

import html
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from ai_project.experiment import load_results, run_pilot, save_results
from ai_project.tasks import ROLES, flash_talk_task
from ai_project.ui import (
    FLASH_TALK_CF_AGENTS,
    MODE_PILOT,
    CounterfactualView,
    DemoView,
    RunEvent,
    RunView,
    experiment_view,
    find_results,
    flash_talk_demo,
    trial_demo_view,
)

RESULTS_DIR = Path(
    os.environ.get("AI_PROJECT_RESULTS_DIR")
    or Path(__file__).resolve().parents[1] / "experiments" / "results"
)

st.set_page_config(page_title="Blackboard + Counterfactual Agents", layout="wide")

st.markdown(
    """
<style>
:root { --ratify:#3d9a62; --revise:#4a7fc1; --refute:#d07a2a; --reject:#cc4646; --muted:#8a8f98; }
.block-container { max-width: 1180px; padding-top: 2.2rem; }
h1 { font-size: 1.55rem !important; font-weight: 650 !important; letter-spacing: -0.01em; }
h3 { font-size: 0.78rem !important; font-weight: 650 !important; letter-spacing: .09em;
     text-transform: uppercase; color: var(--muted); margin: 1.6rem 0 .4rem 0 !important; }
.lede { color: var(--muted); margin: -0.4rem 0 0.6rem 0; }
.mode { display:inline-block; font: 600 .7rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;
        letter-spacing:.06em; padding:.3rem .45rem; border:1px solid var(--muted);
        border-radius:3px; color:var(--muted); margin-right:.4rem; }
.task { font-size: 1.05rem; line-height: 1.5; padding: .2rem 0 .2rem .9rem;
        border-left: 3px solid var(--muted); }
.ev { display:grid; grid-template-columns: 2.2rem 6.5rem 4.6rem 1fr 3.4rem; gap:.6rem;
      align-items:baseline; padding:.45rem .2rem .45rem .6rem; border-left:3px solid transparent; }
.ev + .ev { border-top: 1px solid rgba(128,128,128,.18); }
.ev .n { font: .8rem ui-monospace,Menlo,monospace; color: var(--muted); }
.ev .who { font-weight: 600; }
.ev .tag { font: 700 .72rem ui-monospace,Menlo,monospace; letter-spacing:.04em; }
.ev .conf { font: .78rem ui-monospace,Menlo,monospace; color: var(--muted); text-align:right; }
.ev .why { grid-column: 2 / 6; color: var(--muted); font-size: .86rem; line-height:1.4; }
.ev .note { font: 600 .68rem ui-monospace,Menlo,monospace; letter-spacing:.05em;
            text-transform:uppercase; margin-left:.5rem; color: var(--muted); }
.RATIFY .tag{color:var(--ratify)} .REVISE .tag{color:var(--revise)}
.REFUTE .tag{color:var(--refute)} .REJECT .tag{color:var(--reject)}
.ev.inherited { opacity: .5; }
.ev.intervention { border-left-color: var(--revise); background: rgba(74,127,193,.08); }
.status { text-align:center; margin:.7rem 0; font: 700 .8rem ui-monospace,Menlo,monospace;
          letter-spacing:.12em; }
.status span { padding:.35rem .8rem; border:1.5px solid currentColor; border-radius:3px; }
.status.DEADLOCK { color: var(--refute); } .status.CONSENSUS { color: var(--ratify); }
.status.MAX_STEPS, .status.ERROR { color: var(--reject); }
.status-why { text-align:center; color:var(--muted); font-size:.85rem; margin-top:-.2rem; }
.diff { display:grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.diff > div { padding:.7rem .9rem; border:1px solid rgba(128,128,128,.3); border-radius:4px; }
.diff .lbl { font: 600 .7rem ui-monospace,Menlo,monospace; letter-spacing:.08em; color:var(--muted); }
.diff .after { border-color: var(--revise); }
.flow { font: .9rem ui-monospace,Menlo,monospace; line-height: 1.8; }
.flow .muted { display:inline-block; width: 9.5rem; font-size:.9rem; }
.muted { color: var(--muted); font-size: .88rem; }
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ rendering helpers

def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def event_html(e: RunEvent) -> str:
    if not e.is_message:
        return (f'<div class="status {esc(e.tag)}"><span>{esc(e.tag)}</span></div>'
                f'<div class="status-why">{esc(e.reason)}</div>')
    note = {"inherited": "inherited", "intervention": "counterfactual revision"}.get(e.kind, "")
    alt = f" &rarr; names {esc(e.alternative)}" if e.alternative else ""
    conf = f"{e.confidence:.2f}" if e.confidence is not None else "-"
    return (
        f'<div class="ev {esc(e.tag)} {esc(e.kind)}">'
        f'<span class="n">{e.step:02d}</span><span class="who">{esc(e.agent_id)}</span>'
        f'<span class="tag">{esc(e.tag)}</span>'
        f'<span>{esc(e.prediction)}{alt}'
        f'{f"<span class=note>{note}</span>" if note else ""}</span>'
        f'<span class="conf">{conf}</span>'
        f'<span class="why">{esc(e.explanation)}</span></div>'
    )


def timeline(events: list[RunEvent]) -> None:
    st.markdown("".join(event_html(e) for e in events), unsafe_allow_html=True)


def mode_badges(*labels: str) -> None:
    st.markdown("".join(f'<span class="mode">{esc(x)}</span>' for x in labels),
                unsafe_allow_html=True)


def evidence_table(demo: DemoView) -> None:
    rows = []
    for a in demo.agents:
        scores = ", ".join(f"{o} {s:.2f}" for o, s in a.evidence["scores"].items())
        objections = "; ".join(f"{o}: {r}" for o, r in a.evidence["objections"].items())
        rows.append({
            "agent": a.agent_id,
            "role": a.description,
            "benefit estimates": scores or "-",
            "rules out": objections or "-",
            "counterfactual-capable": "yes" if a.counterfactual_capable else "no",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def changed_event(cf: CounterfactualView) -> None:
    o, r = cf.original_event, cf.revised_event
    alt = f" (names {esc(r.alternative)})" if r.alternative else ""
    st.markdown(
        f'<div class="diff">'
        f'<div><div class="lbl">ORIGINAL &middot; STEP {o.step} &middot; {esc(o.agent_id)}</div>'
        f'<b>{esc(o.tag)} {esc(o.prediction)}</b><div class="muted">{esc(o.explanation)}</div></div>'
        f'<div class="after"><div class="lbl">REVISED IN HINDSIGHT &middot; STEP {r.step} &middot; '
        f'{esc(r.agent_id)}</div><b>{esc(r.tag)} {esc(r.prediction)}</b>{alt}'
        f'<div class="muted">{esc(r.explanation)}</div></div></div>',
        unsafe_allow_html=True,
    )


def outcome_line(run: RunView) -> str:
    o = run.outcome
    return f"{o.status} on {o.prediction or '-'} after {o.iterations} steps"


def raw_data(label: str, payload) -> None:
    with st.expander(f"Raw data: {label}"):
        st.code(json.dumps(payload, indent=2, default=str), language="json")


# ------------------------------------------------------------------ page

st.title("Intelligible Blackboard Architecture with Counterfactual Agents")
st.markdown(
    '<p class="lede">When agents sharing a Blackboard deadlock, can a counterfactual '
    "replay of their own history show which message, said differently, would have led "
    "to agreement?</p>",
    unsafe_allow_html=True,
)

tab_talk, tab_explore, tab_eval = st.tabs(["Flash Talk", "Run Explorer", "Evaluation"])

# ------------------------------------------------------------------ Flash Talk

with tab_talk:
    mode_badges("DETERMINISTIC MOCK AGENTS", "REAL BLACKBOARD · SCHEDULER · DEADLOCK · COUNTERFACTUAL")
    st.markdown(
        '<p class="muted">The agents follow explicit, documented rules (no language model). '
        "Every step below is produced by running the actual backend; nothing is scripted "
        "after the task is defined.</p>",
        unsafe_allow_html=True,
    )

    task = flash_talk_task()
    st.markdown("### 1 · Task")
    st.markdown(f'<div class="task">{esc(task.question)}</div>', unsafe_allow_html=True)

    cols = st.columns([3, 1])
    cf_agents = cols[0].multiselect(
        "Counterfactual-capable agents (may revise their own past messages after a deadlock)",
        options=list(ROLES), default=list(FLASH_TALK_CF_AGENTS), key="talk_cf",
    )
    cols[1].markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
    # Runs once on first load so the tab is never empty; Run re-executes with the selection
    if cols[1].button("Run", key="talk_run", type="primary", width="stretch") or (
        "talk_demo" not in st.session_state
    ):
        st.session_state["talk_demo"] = flash_talk_demo(cf_agents)

    demo: DemoView = st.session_state["talk_demo"]
    st.caption("Showing the run with counterfactual-capable agents: "
               f"{', '.join(demo.cf_agents) or 'none'}")
    with st.expander("What each agent privately knows", expanded=False):
        evidence_table(demo)

    st.markdown("### 2 · Agent interaction (original run)")
    timeline(demo.original.events)

    if not demo.deadlocked:
        st.success(f"No deadlock: {outcome_line(demo.original)}.")
    else:
        st.markdown("### 3 · Counterfactual reflection")
        if not demo.cf_agents:
            st.warning("No agent is counterfactual-capable, so the deadlock stands. "
                       "Select at least one agent and run again.")
        for r in demo.reflections:
            verdict = (f"would have sent **{r.revised}** instead"
                       if r.revised else "would not change it")
            result = f" → replayed: **{r.outcome}**" if r.replayed else ""
            st.markdown(f"- `{r.agent_id}` reflects on step {r.step} "
                        f"(`{r.original}`): {verdict}{result}")

        cf = demo.shown_branch
        if cf is not None:
            st.markdown("### 4 · Intervention")
            changed_event(cf)

            st.markdown("### 5 · Replay")
            st.markdown(
                f'<p class="muted">Steps before {cf.branch_point} are inherited unchanged; '
                f"step {cf.branch_point} is replaced; everything after is produced again by "
                "the same agents, policy and configuration.</p>",
                unsafe_allow_html=True,
            )
            timeline(cf.branch.events)

        st.markdown("### 6 · Outcome")
        rows = [("original", outcome_line(demo.original))]
        if cf is not None:
            rows.append(("counterfactual", outcome_line(cf.branch)))
            rows.append(("diverged at", f"step {cf.divergence_step} "
                                        f"(shared prefix: {cf.shared_prefix} event)"))
        rows.append(("original board", "unchanged by branching" if demo.original_preserved
                     else "CHANGED (bug)"))
        st.markdown(
            '<div class="flow">' + "".join(
                f"<div><span class='muted'>{esc(k)}</span>{esc(v)}</div>" for k, v in rows
            ) + "</div>",
            unsafe_allow_html=True,
        )

    raw_data("this run", demo.to_dict())

# ------------------------------------------------------------------ Run Explorer

with tab_explore:
    source = st.radio("Run source", ["Flash Talk task", "Recorded pilot trial"],
                      horizontal=True, key="explore_source")
    explored: DemoView | None = None
    if source == "Flash Talk task":
        cf = st.multiselect("Counterfactual-capable agents", list(ROLES),
                            default=list(FLASH_TALK_CF_AGENTS), key="explore_cf")
        explored = flash_talk_demo(cf)
    else:
        files = find_results(RESULTS_DIR)
        if not files:
            st.info("No pilot results yet. Run `python experiments/run_experiment.py` "
                    "or use the Evaluation tab.")
        else:
            path = st.selectbox("Results file", files, format_func=lambda p: p.name,
                                key="explore_file")
            doc = load_results(path)
            outcome_filter = st.radio(
                "Show trials", ["all", "deadlocked", "recovered", "not recovered"],
                horizontal=True, key="explore_filter")
            keep = {
                "all": lambda m: True,
                "deadlocked": lambda m: m["original_deadlock"],
                "recovered": lambda m: m["recovered"] is True,
                "not recovered": lambda m: m["recovered"] is False,
            }[outcome_filter]
            trials = [t for t in doc["trials"] if keep(t["metrics"])]
            if trials:
                trial = st.selectbox("Trial", trials, format_func=lambda t: t["trial_id"],
                                     key="explore_trial")
                explored, reproduced = trial_demo_view(doc, trial)
                if reproduced:
                    st.caption("Re-executed live from the recorded task and condition; "
                               "matches the recorded trace and outcome.")
                else:
                    st.error("Re-execution does NOT match the recorded trial.")
            else:
                st.info("No trials match this filter.")

    if explored is not None:
        runs = {"Original run": explored.original}
        for b in explored.branches:
            mark = "recovered" if b.recovered else b.branch.outcome.status.lower()
            runs[f"Branch at step {b.branch_point} ({b.agent_id}, {mark})"] = b.branch
        run_name = st.radio("Run", list(runs), horizontal=True, key="explore_run")
        run = runs[run_name]

        left, center, right = st.columns([1.1, 1.6, 1.3], gap="large")
        with left:
            st.markdown("### Run")
            st.markdown(f'<div class="task">{esc(run.task)}</div>', unsafe_allow_html=True)
            mode_badges(run.mode)
            st.markdown(
                f"**Outcome:** {outcome_line(run)}  \n"
                f"<span class='muted'>{esc(run.outcome.reason)}</span>  \n"
                f"**Provider:** `{run.provider.get('name')}`  \n"
                f"**Policy:** `{run.policy.get('name')}`  \n"
                f"**Counterfactual-capable:** {', '.join(explored.cf_agents) or 'none'}",
                unsafe_allow_html=True,
            )
            with st.expander("Agents and private evidence"):
                evidence_table(explored)
            with st.expander("Scheduler configuration"):
                st.json(run.config)

        with center:
            st.markdown("### Timeline")
            labels = [
                (f"{e.step:02d}  {e.agent_id:<10} {e.tag:<6} {e.prediction}"
                 + {"inherited": "  · inherited", "intervention": "  · revised"}.get(e.kind, ""))
                if e.is_message else f"--  {e.tag}"
                for e in run.events
            ]
            idx = st.radio("Event", range(len(labels)), format_func=lambda i: labels[i],
                           label_visibility="collapsed", key=f"explore_ev_{run_name}")

        with right:
            st.markdown("### Selected event")
            e = run.events[idx]
            if e.is_message:
                st.markdown(f"> {e.explanation}")
                st.markdown(
                    f"| | |\n|---|---|\n"
                    f"| agent | `{e.agent_id}` ({e.role or '-'}) |\n"
                    f"| PXP tag | `{e.tag}` |\n"
                    f"| prediction | {e.prediction} |\n"
                    f"| alternative named | {e.alternative or '-'} |\n"
                    f"| confidence | {e.confidence if e.confidence is not None else '-'} |\n"
                    f"| iteration | {e.step} |\n"
                    f"| decision rule | `{e.rule or '-'}` |\n"
                    f"| why selected | {e.reason or '-'} |\n"
                    f"| board status after | `{e.status_after}` |\n"
                    f"| timestamp | `{e.timestamp or '-'}` |\n"
                    f"| kind | {e.kind} |"
                )
            else:
                st.markdown(event_html(e), unsafe_allow_html=True)
                st.markdown(f"Board status set to `{e.tag}` at iteration {e.step}.")

        raw_data("selected run", run.to_dict())

# ------------------------------------------------------------------ Evaluation


@st.cache_data(show_spinner=False)
def cached_experiment(path: str, mtime: float):
    return experiment_view(path)


with tab_eval:
    files = find_results(RESULTS_DIR)
    top = st.columns([3, 1])
    if top[1].button("Run pilot now (~3 s)", key="eval_run", width="stretch"):
        with st.spinner("Running 800 end-to-end trials..."):
            out = RESULTS_DIR / "pilot_mock_seed42_n100.json"
            save_results(run_pilot(n_tasks=100, seed=42), out)
        files = find_results(RESULTS_DIR)

    if not files:
        top[0].info("No pilot results yet. Press **Run pilot now** or run "
                    "`python experiments/run_experiment.py`.")
    else:
        path = top[0].selectbox("Results file", files, format_func=lambda p: p.name,
                                key="eval_file")
        ev = cached_experiment(str(path), path.stat().st_mtime)
        p = ev.parameters

        st.markdown("### Methodology")
        mode_badges(MODE_PILOT, "DETERMINISTIC" if ev.provider.get("deterministic")
                    else "NON-DETERMINISTIC MODEL", "SYNTHETIC TASKS")
        st.markdown(
            f"**{ev.mode}.** {ev.n_trials} trials = {p['n_tasks']} generated tasks "
            f"(seed {p['seed']}, {p['n_options']} options each) × {len(p['conditions'])} "
            f"conditions. Each trial runs the full system: Blackboard, the three role agents, "
            f"Scheduler (`{p['policy']}`), deadlock detection and, after a deadlock, "
            f"counterfactual reflection and replay.  \n"
            f"Provider `{ev.provider.get('name')}` · commit `{ev.git_commit}` · "
            f"generated {ev.generated_at}"
        )
        st.warning(
            "These are descriptive results of a deterministic pilot. The agents follow fixed "
            "rules over procedurally generated tasks, so the numbers characterise the "
            "implemented mechanism, not LLM agents or real-world tasks. They are not a "
            "validated research finding."
        )
        with st.expander("Definitions"):
            for k, v in ev.definitions.items():
                st.markdown(f"- **{k}**: {v}")

        st.markdown("### By counterfactual fraction")
        frac = pd.DataFrame(ev.by_fraction)
        shown = frac[["cf_fraction", "trials", "deadlock_rate", "deadlocked",
                      "deadlocked_feasible", "recovery_rate", "recovery_rate_feasible",
                      "final_consensus_rate", "best_decision_rate", "mean_iterations"]]
        st.dataframe(shown.style.format(precision=2, na_rep="-"), hide_index=True,
                     width="stretch")
        st.caption(
            "Pooled over every subset of agents of that size (so 1/3 and 2/3 contain 3 "
            "subsets × tasks). The original run does not depend on the condition, which is "
            "why the deadlock rate is constant; only recovery changes. Deadlocks on tasks "
            "with no option acceptable to all roles cannot be recovered and are the correct "
            "outcome; 'feasible' rates exclude them."
        )
        chart = frac.assign(
            fraction=frac["cf_fraction"].map(lambda f: f"{round(f * 3)}/3")
        ).set_index("fraction")[["recovery_rate_feasible"]]
        st.bar_chart(chart, y_label="recovered / feasible deadlocks", height=240)

        st.markdown("### By condition")
        cond = pd.DataFrame(ev.by_condition)
        cond["95% CI (Wilson)"] = cond["recovery_rate_feasible_ci95"].map(
            lambda ci: "-" if ci is None else f"[{ci[0]:.2f}, {ci[1]:.2f}]")
        st.dataframe(
            cond[["cf_agents", "trials", "deadlocked_feasible", "recovered",
                  "recovery_rate_feasible", "95% CI (Wilson)", "mean_branches_replayed"]]
            .style.format(precision=2, na_rep="-"),
            hide_index=True, width="stretch",
        )
        st.caption(
            "One trial per task per condition, so the interval describes uncertainty over "
            "the task generator's distribution only."
        )

        st.markdown("### Not measured")
        st.markdown(
            "- **Token cost**: the deterministic mock reports no token usage; it is recorded "
            "only when a model provider reports it (e.g. `--provider ollama`).\n"
            "- **Intelligibility to humans**: not measured; would need a user study.\n"
            "- **Benchmarks** (KramaBench, MSCoRe, MedAgentBench): not integrated."
        )
