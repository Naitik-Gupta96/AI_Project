import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Catalog, ProviderOption } from "../types";

/** Start a live session: task, provider, counterfactual-capable agents, pace. */
export function NewSession({ onStarted }: { onStarted: (id: string) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [providers, setProviders] = useState<ProviderOption[]>([{ spec: "mock", label: "Deterministic mock (rules, no model)" }]);
  const [benchmark, setBenchmark] = useState("synthetic");
  const [taskId, setTaskId] = useState("architecture");
  const [provider, setProvider] = useState("mock");
  const [cf, setCf] = useState<string[]>(["analyst"]);
  const [pace, setPace] = useState(0.7);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.catalog().then(setCatalog).catch((e) => setError(String(e)));
    api.providers().then(setProviders).catch(() => undefined);
  }, []);

  const bench = catalog?.benchmarks.find((b) => b.name === benchmark);
  const task = useMemo(() => bench?.tasks.find((t) => t.task_id === taskId) ?? bench?.tasks[0], [bench, taskId]);
  const roles = task?.roles ?? [];

  async function start() {
    if (!task) return;
    setBusy(true);
    setError(null);
    try {
      const s = await api.start({
        benchmark, task_id: task.task_id, provider, cf_agents: cf.filter((a) => roles.includes(a)),
        pace, start_paused: paused,
      });
      onStarted(s.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <header>
        <h2>New session</h2>
      </header>
      <div className="panel-body">
        <div className="form-row">
          <label className="field">
            Benchmark
            <select value={benchmark} onChange={(e) => { setBenchmark(e.target.value); setTaskId(""); }}>
              {catalog?.benchmarks.map((b) => (
                <option key={b.name} value={b.name} disabled={!b.available}>
                  {b.name}{b.available ? "" : " (data not fetched)"}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Task
            <select value={task?.task_id ?? ""} onChange={(e) => setTaskId(e.target.value)} style={{ maxWidth: 260 }}>
              {bench?.tasks.map((t) => (
                <option key={t.task_id} value={t.task_id}>{t.task_id}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Provider
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {providers.map((p) => (
                <option key={p.spec} value={p.spec}>{p.label}</option>
              ))}
            </select>
          </label>
          <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend style={{ padding: 0, marginBottom: 4 }}>Counterfactual-capable</legend>
            <div className="checks">
              {roles.map((r) => (
                <label key={r}>
                  <input type="checkbox" checked={cf.includes(r)}
                         onChange={(e) => setCf(e.target.checked ? [...cf, r] : cf.filter((x) => x !== r))} />
                  {r}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="field">
            Pace (s/round)
            <input type="number" min={0} max={5} step={0.1} value={pace} style={{ width: 80 }}
                   onChange={(e) => setPace(Number(e.target.value))} />
          </label>
          <div className="checks" style={{ paddingBottom: 6 }}>
            <label>
              <input type="checkbox" checked={paused} onChange={(e) => setPaused(e.target.checked)} />
              start paused
            </label>
          </div>
          <button className="btn primary" onClick={start} disabled={busy || !task}>Run session</button>
        </div>
        {task && <div className="question">{task.question}</div>}
        {error && <div className="alert" style={{ marginTop: 8 }}>{error}</div>}
      </div>
    </section>
  );
}
