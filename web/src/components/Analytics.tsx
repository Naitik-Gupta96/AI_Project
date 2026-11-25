import * as d3 from "d3";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { api, type ExperimentDetail, type ExperimentSummary, type GroupRow } from "../api";
import { useWidth } from "../useWidth";

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
const compact = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(1));

/** What a run is, in words, from its meta.json. */
function describe(meta: Record<string, any>, perGroup: number) {
  const provider = String(meta.config?.provider ?? "");
  if (provider === "mock") {
    return {
      title: "Pipeline check with scripted agents",
      text: `Deterministic rule-based agents on synthetic tasks built to deadlock; no language model. ${perGroup} tasks per group.`,
    };
  }
  const model = meta.provider?.model ?? provider;
  const via = meta.provider?.name === "ollama" ? "Ollama, 4-bit" : meta.provider?.name ?? "";
  return {
    title: `Language-model run: ${model}`,
    text: `${model}${via ? ` (${via})` : ""} on MSCoRe, KramaBench and MedAgentBench. ${perGroup} tasks per group${
      perGroup < 500 ? " (reduced scale; the brief specifies 500)" : ""}.`,
  };
}

/** Ablation results: convergence, intelligibility depth and cost by share of CF agents. */
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
          No experiment results yet. Run <code>bb ablate experiments/configs/mock-synthetic.toml</code> for a quick
          check; results appear here.
        </div>
      </section>
    );
  }

  const current = rows(selected);
  const meta = detail?.meta ?? {};
  const perGroup = rows(benchmarks.includes("all") ? "all" : selected)[0]?.trials ?? 0;
  const about = describe(meta, perGroup);
  const first = current[0];
  const last = current[current.length - 1];
  const hasTokens = first?.tokens_mean != null;

  return (
    <>
      <div className="run-head">
        <div className="desc">
          <h2>{about.title}</h2>
          <p>
            {about.text}
            {meta.git_commit ? <span className="muted"> · commit {String(meta.git_commit).slice(0, 7)}</span> : null}
          </p>
        </div>
        {list.length > 1 && (
          <div className="seg" aria-label="Experiment">
            {list.map((e) => (
              <button key={e.name} aria-pressed={e.name === name} onClick={() => setName(e.name)}>
                {e.provider === "mock" ? "Scripted agents" : "Language model"}
              </button>
            ))}
          </div>
        )}
      </div>

      {benchmarks.length > 1 && (
        <div className="seg" aria-label="Benchmark" style={{ justifySelf: "start" }}>
          {benchmarks.map((b) => (
            <button key={b} aria-pressed={b === selected} onClick={() => setBench(b)}>{NAMES[b] ?? b}</button>
          ))}
        </div>
      )}

      {first && last && (
        <div className="tiles">
          <Tile k="Convergence success, 0% → 100% CF" v={<>{pct(first.convergence_success)}<span className="arrow">→</span>{pct(last.convergence_success)}</>}
                s={`consensus on an accurate answer · ${first.trials} tasks per group`} />
          <Tile k="Sessions that deadlocked" v={pct(first.deadlock)}
                s={first.deadlock === 0 ? "no deadlock, so counterfactual agents never act" : "the same in every group before any replay"} />
          <Tile k="Deadlocks recovered, 0% → 100% CF" v={<>{pct(first.recovered)}<span className="arrow">→</span>{pct(last.recovered)}</>}
                s="share of deadlocked sessions that still reached consensus" />
          {hasTokens ? (
            <Tile k="Tokens per instance, 0% → 100% CF"
                  v={<>{compact(first.tokens_mean ?? 0)}<span className="arrow">→</span>{compact(last.tokens_mean ?? 0)}</>}
                  s="prompt + completion, live board and sandbox" />
          ) : (
            <Tile k="Model calls per session, 0% → 100% CF"
                  v={<>{(first.calls_mean ?? first.messages_mean).toFixed(1)}<span className="arrow">→</span>{(last.calls_mean ?? last.messages_mean).toFixed(1)}</>}
                  s="sandbox replays add calls; the mock reports no tokens" />
          )}
        </div>
      )}

      <div className="chart-row">
        <section className="panel chart">
          <header>
            <h2>Convergence success</h2>
            <span className="hint">by share of counterfactual-capable agents · 95% Wilson interval</span>
          </header>
          <ConvergenceChart series={selected === "all" ? benchmarks : [selected]} rows={rows} />
        </section>
        <div className="chart-col">
          <section className="panel chart">
            <header>
              <h2>Intelligibility depth</h2>
              <span className="hint">whole session, Mestha et al. Def. 2</span>
            </header>
            <IntelligibilityBars rows={current} />
          </section>
          <section className="panel chart">
            <header>
              <h2>{hasTokens ? "Tokens per instance" : "Model calls per session"}</h2>
              <span className="hint">{hasTokens ? "mean · live board and sandbox" : "mean · scripted agents report no tokens"}</span>
            </header>
            <CostBars rows={current} tokens={hasTokens} />
          </section>
        </div>
      </div>

      <section className="panel">
        <header><h2>All numbers</h2><span className="hint">{NAMES[selected] ?? selected}</span></header>
        <div className="panel-body" style={{ overflowX: "auto" }}>
          <GroupTable rows={current} />
          <h3 style={{ margin: "16px 0 6px" }}>Paired tests against the control group (exact McNemar)</h3>
          <table className="data">
            <thead>
              <tr><th>Comparison</th><th className="num">Pairs</th><th className="num">Solved only by control</th>
                <th className="num">Solved only by group</th><th className="num">p</th></tr>
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
    </>
  );
}

