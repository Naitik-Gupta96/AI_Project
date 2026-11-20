import * as d3 from "d3";
import "d3-transition"; // adds selection.transition(); a side-effect import the bundler would drop
import { useEffect, useMemo, useRef, useState } from "react";
import { reasoningGraph } from "../board";
import type { MessageRecord } from "../types";
import { tagPaint, TagLabel } from "./Badges";

const HEIGHT = 470;
const INNER = 34; // radius of the task node's ring

/**
 * The reasoning graph. The task is the root at the centre. Each agent owns an angular sector;
 * a message sits in its author's sector, one ring further out per message number, and a curved
 * edge joins it to the message it answered (message 1 joins the root). Marks are coloured by
 * PXP tag (REFUTE hollow, REJECT solid); a run of objections at the end of the log pulses red.
 */
export function BoardGraph({
  agents,
  messages,
  question,
  alertIds,
  selected,
  onSelect,
}: {
  agents: string[];
  messages: MessageRecord[];
  question: string;
  alertIds: Set<string>;
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<{ m: MessageRecord; x: number; y: number } | null>(null);
  const graph = useMemo(() => reasoningGraph(messages), [messages]);

  useEffect(() => {
    if (!wrap.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(300, entry.contentRect.width)));
    observer.observe(wrap.current);
    return () => observer.disconnect();
  }, []);

  const cx = width / 2;
  const cy = HEIGHT / 2;
  // leave room outside the rings for the agent labels (narrow screens lose the sides first)
  const outer = Math.min(width / 2 - 78, HEIGHT / 2 - 36);
  const rings = Math.max(8, messages.length);
  const radius = (iteration: number) => INNER + ((outer - INNER) * iteration) / rings;
  const sector = (2 * Math.PI) / Math.max(1, agents.length);
  const angleOf = (agent: string) => -Math.PI / 2 + sector * Math.max(0, agents.indexOf(agent));

  const point = (m: MessageRecord) => {
    // alternate a small offset inside the sector so consecutive posts by one agent fan out
    const sameAgentBefore = messages.filter((x) => x.agent_id === m.agent_id && x.iteration < m.iteration).length;
    const spread = Math.min(sector * 0.28, 0.42);
    const a = angleOf(m.agent_id) + (sameAgentBefore % 2 === 0 ? -1 : 1) * spread * 0.5;
    const r = radius(m.iteration);
    return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), a, r };
  };

  useEffect(() => {
    const svg = d3.select(svgRef.current!);
    const byId = new Map(messages.map((m) => [m.message_id, m]));
    const pos = new Map<string, { x: number; y: number; a: number; r: number }>();
    pos.set("root", { x: cx, y: cy, a: 0, r: 0 });
    for (const m of messages) pos.set(m.message_id, point(m));

    const curve = (s: { x: number; y: number; a: number; r: number }, t: { x: number; y: number; a: number; r: number }) => {
      if (s.r === 0) return `M${s.x},${s.y}L${t.x},${t.y}`;
      const mid = (Math.max(s.r, t.r) + Math.min(s.r, t.r)) / 2 * 0.72;
      const a = Math.atan2(Math.sin(s.a) + Math.sin(t.a), Math.cos(s.a) + Math.cos(t.a));
      return `M${s.x},${s.y}Q${cx + mid * Math.cos(a)},${cy + mid * Math.sin(a)} ${t.x},${t.y}`;
    };

    const links = graph.links.map((l) => ({ ...l, d: curve(pos.get(l.source)!, pos.get(l.target)!) }));
    svg
      .select("g.links")
      .selectAll<SVGPathElement, (typeof links)[number]>("path")
      .data(links, (d) => d.target)
      .join((enter) => enter.append("path").attr("class", "link").attr("opacity", 0)
        .call((p) => p.transition().duration(350).attr("opacity", 1)))
      .attr("d", (d) => d.d);

    const nodes = graph.nodes.filter((n) => n.kind === "message").map((n) => ({ ...n, p: pos.get(n.id)! }));
    const sel = svg
      .select("g.nodes")
      .selectAll<SVGGElement, (typeof nodes)[number]>("g.node")
      .data(nodes, (d) => d.id)
      .join((enter) => {
        const g = enter.append("g").attr("class", "node");
        g.append("circle").attr("class", "hit").attr("r", 14).attr("fill", "transparent");
        g.append("circle").attr("class", "mark").attr("r", 0)
          .transition().duration(300).attr("r", 7);
        g.append("text");
        g.attr("transform", (d) => {
          const parent = byId.get(d.message!.in_reply_to ?? "");
          const from = parent ? pos.get(parent.message_id)! : { x: cx, y: cy };
          return `translate(${from.x},${from.y})`;
        });
        return g;
      });
    sel.transition().duration(350).attr("transform", (d) => `translate(${d.p.x},${d.p.y})`);
    sel
      .select<SVGCircleElement>("circle.mark")
      .attr("stroke", (d) => tagPaint(d.message!.tag).stroke)
      .attr("fill", (d) => tagPaint(d.message!.tag).fill)
      .attr("stroke-width", (d) => (d.id === selected ? 3.5 : 2));
    sel
      .select("text")
      .attr("text-anchor", (d) => (Math.cos(d.p.a) >= 0 ? "start" : "end"))
      .attr("dx", (d) => (Math.cos(d.p.a) >= 0 ? 11 : -11))
      .attr("dy", 4)
      .text((d) => `#${d.message!.iteration}`);
    sel.selectAll("circle.pulse").remove();
    sel.filter((d) => alertIds.has(d.id)).insert("circle", "circle.mark").attr("class", "pulse").attr("r", 9);
    sel
      .on("mouseenter mousemove", (event, d) => setHover({ m: d.message!, x: event.clientX, y: event.clientY }))
      .on("mouseleave", () => setHover(null))
      .on("click", (_, d) => onSelect(d.message!.message_id));
    // positions depend on the width, so the layout is recomputed on resize too
  }, [graph, width, alertIds, selected, onSelect, agents]);

  const ticks = d3.range(1, rings + 1).filter((i) => rings <= 12 || i % 2 === 0);

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
              <line key={`s${a}`} x1={cx + INNER * Math.cos(angle)} y1={cy + INNER * Math.sin(angle)}
                    x2={cx + (outer + 14) * Math.cos(angle)} y2={cy + (outer + 14) * Math.sin(angle)}
                    stroke="var(--grid)" />
            );
          })}
          {agents.map((a) => {
            const angle = angleOf(a);
            const r = outer + 22;
            return (
              <text key={`l${a}`} className="root-label" x={cx + r * Math.cos(angle)} y={cy + r * Math.sin(angle) + 4}
                    textAnchor={Math.abs(Math.cos(angle)) < 0.2 ? "middle" : Math.cos(angle) > 0 ? "start" : "end"}>
                {a}
              </text>
            );
          })}
        </g>
        <g className="links" />
        <g>
          <circle cx={cx} cy={cy} r={11} fill="var(--surface)" stroke="var(--ink)" strokeWidth={2} />
          <text className="root-label" x={cx} y={cy + 28} textAnchor="middle">Task</text>
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
