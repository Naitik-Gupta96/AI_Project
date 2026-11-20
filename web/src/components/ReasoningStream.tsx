import { useEffect, useRef, useState } from "react";
import type { Intervention, MessageRecord } from "../types";
import { tagPaint } from "./Badges";

const LANE = 34;
const LEFT = 92;
const TOP = 22;

/**
 * Reasoning stream: one lane per agent, one column per message. Shows who was activated when
 * and what they said; dashed lines mark applied counterfactual interventions.
 */
export function ReasoningStream({
  agents,
  messages,
  interventions,
  selected,
  onSelect,
}: {
  agents: string[];
  messages: MessageRecord[];
  interventions: Intervention[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    if (!wrap.current) return;
    const observer = new ResizeObserver(([e]) => setWidth(Math.max(320, e.contentRect.width)));
    observer.observe(wrap.current);
    return () => observer.disconnect();
  }, []);

  const columns = Math.max(messages.length, 12);
  const step = Math.max(18, (width - LEFT - 12) / columns);
  const height = TOP + agents.length * LANE + 8;
  const x = (iteration: number) => LEFT + (iteration - 0.5) * step;
  const y = (agent: string) => TOP + agents.indexOf(agent) * LANE + LANE / 2;

  return (
    <section className="panel">
      <header>
        <h2>Reasoning stream</h2>
        <span className="hint">lanes are agents, columns are message numbers</span>
      </header>
      <div className="panel-body" ref={wrap}>
        <svg className="stream-svg" width={width} height={height} role="img"
             aria-label="Messages by agent over time">
          {agents.map((a) => (
            <g key={a}>
              <line className="gridline" x1={LEFT} x2={width - 8} y1={y(a)} y2={y(a)} />
              <text className="lane-label" x={0} y={y(a) + 4}>{a}</text>
            </g>
          ))}
          {messages.map((m) => (
            <text key={`n${m.iteration}`} x={x(m.iteration)} y={12} textAnchor="middle">
              {m.iteration}
            </text>
          ))}
          {interventions.filter((i) => i.applied).map((i, k) => (
            <g key={`i${k}`}>
              <line className="marker-line" x1={LEFT + i.at_iteration * step} x2={LEFT + i.at_iteration * step}
                    y1={TOP - 4} y2={height - 4} />
              <title>{i.reason}</title>
            </g>
          ))}
          {messages.slice(1).map((m, k) => {
            const prev = messages[k];
            return (
              <line key={`c${m.iteration}`} x1={x(prev.iteration)} y1={y(prev.agent_id)}
                    x2={x(m.iteration)} y2={y(m.agent_id)} stroke="var(--grid)" strokeWidth={1.5} />
            );
          })}
          {messages.map((m) => {
            const paint = tagPaint(m.tag);
            return (
              <g key={m.message_id} style={{ cursor: "pointer" }} onClick={() => onSelect(m.message_id)}>
                <circle cx={x(m.iteration)} cy={y(m.agent_id)} r={12} fill="transparent" />
                <circle cx={x(m.iteration)} cy={y(m.agent_id)} r={6} fill={paint.fill}
                        stroke={paint.stroke} strokeWidth={m.message_id === selected ? 3.5 : 2} />
                <title>{`#${m.iteration} ${m.agent_id} ${m.tag} ${m.prediction}`}</title>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}
