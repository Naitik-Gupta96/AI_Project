import * as d3 from "d3";
import { useEffect, useMemo, useState } from "react";
import { api, type ExperimentDetail, type ExperimentSummary, type GroupRow } from "../api";

const SERIES: Record<string, string> = {
  mscore: "var(--tag-revise)",
  kramabench: "var(--tag-objection)",
  medagentbench: "var(--tag-ratify)",
  synthetic: "var(--ink-2)",
  all: "var(--ink)",
};
const NAMES: Record<string, string> = {
  mscore: "MSCoRe",
  kramabench: "KramaBench",
  medagentbench: "MedAgentBench",
  synthetic: "Synthetic",
  all: "All benchmarks",
};
const LEVELS = [
  { key: "ultra_strong", name: "Ultra-Strong", color: "#0d366b" },
  { key: "strong", name: "Strong", color: "#2a78d6" },
  { key: "one_way", name: "One-Way", color: "#86b6ef" },
  { key: "none", name: "None", color: "#cde2fb" },
] as const;
const pct = (v: number) => `${Math.round(v * 100)}%`;
const share = (r: GroupRow) => `${Math.round(r.cf_fraction * 100)}%`;

/** Ablation results: convergence, intelligibility depth and token cost by share of CF agents. */
export function Analytics() {
  const [list, setList] = useState<ExperimentSummary[] | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExperimentDetail | null>(null);
  const [bench, setBench] = useState("all");

  useEffect(() => {
    api.experiments().then((l) => {
      setList(l);
      if (l.length) setName(l[0].name);
    }).catch(() => setList([]));
  }, []);
  useEffect(() => {
    if (name) api.experiment(name).then(setDetail).catch(() => setDetail(null));
  }, [name]);

  const benchmarks = useMemo(
    () => [...new Set(detail?.groups.map((g) => g.benchmark) ?? [])].sort((a, b) =>
      a === "all" ? -1 : b === "all" ? 1 : a.localeCompare(b)),
    [detail],
  );
  const selected = benchmarks.includes(bench) ? bench : benchmarks[0];
  const rows = (b: string) =>
    (detail?.groups ?? []).filter((g) => g.benchmark === b).sort((x, y) => x.cf_fraction - y.cf_fraction);

  if (list === null) return <section className="panel"><div className="empty">Loading…</div></section>;
  if (!list.length) {
    return (
      <section className="panel">
        <header><h2>Experiments</h2></header>
        <div className="empty">
          No experiment results yet. Run <code>bb ablate experiments/configs/ablation.toml</code> (or the
          mock config for a quick check); results appear here.
        </div>
      </section>
    );
  }

  const current = rows(selected);
  const meta = detail?.meta ?? {};
  return (
    <>
      <section className="panel">
        <div className="panel-body" style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "end" }}>
          <label className="field">
            Experiment
            <select value={name ?? ""} onChange={(e) => setName(e.target.value)}>
              {list.map((e) => <option key={e.name} value={e.name}>{e.name}</option>)}
            </select>
          </label>
          <div className="tabs" role="tablist" aria-label="Benchmark">
            {benchmarks.map((b) => (
              <button key={b} className="tab" role="tab" aria-selected={b === selected} onClick={() => setBench(b)}>
                {NAMES[b] ?? b}
              </button>
            ))}
          </div>
          <span className="spacer" />
          <span style={{ color: "var(--ink-2)", fontSize: 13 }}>
            {meta.provider?.model ?? meta.config?.provider ?? ""} · {current[0]?.trials ?? 0} trials per group
            {meta.git_commit ? ` · commit ${String(meta.git_commit).slice(0, 7)}` : ""}
          </span>
        </div>
      </section>

      <div className="session-grid" style={{ gridTemplateAreas: '"graph side" "stream side" "cf cf"' }}>
        <section className="panel area-graph">
          <header>
            <h2>Convergence success</h2>
            <span className="hint">consensus within the budget on an accurate answer · 95% Wilson interval</span>
          </header>
          <ConvergenceChart series={selected === "all" ? benchmarks : [selected]} rows={rows} />
        </section>
        <div className="area-side">
          <section className="panel">
            <header>
              <h2>Intelligibility depth</h2>
              <span className="hint">whole session, Mestha et al. Def. 2</span>
            </header>
            <IntelligibilityBars rows={current} />
          </section>
          <section className="panel">
            <header>
              <h2>Token cost per instance</h2>
              <span className="hint">mean · live board + sandbox</span>
            </header>
            <TokenBars rows={current} />
          </section>
        </div>
        <section className="panel area-cf">
          <header><h2>Table</h2><span className="hint">{NAMES[selected] ?? selected}</span></header>
          <div className="panel-body" style={{ overflowX: "auto" }}>
            <GroupTable rows={current} />
            <h3 style={{ fontSize: 13, margin: "14px 0 6px" }}>Paired tests against the control group (exact McNemar)</h3>
            <table className="data">
              <thead>
                <tr><th>Comparison</th><th className="num">Pairs</th><th className="num">Control only</th>
                  <th className="num">Group only</th><th className="num">p</th></tr>
              </thead>
              <tbody>
                {(detail?.tests ?? []).filter((t) => t.benchmark === selected).map((t) => (
                  <tr key={t.comparison}>
                    <td>{t.comparison}</td><td className="num">{t.pairs}</td>
                    <td className="num">{t.b}</td><td className="num">{t.c}</td>
                    <td className="num">{t.p_value < 0.001 ? t.p_value.toExponential(1) : t.p_value.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </>
  );
}

function ConvergenceChart({ series, rows }: { series: string[]; rows: (b: string) => GroupRow[] }) {
  const [hover, setHover] = useState<{ b: string; r: GroupRow; x: number; y: number } | null>(null);
  const W = 640, H = 340, M = { top: 16, right: 130, bottom: 44, left: 52 };
  const x = d3.scaleLinear([0, 1], [M.left, W - M.right]);
  const y = d3.scaleLinear([0, 1], [H - M.bottom, M.top]);
  const ends = series.map((b) => ({ b, y: rows(b).at(-1)?.convergence_success ?? 0 })).sort((a, c) => a.y - c.y);
  for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 0.055);
  return (
    <div className="panel-body" style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Convergence success by share of counterfactual-capable agents">
        {y.ticks(5).map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={M.left - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--muted)">{pct(t)}</text>
          </g>
        ))}
        {[0, 1 / 3, 2 / 3, 1].map((t) => (
          <text key={t} x={x(t)} y={H - M.bottom + 18} textAnchor="middle" fontSize={11} fill="var(--muted)">{pct(t)}</text>
        ))}
        <text x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle" fontSize={12} fill="var(--ink-2)">
          Counterfactual-capable agents
        </text>
        {series.map((b) => {
          const rs = rows(b);
          const line = d3.line<GroupRow>().x((r) => x(r.cf_fraction)).y((r) => y(r.convergence_success))(rs) ?? "";
          return (
            <g key={b}>
              {rs.map((r) => (
                <line key={`ci${r.group}`} x1={x(r.cf_fraction)} x2={x(r.cf_fraction)} y1={y(r.convergence_ci[0])}
                      y2={y(r.convergence_ci[1])} stroke={SERIES[b]} strokeWidth={1} opacity={0.7} />
              ))}
              <path d={line} fill="none" stroke={SERIES[b]} strokeWidth={b === "all" ? 2.5 : 2} />
              {rs.map((r) => (
                <circle key={r.group} cx={x(r.cf_fraction)} cy={y(r.convergence_success)} r={4.5} fill={SERIES[b]}
                        stroke="var(--surface)" strokeWidth={2}
                        onMouseEnter={(e) => setHover({ b, r, x: e.clientX, y: e.clientY })}
                        onMouseLeave={() => setHover(null)} />
              ))}
            </g>
          );
        })}
        {ends.map((e) => (
          <text key={e.b} x={x(1) + 12} y={y(e.y) + 4} fontSize={12} fill="var(--ink-2)">{NAMES[e.b] ?? e.b}</text>
        ))}
      </svg>
      {hover && (
        <div className="tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>
          <strong>{NAMES[hover.b]}</strong> · {share(hover.r)} counterfactual-capable<br />
          Convergence {pct(hover.r.convergence_success)} [{pct(hover.r.convergence_ci[0])}, {pct(hover.r.convergence_ci[1])}]<br />
          Consensus {pct(hover.r.consensus)} · accuracy {pct(hover.r.accuracy)} · {hover.r.trials} trials
        </div>
      )}
    </div>
  );
}

