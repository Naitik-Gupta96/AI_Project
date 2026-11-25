import * as d3 from "d3";
import "d3-transition"; // adds selection.transition(); a side-effect import the bundler would drop
import { useEffect, useMemo, useRef, useState } from "react";
import { reasoningGraph } from "../board";
import type { MessageRecord } from "../types";
import { useWidth } from "../useWidth";
import { tagPaint, TagLabel } from "./Badges";

const HEIGHT = 500;
const INNER = 40; // radius of the innermost ring around the task node
const NODE = 12;

const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/**
 * The reasoning graph. The task is the root at the centre. Each agent owns an angular sector;
 * a message sits in its author's sector, one ring further out per message number, and a curved
 * edge, coloured by the reply's tag, joins it to the message it answered (message 1 joins the
 * root). Marks carry their message number and are coloured by PXP tag (REFUTE hollow, REJECT
 * solid); a run of objections at the end of the log pulses red.
 */
export function BoardGraph({
  agents,
  messages,
  question,
  alertIds,
  selected,
  onSelect,
  cfAgents,
  weights,
}: {
  agents: string[];
  messages: MessageRecord[];
  question: string;
  alertIds: Set<string>;
  selected: string | null;
  onSelect: (id: string | null) => void;
  cfAgents: string[];
  weights: Record<string, number>;
}) {
  const [wrap, width] = useWidth<HTMLDivElement>(640, 320);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ m: MessageRecord; x: number; y: number } | null>(null);
  const graph = useMemo(() => reasoningGraph(messages), [messages]);

  const cx = width / 2;
  const cy = HEIGHT / 2 + 6;
  // leave room outside the rings for the agent labels (narrow screens lose the sides first)
  const outer = Math.max(90, Math.min(width / 2 - 130, HEIGHT / 2 - 62));
  // one empty ring outside the last message keeps message labels clear of the agent names
  const rings = Math.max(8, messages.length + 1);
  const radius = (iteration: number) => INNER + ((outer - INNER) * iteration) / rings;
  const sector = (2 * Math.PI) / Math.max(1, agents.length);
  const angleOf = (agent: string) => -Math.PI / 2 + sector * Math.max(0, agents.indexOf(agent));
  const showPredictions = messages.length <= 14;

  useEffect(() => {
    const svg = d3.select(svgRef.current!);
    const byId = new Map(messages.map((m) => [m.message_id, m]));
    const pos = new Map<string, { x: number; y: number; a: number; r: number }>();
    pos.set("root", { x: cx, y: cy, a: 0, r: 0 });
    for (const m of messages) {
      // alternate a small offset inside the sector so consecutive posts by one agent fan out
      const before = messages.filter((x) => x.agent_id === m.agent_id && x.iteration < m.iteration).length;
      const spread = Math.min(sector * 0.3, 0.46);
      const a = angleOf(m.agent_id) + (before % 2 === 0 ? -1 : 1) * spread * 0.5;
      const r = radius(m.iteration);
      pos.set(m.message_id, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), a, r });
    }

    const curve = (s: { x: number; y: number; a: number; r: number }, t: { x: number; y: number; a: number; r: number }) => {
      if (s.r === 0) return `M${s.x},${s.y}L${t.x},${t.y}`;
      const mid = ((Math.max(s.r, t.r) + Math.min(s.r, t.r)) / 2) * 0.7;
      const a = Math.atan2(Math.sin(s.a) + Math.sin(t.a), Math.cos(s.a) + Math.cos(t.a));
      return `M${s.x},${s.y}Q${cx + mid * Math.cos(a)},${cy + mid * Math.sin(a)} ${t.x},${t.y}`;
    };

    const links = graph.links.map((l) => ({ ...l, d: curve(pos.get(l.source)!, pos.get(l.target)!) }));
    svg
      .select("g.links")
      .selectAll<SVGPathElement, (typeof links)[number]>("path")
      .data(links, (d) => d.target)
      .join((enter) => enter.append("path").attr("class", "link").attr("opacity", 0)
        .call((p) => p.transition().duration(400).attr("opacity", 1)))
      .attr("d", (d) => d.d)
      .attr("stroke", (d) => tagPaint(d.tag).stroke);

    const nodes = graph.nodes.filter((n) => n.kind === "message").map((n) => ({ ...n, p: pos.get(n.id)! }));
    const sel = svg
      .select("g.nodes")
      .selectAll<SVGGElement, (typeof nodes)[number]>("g.node")
      .data(nodes, (d) => d.id)
      .join((enter) => {
        const g = enter.append("g").attr("class", "node");
        g.append("circle").attr("class", "hit").attr("r", NODE + 6).attr("fill", "transparent");
        g.append("circle").attr("class", "mark").attr("r", 0)
          .transition().duration(320).attr("r", NODE);
        g.append("text").attr("class", "n").attr("text-anchor", "middle").attr("dy", 3.8);
        g.append("text").attr("class", "pred");
        g.attr("transform", (d) => {
          const parent = byId.get(d.message!.in_reply_to ?? "");
          const from = parent ? pos.get(parent.message_id)! : { x: cx, y: cy };
          return `translate(${from.x},${from.y})`;
        });
        return g;
      });
    sel.transition().duration(400).attr("transform", (d) => `translate(${d.p.x},${d.p.y})`);
    sel
      .select<SVGCircleElement>("circle.mark")
      .attr("stroke", (d) => tagPaint(d.message!.tag).stroke)
      .attr("fill", (d) => tagPaint(d.message!.tag).fill)
      .attr("stroke-width", (d) => (d.id === selected ? 4 : 2.5));
    sel
      .select("text.n")
      .attr("fill", (d) => (d.message!.tag === "REFUTE" ? tagPaint("REFUTE").stroke : "var(--surface)"))
      .text((d) => d.message!.iteration);
    sel
      .select("text.pred")
      .attr("text-anchor", (d) => (Math.cos(d.p.a) >= 0 ? "start" : "end"))
      .attr("dx", (d) => (Math.cos(d.p.a) >= 0 ? NODE + 6 : -NODE - 6))
      .attr("dy", 4)
      .text((d) => (showPredictions ? clip(d.message!.prediction, 16) : ""));
    sel.selectAll("circle.pulse").remove();
    sel.filter((d) => alertIds.has(d.id)).insert("circle", "circle.mark").attr("class", "pulse").attr("r", NODE);
    sel
      .on("mouseenter mousemove", (event, d) => setHover({ m: d.message!, x: event.clientX, y: event.clientY }))
      .on("mouseleave", () => setHover(null))
      .on("click", (_, d) => onSelect(d.message!.message_id));
    // positions depend on the width, so the layout is recomputed on resize too
  }, [graph, width, alertIds, selected, onSelect, agents, showPredictions]);

  const ticks = d3.range(1, rings + 1);

  return (
    <div ref={wrap} style={{ position: "relative" }}>
      <svg ref={svgRef} className="graph-svg" width={width} height={HEIGHT} role="img"
           aria-label={`Reasoning graph with ${messages.length} messages. Task: ${question}`}>
        <g>
          {ticks.map((i) => (
            <circle key={i} className="ring" cx={cx} cy={cy} r={radius(i)} />
          ))}
          {agents.map((a) => {
            const angle = angleOf(a) + sector / 2;
            return (
              <line key={`s${a}`} className="sector" x1={cx + INNER * Math.cos(angle)} y1={cy + INNER * Math.sin(angle)}
                    x2={cx + (outer + 10) * Math.cos(angle)} y2={cy + (outer + 10) * Math.sin(angle)} />
            );
          })}
          {agents.map((a) => {
            const angle = angleOf(a);
            const r = outer + 38;
            const x = cx + r * Math.cos(angle);
            const y = cy + r * Math.sin(angle);
            const anchor = Math.abs(Math.cos(angle)) < 0.2 ? "middle" : Math.cos(angle) > 0 ? "start" : "end";
            const above = Math.sin(angle) < -0.5;
            const w = weights[a] ?? 1;
            return (
              <g key={`l${a}`}>
                <text className="agent-label" x={x} y={above ? y - 10 : y + 2} textAnchor={anchor}>
                  {a}{cfAgents.includes(a) ? " · CF" : ""}
                </text>
                <text className="agent-sub" x={x} y={above ? y + 5 : y + 17} textAnchor={anchor}>
                  weight {w.toFixed(2)}
                </text>
              </g>
            );
          })}
        </g>
        <g className="links" />
        <g>
          <circle cx={cx} cy={cy} r={16} fill="var(--surface)" stroke="var(--ink)" strokeWidth={2}>
            <title>{question}</title>
          </circle>
          <text className="root-label" x={cx} y={cy + 4} textAnchor="middle">T</text>
          <text className="agent-sub" x={cx} y={cy + 32} textAnchor="middle">task</text>
        </g>
        <g className="nodes" />
      </svg>
      {hover && (
        <div className="tooltip" style={{ left: hover.x + 14, top: hover.y + 14 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
            <span className="mono">#{hover.m.iteration}</span>
            <strong>{hover.m.agent_id}</strong>
            <TagLabel tag={hover.m.tag} />
          </div>
          <div className="mono" style={{ margin: "4px 0" }}>{hover.m.prediction}</div>
          <div>{hover.m.explanation}</div>
          {hover.m.judgment && (
            <div className="muted mono" style={{ marginTop: 4 }}>
              match {String(hover.m.judgment.prediction_matches)} · agree{" "}
              {String(hover.m.judgment.explanation_agrees)} · changed {String(hover.m.judgment.changed)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
