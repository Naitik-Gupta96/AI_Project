import { useState } from "react";
import type { CfMessage } from "../api";
import type { Branch, Intervention, MessageRecord, Status } from "../types";
import { StatusBadge, TagLabel } from "./Badges";

interface View {
  live: boolean;
  atIteration: number;
  proximityBefore: number;
  branches: Branch[];
  intervention: Intervention | null;
}

/** Branches still running in the sandbox, rebuilt from the live counterfactual stream. */
function liveView(cf: CfMessage[]): View | null {
  const start = cf.map((m) => m.kind).lastIndexOf("cf.start");
  if (start < 0) return null;
  const tail = cf.slice(start);
  if (tail.some((m) => m.kind === "cf.applied" || m.kind === "cf.none")) return null;
  const branches = new Map<string, Branch>();
  for (const m of tail) {
    if (m.kind === "cf.branch_start") {
      branches.set(m.data.branch_id, {
        branch_id: m.data.branch_id, agent_id: m.data.agent_id, target: m.data.target,
        candidate: m.data.candidate, lesson: "", status: "RUNNING", final_prediction: null,
        proximity: 0, credit: 0, messages: [],
      });
    } else if (m.kind === "cf.branch_event" && m.data.event.kind === "message") {
      const b = branches.get(m.data.branch_id);
      if (b) b.messages = [...b.messages, m.data.event.data.message];
    } else if (m.kind === "cf.branch_end") {
      branches.set(m.data.branch_id, m.data as Branch);
    }
  }
  return {
    live: true,
    atIteration: tail[0].data.at_iteration,
    proximityBefore: tail[0].data.proximity,
    branches: [...branches.values()],
    intervention: null,
  };
}

export function CounterfactualPanel({
  interventions,
  cf,
  liveMessages,
  cfAgents,
}: {
  interventions: Intervention[];
  cf: CfMessage[];
  liveMessages: MessageRecord[];
  cfAgents: string[];
}) {
  const [pick, setPick] = useState<number | null>(null);
  const running = liveView(cf);
  const views: View[] = interventions.map((i) => ({
    live: false, atIteration: i.at_iteration, proximityBefore: i.proximity_before,
    branches: i.branches, intervention: i,
  }));
  if (running) views.push(running);

  if (!views.length) {
    return (
      <section className="panel">
        <header>
          <h2>Counterfactual simulation</h2>
        </header>
        <div className="empty">
          {cfAgents.length
            ? `If the board deadlocks, ${cfAgents.join(", ")} will replay the session in a sandbox here.`
            : "No counterfactual-capable agents in this session."}
        </div>
      </section>
    );
  }

  const index = pick !== null && pick < views.length ? pick : views.length - 1;
  const view = views[index];
  const ranked = [...view.branches].sort((a, b) => b.credit - a.credit);
  const from = Math.min(...view.branches.map((b) => b.target.iteration), view.atIteration);
  const original = liveMessages.filter((m) => m.iteration >= from && m.iteration <= view.atIteration);

  return (
    <section className="panel">
      <header>
        <h2>Counterfactual simulation</h2>
        <span className="hint">
          {view.live ? "sandbox running" : view.intervention?.applied ? "applied to the live board" : "no positive credit"}
        </span>
        <span className="spacer" />
        {views.length > 1 && views.map((_, k) => (
          <button key={k} className="tab" aria-selected={k === index} onClick={() => setPick(k)}>
            Deadlock {k + 1}
          </button>
        ))}
      </header>
      <div className="panel-body">
        {view.intervention && (
          <p style={{ marginTop: 0 }}>
            {view.intervention.reason}.
            {view.intervention.applied && view.intervention.weight_before !== view.intervention.weight_after && (
              <> Weight of {view.intervention.agent_id}: {view.intervention.weight_before?.toFixed(2)} →{" "}
                {view.intervention.weight_after?.toFixed(2)}.</>
            )}
          </p>
        )}
        <div className="cf-split">
          <div>
            <h3 style={{ fontSize: 13, marginBottom: 6 }}>Live board, up to the deadlock</h3>
            <div className="timeline">
              {original.map((m) => (
                <Row key={m.message_id} m={m}
                     className={view.branches.some((b) => b.target.message_id === m.message_id) ? "diverge" : ""} />
              ))}
              <div className="end"><StatusBadge status="DEADLOCK" /> proximity {view.proximityBefore.toFixed(2)}</div>
            </div>
          </div>
          <div className="branch-list">
            {ranked.map((b) => (
              <BranchCard key={b.branch_id} b={b} before={view.proximityBefore}
                          chosen={view.intervention?.chosen_branch === b.branch_id} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function BranchCard({ b, before, chosen }: { b: Branch; before: number; chosen: boolean }) {
  const done = b.status !== "RUNNING";
  return (
    <div className={`branch${chosen ? " chosen" : ""}`}>
      <header>
        <strong>{b.agent_id}</strong>
        <span className="mono">replaces #{b.target.iteration}</span>
        <span>
          <TagLabel tag={b.target.tag} /> <span className="mono">{b.target.prediction}</span> →{" "}
          <TagLabel tag={b.candidate.tag} /> <span className="mono">{b.candidate.prediction}</span>
        </span>
        <span className="spacer" />
        {chosen && <strong>applied</strong>}
      </header>
      <div className="timeline">
        {b.messages.map((m, k) => (
          <Row key={m.message_id} m={m} className={k === 0 ? "diverge" : ""} />
        ))}
      </div>
      {done && (
        <div className="credit">
          <StatusBadge status={b.status as Status} />
          <ProximityBar before={before} after={b.proximity} />
          <span>proximity {before.toFixed(2)} → {b.proximity.toFixed(2)} · credit {b.credit >= 0 ? "+" : ""}{b.credit.toFixed(2)}</span>
        </div>
      )}
      {b.lesson && <div className="lesson">Lesson: {b.lesson}</div>}
    </div>
  );
}

function Row({ m, className = "" }: { m: MessageRecord; className?: string }) {
  return (
    <div className={`row ${className}`}>
      <span className="num">#{m.iteration}</span>
      <span>{m.agent_id}</span>
      <TagLabel tag={m.tag} />
      <span className="pred">{m.prediction}</span>
    </div>
  );
}

/** Consensus proximity before (tick) and after (bar) on a 0-1 track. */
function ProximityBar({ before, after }: { before: number; after: number }) {
  const w = 96;
  return (
    <svg width={w} height={10} aria-hidden="true">
      <rect x={0} y={3} width={w} height={4} rx={2} fill="var(--grid)" />
      <rect x={0} y={3} width={Math.max(4, after * w)} height={4} rx={2} fill="var(--ink-2)" />
      <line x1={before * w} x2={before * w} y1={0} y2={10} stroke="var(--ink)" strokeWidth={2} />
    </svg>
  );
}