function IntelligibilityBars({ rows }: { rows: GroupRow[] }) {
  const W = 420, row = 30, M = { left: 44, right: 8, top: 6 };
  const H = M.top + rows.length * row + 30;
  const x = d3.scaleLinear([0, 1], [M.left, W - M.right]);
  return (
    <div className="panel-body">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Share of sessions per intelligibility level">
        {rows.map((r, i) => {
          let left = 0;
          return (
            <g key={r.group} transform={`translate(0,${M.top + i * row})`}>
              <text x={M.left - 6} y={row / 2} textAnchor="end" fontSize={11} fill="var(--muted)">{share(r)}</text>
              {LEVELS.map((l) => {
                const v = (r as any)[l.key] as number;
                const start = left;
                left += v;
                return v > 0 ? (
                  <g key={l.key}>
                    <rect x={x(start)} y={4} width={Math.max(0, x(start + v) - x(start) - 2)} height={row - 10}
                          fill={l.color} rx={2}>
                      <title>{`${l.name}: ${pct(v)}`}</title>
                    </rect>
                    {v >= 0.1 && (
                      <text x={x(start + v / 2)} y={row / 2 + 4} textAnchor="middle" fontSize={10.5}
                            fill={l.key === "strong" || l.key === "ultra_strong" ? "#fff" : "#0b0b0b"}>{pct(v)}</text>
                    )}
                  </g>
                ) : null;
              })}
            </g>
          );
        })}
      </svg>
      <div className="legend" style={{ padding: 0 }}>
        {LEVELS.map((l) => (
          <span key={l.key} style={{ display: "inline-flex", gap: 5, alignItems: "center", fontSize: 12.5 }}>
            <span style={{ width: 10, height: 10, background: l.color, borderRadius: 2 }} />{l.name}
          </span>
        ))}
      </div>
    </div>
  );
}

