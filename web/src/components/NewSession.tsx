import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Catalog, Evidence, ProviderOption } from "../types";
import { TagLabel } from "./Badges";

const TAG_GUIDE: [string, string][] = [
  ["INIT", "the opening message: a prediction and its explanation"],
  ["RATIFY", "agrees with the prediction and the explanation it answers"],
  ["REVISE", "agrees with one of them and changes its own position"],
  ["REFUTE", "agrees with one of them but keeps its position"],
  ["REJECT", "agrees with neither (from message 4 on); the board deadlocks"],
];

/** Start a live session: the task, what each agent privately knows, and who can reflect. */
export function NewSession({ onStarted }: { onStarted: (id: string) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [providers, setProviders] = useState<ProviderOption[]>([{ spec: "mock", label: "Deterministic mock (rules, no model)" }]);
  const [benchmark, setBenchmark] = useState("synthetic");
  const [taskId, setTaskId] = useState("architecture");
  const [provider, setProvider] = useState("mock");
  const [cf, setCf] = useState<string[]>(["analyst"]);
  const [pace, setPace] = useState(1.2);
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
  const toggle = (r: string) => setCf((c) => (c.includes(r) ? c.filter((x) => x !== r) : [...c, r]));

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
    <>
      <div className="intro">
        <h2>Run a session</h2>
        <p>
          Three agents work on one task through a shared blackboard, and every message they post is a
          prediction, an explanation and a PXP tag. If they deadlock, counterfactual-capable agents replay
          their own past messages in a sandbox and apply the alternative that would have led to consensus.
        </p>
      </div>

      <section className="panel">
        <div className="panel-body" style={{ display: "grid", gap: 18, paddingTop: 16 }}>
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
              <select value={task?.task_id ?? ""} onChange={(e) => setTaskId(e.target.value)} style={{ maxWidth: 280 }}>
                {bench?.tasks.map((t) => (
                  <option key={t.task_id} value={t.task_id}>{t.task_id}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Model
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                {providers.map((p) => (
                  <option key={p.spec} value={p.spec}>{p.label}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Seconds per round
              <input type="number" min={0} max={5} step={0.1} value={pace} style={{ width: 90 }}
                     onChange={(e) => setPace(Number(e.target.value))} />
            </label>
            <div className="checks" style={{ paddingBottom: 7 }}>
              <label>
                <input type="checkbox" checked={paused} onChange={(e) => setPaused(e.target.checked)} />
                start paused
              </label>
            </div>
            <span className="spacer" />
            <button className="btn primary" onClick={start} disabled={busy || !task}>Run session</button>
          </div>

          {task && (
            <div className="task-card">
              <div className="q">{task.question}</div>
              {task.options.length > 0 && (
                <div className="options">{task.options.map((o) => <span key={o} className="option">{o}</span>)}</div>
              )}
            </div>
          )}

          {roles.length > 0 && (
            <div style={{ display: "grid", gap: 8 }}>
              <h3>The team <span className="muted" style={{ fontWeight: 400 }}>· click an agent to make it counterfactual-capable</span></h3>
              <div className="roles">
                {roles.map((r) => (
                  <label key={r} className={`role${cf.includes(r) ? " on" : ""}`}>
                    <div className="head">
                      <input type="checkbox" checked={cf.includes(r)} onChange={() => toggle(r)} />
                      <strong>{r}</strong>
                      {cf.includes(r) && <span className="cf-badge">CF</span>}
                    </div>
                    <Knows evidence={task?.evidence?.[r]} />
                  </label>
                ))}
              </div>
            </div>
          )}
          {error && <div className="alert">{error}</div>}
        </div>
      </section>

      <section className="panel">
        <header><h2>Reading the board</h2><span className="hint">what each PXP tag means</span></header>
        <div className="panel-body tag-guide">
          {TAG_GUIDE.map(([tag, text]) => (
            <div key={tag}><TagLabel tag={tag} /><span>{text}</span></div>
          ))}
        </div>
      </section>
    </>
  );
}

function Knows({ evidence }: { evidence?: Evidence }) {
  const scores = Object.entries(evidence?.scores ?? {});
  const objections = Object.entries(evidence?.objections ?? {});
  if (!scores.length && !objections.length) {
    return <div className="knows"><span className="k">Works from the task and the board.</span></div>;
  }
  return (
    <div className="knows">
      <span className="k">Privately knows</span>
      {scores.length > 0 && (
        <span>Rates {scores.map(([o, s]) => `${o} ${s.toFixed(2)}`).join(" · ")}</span>
      )}
      {objections.map(([o, why]) => (
        <span key={o}>Rules out <strong>{o}</strong>: {why}</span>
      ))}
    </div>
  );
}
