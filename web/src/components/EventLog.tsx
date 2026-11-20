import { useEffect, useRef } from "react";
import type { BoardEvent, MessageRecord } from "../types";
import { StatusBadge, TagLabel } from "./Badges";

/** The board log: messages in full, other state changes as one-line entries. */
export function EventLog({
  events,
  selected,
  follow,
  onSelect,
}: {
  events: BoardEvent[];
  selected: string | null;
  follow: boolean;
  onSelect: (id: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // scroll the log itself, never the page
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [events.length, follow]);

  return (
    <section className="panel">
      <header>
        <h2>Board log</h2>
        <span className="hint">{events.length} events</span>
      </header>
      <div className="panel-body log" aria-live="polite" ref={box}>
        {events.map((e) => (
          <LogEntry key={e.seq} event={e} selected={selected} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}

function LogEntry({ event, selected, onSelect }: {
  event: BoardEvent;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const d = event.data;
  switch (event.kind) {
    case "message": {
      const m = d.message as MessageRecord;
      const j = m.judgment;
      return (
        <div className={`log-item${selected === m.message_id ? " selected" : ""}`}
             onClick={() => onSelect(m.message_id)} id={`msg-${m.message_id}`}>
          <span className="num">#{m.iteration}</span>
          <div>
            <div className="head">
              <span className="who">{m.agent_id}</span>
              <TagLabel tag={m.tag} />
              <span className="pred">{m.prediction}</span>
              {m.metadata?.counterfactual ? <span className="judg">counterfactual</span> : null}
            </div>
            <p>{m.explanation}</p>
            {j && (
              <div className="judg">
                peer {j.prediction_matches ? "matches" : "differs"} · explanation{" "}
                {j.explanation_agrees ? "agrees" : "conflicts"} · {j.changed ? "changed" : "unchanged"}
              </div>
            )}
          </div>
        </div>
      );
    }
    case "status":
      if (d.status === "RUNNING" && d.previous === "INITIALIZED") return null;
      return (
        <div className="log-item system">
          <span className="num" />
          <div>
            <StatusBadge status={d.status} /> {d.reason}
          </div>
        </div>
      );
    case "intervention":
      return (
        <div className="log-item system">
          <span className="num">CF</span>
          <div>
            <strong>{d.applied ? "Counterfactual intervention" : "Counterfactual search found nothing"}</strong>
            {" · "}
            {d.branches?.length ?? 0} sandbox branch(es). {d.reason}
          </div>
        </div>
      );
    case "context_revision":
      return (
        <div className="log-item system">
          <span className="num" />
          <div>
            {d.agent_id} revises its position to <span className="mono">{d.prediction}</span>
          </div>
        </div>
      );
    case "weight":
      return (
        <div className="log-item system">
          <span className="num" />
          <div>
            {d.agent_id} weight {Number(d.previous).toFixed(2)} → {Number(d.weight).toFixed(2)} ({d.reason})
          </div>
        </div>
      );
    case "format_error":
      return (
        <div className="log-item system">
          <span className="num" />
          <div>
            {d.agent_id}: {d.recovered ? "rejected attempt, then a valid message" : `no valid message (${d.error})`}
          </div>
        </div>
      );
    case "collision":
      return (
        <div className="log-item system">
          <span className="num" />
          <div>{d.agent_id}'s draft discarded: the board moved from version {d.expected_version} to {d.actual_version}</div>
        </div>
      );
    case "tool":
      return (
        <div className="log-item system">
          <span className="num" />
          <div>
            {d.agent_id} called <span className="mono">{d.tool}</span>
          </div>
        </div>
      );
    default:
      return null;
  }
}