function TokenBars({ rows }: { rows: GroupRow[] }) {
  if (!rows.length || rows[0].tokens_mean == null) {
    return <div className="empty">No token counts (the deterministic mock reports none).</div>;
  }
  const W = 420, H = 200, M = { top: 22, bottom: 24, left: 44, right: 8 };
  const max = d3.max(rows, (r) => (r.tokens_ci?.[1] ?? r.tokens_mean ?? 0)) ?? 1;
  const y = d3.scaleLinear([0, max * 1.1], [H - M.bottom, M.top]).nice();
  const x = d3.scaleBand(rows.map(share), [M.left, W - M.right]).padding(0.35);
  return (
    <div className="panel-body">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Mean tokens per instance by group">
        {y.ticks(4).map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={M.left - 6} y={y(t) + 4} textAnchor="end" fontSize={10.5} fill="var(--muted)">{d3.format("~s")(t)}</text>
          </g>
        ))}
        {rows.map((r) => {
          const live = r.live_tokens_mean ?? 0;
          const sb = r.sandbox_tokens_mean ?? 0;
          const bx = x(share(r))!;
          return (
            <g key={r.group}>
              <rect x={bx} y={y(live)} width={x.bandwidth()} height={y(0) - y(live)} fill="var(--tag-revise)" rx={2}>
                <title>{`Live board: ${Math.round(live).toLocaleString()} tokens`}</title>
              </rect>
              {sb > 0 && (
                <rect x={bx} y={y(live + sb)} width={x.bandwidth()} height={Math.max(0, y(live) - y(live + sb) - 2)}
                      fill="var(--tag-objection)" rx={2}>
                  <title>{`Sandbox: ${Math.round(sb).toLocaleString()} tokens`}</title>
                </rect>
              )}
              <text x={bx + x.bandwidth() / 2} y={y(live + sb) - 6} textAnchor="middle" fontSize={10.5} fill="var(--ink-2)">
                {Math.round(r.tokens_mean ?? 0).toLocaleString()}
              </text>
              <text x={bx + x.bandwidth() / 2} y={H - 6} textAnchor="middle" fontSize={11} fill="var(--muted)">{share(r)}</text>
            </g>
          );
        })}
      </svg>
      <div className="legend" style={{ padding: 0 }}>
        <span style={{ display: "inline-flex", gap: 5, alignItems: "center", fontSize: 12.5 }}>
          <span style={{ width: 10, height: 10, background: "var(--tag-revise)", borderRadius: 2 }} />Live board
        </span>
        <span style={{ display: "inline-flex", gap: 5, alignItems: "center", fontSize: 12.5 }}>
          <span style={{ width: 10, height: 10, background: "var(--tag-objection)", borderRadius: 2 }} />Counterfactual sandbox
        </span>
      </div>
    </div>
  );
}

function GroupTable({ rows }: { rows: GroupRow[] }) {
  return (
    <table className="data">
      <thead>
        <tr>
          <th>CF share</th><th className="num">Trials</th><th className="num">Convergence</th>
          <th className="num">Consensus</th><th className="num">Accuracy</th><th className="num">Deadlocked</th>
          <th className="num">Recovered</th><th className="num">Ultra-Strong</th><th className="num">Strong</th>
          <th className="num">Messages</th><th className="num">Tokens</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.group}>
            <td>{share(r)}</td><td className="num">{r.trials}</td>
            <td className="num">{pct(r.convergence_success)} [{pct(r.convergence_ci[0])}–{pct(r.convergence_ci[1])}]</td>
            <td className="num">{pct(r.consensus)}</td><td className="num">{pct(r.accuracy)}</td>
            <td className="num">{pct(r.deadlock)}</td><td className="num">{pct(r.recovered)}</td>
            <td className="num">{pct(r.ultra_strong)}</td><td className="num">{pct(r.strong)}</td>
            <td className="num">{r.messages_mean.toFixed(1)}</td>
            <td className="num">{r.tokens_mean == null ? "—" : Math.round(r.tokens_mean).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