function Tile({ k, v, s }: { k: string; v: ReactNode; s: string }) {
  return (
    <div className="panel tile">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
      <span className="s">{s}</span>
    </div>
  );
}

function ConvergenceChart({ series, rows }: { series: string[]; rows: (b: string) => GroupRow[] }) {
  const [ref, W] = useWidth<HTMLDivElement>(640, 320);
  const [hover, setHover] = useState<{ b: string; r: GroupRow; x: number; y: number } | null>(null);
  const labels = series.length > 1;
  const H = 330, M = { top: 18, right: labels ? 128 : 24, bottom: 48, left: 48 };
  const x = d3.scaleLinear([0, 1], [M.left, W - M.right]);
  const y = d3.scaleLinear([0, 1], [H - M.bottom, M.top]);
  const ends = series.map((b) => ({ b, y: rows(b).at(-1)?.convergence_success ?? 0 })).sort((a, c) => a.y - c.y);
  for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 0.06);
  return (
    <div className="panel-body" style={{ position: "relative" }} ref={ref}>
      <svg width={W} height={H} role="img" aria-label="Convergence success by share of counterfactual-capable agents">
        {y.ticks(5).map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={M.left - 8} y={y(t) + 4} textAnchor="end" fontSize={12} fill="var(--muted)">{pct(t)}</text>
          </g>
        ))}
        {[0, 1 / 3, 2 / 3, 1].map((t) => (
          <text key={t} x={x(t)} y={H - M.bottom + 20} textAnchor="middle" fontSize={12} fill="var(--muted)">{pct(t)}</text>
        ))}
        <text x={(M.left + W - M.right) / 2} y={H - 8} textAnchor="middle" fontSize={12.5} fill="var(--ink-2)">
          Share of counterfactual-capable agents
        </text>
        {series.map((b) => {
          const rs = rows(b);
          const line = d3.line<GroupRow>().x((r) => x(r.cf_fraction)).y((r) => y(r.convergence_success))(rs) ?? "";
          return (
            <g key={b}>
              {rs.map((r) => (
                <line key={`ci${r.group}`} x1={x(r.cf_fraction)} x2={x(r.cf_fraction)} y1={y(r.convergence_ci[0])}
                      y2={y(r.convergence_ci[1])} stroke={SERIES[b]} strokeWidth={2} strokeLinecap="round" opacity={0.35} />
              ))}
              <path d={line} fill="none" stroke={SERIES[b]} strokeWidth={2} />
              {rs.map((r) => (
                <g key={r.group}>
                  <circle cx={x(r.cf_fraction)} cy={y(r.convergence_success)} r={14} fill="transparent"
                          onMouseEnter={(e) => setHover({ b, r, x: e.clientX, y: e.clientY })}
                          onMouseLeave={() => setHover(null)} />
                  <circle cx={x(r.cf_fraction)} cy={y(r.convergence_success)} r={5} fill={SERIES[b]}
                          stroke="var(--surface)" strokeWidth={2} pointerEvents="none" />
                  {!labels && (
                    <text x={x(r.cf_fraction)} y={y(r.convergence_success) - 12} textAnchor="middle" fontSize={12}
                          fill="var(--ink)" fontWeight={600}>{pct(r.convergence_success)}</text>
                  )}
                </g>
              ))}
            </g>
          );
        })}
        {labels && ends.map((e) => (
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
  const [ref, W] = useWidth<HTMLDivElement>(420, 260);
  const row = 32, M = { left: 48, right: 4, top: 4 };
  const H = M.top + rows.length * row;
  const x = d3.scaleLinear([0, 1], [M.left, W - M.right]);
  return (
    <div className="panel-body" ref={ref}>
      <svg width={W} height={H} role="img" aria-label="Share of sessions per intelligibility level">
        {rows.map((r, i) => {
          let left = 0;
          return (
            <g key={r.group} transform={`translate(0,${M.top + i * row})`}>
              <text x={M.left - 8} y={row / 2 + 3} textAnchor="end" fontSize={12} fill="var(--muted)">{share(r)}</text>
              {LEVELS.map((l) => {
                const v = (r as any)[l.key] as number;
                const start = left;
                left += v;
                return v > 0 ? (
                  <g key={l.key}>
                    <rect x={x(start)} y={4} width={Math.max(0, x(start + v) - x(start) - 2)} height={row - 10}
                          fill={l.color} rx={3}>
                      <title>{`${l.name}: ${pct(v)}`}</title>
                    </rect>
                    {v >= 0.1 && (
                      <text x={x(start + v / 2)} y={row / 2 + 4} textAnchor="middle" fontSize={11.5}
                            fill={l.key === "strong" || l.key === "ultra_strong" ? "#fff" : "#0b0b0b"}>{pct(v)}</text>
                    )}
                  </g>
                ) : null;
              })}
            </g>
          );
        })}
      </svg>
      <div className="legend" style={{ marginTop: 8 }}>
        {LEVELS.map((l) => (
          <span key={l.key} className="legend-item"><span className="swatch" style={{ background: l.color }} />{l.name}</span>
        ))}
      </div>
    </div>
  );
}

function CostBars({ rows, tokens }: { rows: GroupRow[]; tokens: boolean }) {
  const [ref, W] = useWidth<HTMLDivElement>(420, 260);
  if (!rows.length) return <div className="empty">No rows.</div>;
  const H = 210, M = { top: 24, bottom: 26, left: 48, right: 4 };
  const live = (r: GroupRow) => (tokens ? r.live_tokens_mean ?? 0 : r.calls_mean ?? r.messages_mean);
  const sandbox = (r: GroupRow) => (tokens ? r.sandbox_tokens_mean ?? 0 : 0);
  const max = d3.max(rows, (r) => live(r) + sandbox(r)) ?? 1;
  const y = d3.scaleLinear([0, max * 1.12], [H - M.bottom, M.top]).nice();
  const x = d3.scaleBand(rows.map(share), [M.left, W - M.right]).padding(0.38);
  const fmt = (v: number) => (tokens ? Math.round(v).toLocaleString() : v.toFixed(1));
  return (
    <div className="panel-body" ref={ref}>
      <svg width={W} height={H} role="img" aria-label={tokens ? "Mean tokens per instance by group" : "Mean model calls per session by group"}>
        {y.ticks(4).map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={M.left - 8} y={y(t) + 4} textAnchor="end" fontSize={11.5} fill="var(--muted)">{d3.format("~s")(t)}</text>
          </g>
        ))}
        {rows.map((r) => {
          const l = live(r);
          const s = sandbox(r);
          const bx = x(share(r))!;
          return (
            <g key={r.group}>
              <rect x={bx} y={y(l)} width={x.bandwidth()} height={y(0) - y(l)} fill="var(--tag-revise)" rx={3}>
                <title>{`${tokens ? "Live board" : "Calls"}: ${fmt(l)}`}</title>
              </rect>
              {s > 0 && (
                <rect x={bx} y={y(l + s)} width={x.bandwidth()} height={Math.max(0, y(l) - y(l + s) - 2)}
                      fill="var(--tag-objection)" rx={3}>
                  <title>{`Sandbox: ${fmt(s)} tokens`}</title>
                </rect>
              )}
              <text x={bx + x.bandwidth() / 2} y={y(l + s) - 7} textAnchor="middle" fontSize={12} fill="var(--ink)">
                {fmt(l + s)}
              </text>
              <text x={bx + x.bandwidth() / 2} y={H - 6} textAnchor="middle" fontSize={12} fill="var(--muted)">{share(r)}</text>
            </g>
          );
        })}
      </svg>
      {tokens && (
        <div className="legend" style={{ marginTop: 8 }}>
          <span className="legend-item"><span className="swatch" style={{ background: "var(--tag-revise)" }} />Live board</span>
          <span className="legend-item"><span className="swatch" style={{ background: "var(--tag-objection)" }} />Counterfactual sandbox</span>
        </div>
      )}
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
            <td className="num">{r.tokens_mean == null ? "–" : Math.round(r.tokens_mean).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
