import streamlit as st
import json
import glob
import os
import pandas as pd
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

st.set_page_config(page_title="Multi-Agent Blackboard", layout="wide")

st.title("Intelligible Blackboard Architecture")
st.subheader("Counterfactual Agents & PXP Board Visualization")

tabs = st.tabs(["Flash Talk Demo", "Run Viewer", "Experiment Analytics"])

with tabs[0]:
    st.header("Single Run Demo")
    if st.button("Run Mock Single Demo", key="demo"):
        from experiments.run_experiment import run_mock_simulation
        res = run_mock_simulation(0, 1.0) # Always force high probability of CF
        
        st.write("### Task: Choose best option")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Original Path")
            st.write(f"Status: **{res.original_summary.status}**")
            st.write(f"Prediction: {res.original_summary.prediction}")
            st.write(f"Iterations: {res.original_summary.iterations}")
            
            for ev in res.original_events:
                with st.expander(f"Step {ev.step}: {ev.agent_id} - {ev.tag}"):
                    st.write(f"**Prediction:** {ev.prediction}")
                    st.write(f"**Confidence:** {ev.confidence}")
                    st.write(f"**Explanation:** {ev.explanation}")
                    
        with col2:
            st.write("#### Counterfactual Path")
            if res.counterfactual_summary:
                st.write(f"Status: **{res.counterfactual_summary.status}**")
                st.write(f"Prediction: {res.counterfactual_summary.prediction}")
                st.write(f"Iterations: {res.counterfactual_summary.iterations}")
                st.info(f"Diverged at Step {res.divergence_step}")
                
                for ev in res.counterfactual_events:
                    with st.expander(f"Step {ev.step}: {ev.agent_id} - {ev.tag} { '(Branch)' if ev.step >= res.divergence_step else '' }"):
                        st.write(f"**Prediction:** {ev.prediction}")
                        st.write(f"**Confidence:** {ev.confidence}")
                        st.write(f"**Explanation:** {ev.explanation}")
            else:
                st.write("No counterfactual branch generated (Consensus reached initially or not available).")


with tabs[1]:
    st.header("Run Viewer")
    results_files = glob.glob("experiments/results/results_*.json")
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
    csv_files = glob.glob("experiments/results/*_summary.csv")
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
