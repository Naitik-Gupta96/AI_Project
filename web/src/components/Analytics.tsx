import { useEffect, useState } from "react";
import { api, type ExperimentSummary } from "../api";

/** Experiment results (ablation over the share of counterfactual-capable agents). */
export function Analytics() {
  const [list, setList] = useState<ExperimentSummary[] | null>(null);
  useEffect(() => {
    api.experiments().then(setList).catch(() => setList([]));
  }, []);
  return (
    <section className="panel">
      <header>
        <h2>Experiments</h2>
      </header>
      <div className="empty">
        {list === null ? "Loading…" : list.length ? `${list.length} experiment(s)` : "No experiment results yet. Run bb ablate."}
      </div>
    </section>
  );
}
