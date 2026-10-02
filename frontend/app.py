import streamlit as st
import json
import glob
import os
import pandas as pd
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))

from ai_project.ui import DEMO_RUNS

st.set_page_config(page_title="Multi-Agent Blackboard", layout="wide")

st.title("Intelligible Blackboard Architecture")
st.subheader("Counterfactual Agents & PXP Board Visualization")

tabs = st.tabs(["Flash Talk Demo", "Run Viewer", "Experiment Analytics"])


def show_events(events, divergence_step=None):
    for ev in events:
        branch = divergence_step is not None and ev.step >= divergence_step
        with st.expander(f"Step {ev.step}: {ev.agent_id} - {ev.tag} {'(Branch)' if branch else ''}"):
            st.write(f"**Prediction:** {ev.prediction}")
            st.write(f"**Confidence:** {ev.confidence if ev.confidence is not None else '-'}")
            st.write(f"**Explanation:** {ev.explanation}")


with tabs[0]:
    st.header("Single Run Demo")
    run_name = st.selectbox("Scenario", list(DEMO_RUNS), key="scenario")
    if st.button("Run Demo", key="demo"):
        res = DEMO_RUNS[run_name]()
        
        st.write("### Task: Choose best option")
        if res.summary:
            st.write(res.summary)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Original Path")
            st.write(f"Status: **{res.original_summary.status}**")
            st.write(f"Prediction: {res.original_summary.prediction}")
            st.write(f"Iterations: {res.original_summary.iterations}")
            show_events(res.original_events)
                    
        with col2:
            st.write("#### Counterfactual Path")
            if res.counterfactual_summary:
                st.write(f"Status: **{res.counterfactual_summary.status}**")
                st.write(f"Prediction: {res.counterfactual_summary.prediction}")
                st.write(f"Iterations: {res.counterfactual_summary.iterations}")
                if res.divergence_step is not None:
                    st.info(f"Diverged at Step {res.divergence_step}")
                show_events(res.counterfactual_events, res.divergence_step)
            else:
                st.write("No counterfactual branch for this scenario.")


with tabs[1]:
    st.header("Run Viewer")
    st.caption("Results files come from the mock simulator in experiments/run_experiment.py.")
    results_files = glob.glob(os.path.join(ROOT, "experiments/results/results_*.json"))
    if results_files:
        selected_file = st.selectbox("Select Results File", results_files)
        with open(selected_file, "r") as f:
            data = json.load(f)
            
        st.write(f"Loaded {len(data)} trials.")
        
        trial_idx = st.number_input("Select Trial Index", min_value=0, max_value=len(data)-1, value=0)
        
        run_data = data[trial_idx]
        st.json(run_data)
    else:
        st.write("No results files found. Run the experiment first.")

with tabs[2]:
    st.header("Analytics")
    st.caption("Results files come from the mock simulator in experiments/run_experiment.py.")
    csv_files = glob.glob(os.path.join(ROOT, "experiments/results/*_summary.csv"))
    if csv_files:
        selected_csv = st.selectbox("Select CSV File", csv_files)
        df = pd.read_csv(selected_csv)
        
        st.dataframe(df)
        
        st.write("### Consensus Rate vs CF Fraction")
        st.line_chart(df.set_index("cf_fraction")["consensus_rate"])
        
        st.write("### Deadlock Rate vs CF Fraction")
        st.line_chart(df.set_index("cf_fraction")["deadlock_rate"])
        
        st.write("### Mean Iterations vs CF Fraction")
        st.bar_chart(df.set_index("cf_fraction")["mean_iterations"])
    else:
        st.write("No summary CSV files found. Run analyze_results.py first.")
