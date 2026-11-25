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

/** True while sandbox branches are still streaming (used by the story strip). */
export function sandboxRunning(cf: CfMessage[]): boolean {
  return liveView(cf) !== null;
}

/**
 * The counterfactual simulation, side by side: the live board up to the deadlock on the left,
 * every sandbox branch on the right (aligned at the message it replaces), with its consensus
 * proximity, credit and lesson, and what was applied to the live board.
 */
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
          <h2>Counterfactual replay</h2>
          <span className="hint">{cfAgents.length ? "waiting for a deadlock" : "off in this session"}</span>
        </header>
        <div className="panel-body">
          {cfAgents.length ? (
            <div className="cf-empty">
              <p>
                If the board deadlocks, <strong>{cfAgents.join(", ")}</strong> will look back at
                {cfAgents.length > 1 ? " their" : " its"} own past messages:
              </p>
              <ol>
                <li>copy the board into an isolated sandbox;</li>
                <li>propose alternatives to each of its last messages;</li>
                <li>replay the rest of the session from each alternative;</li>
                <li>score each by how much closer it brings the team to consensus;</li>
                <li>apply the best one to the live board: a lesson in its prompt, a revised position and a lower voting weight.</li>
              </ol>
            </div>
          ) : (
            <div className="cf-empty">
              <p>No agent in this session is counterfactual-capable, so a deadlock ends the session.</p>
            </div>
          )}
        </div>
      </section>
    );
  }

  const index = pick !== null && pick < views.length ? pick : views.length - 1;
  const view = views[index];
  const ranked = [...view.branches].sort((a, b) => b.credit - a.credit);
  const from = Math.min(...view.branches.map((b) => b.target.iteration), view.atIteration);
  const original = liveMessages.filter((m) => m.iteration >= from && m.iteration <= view.atIteration);
  const iv = view.intervention;
  const best = ranked.find((b) => b.status !== "RUNNING");
  const chosen = iv?.applied ? view.branches.find((b) => b.branch_id === iv.chosen_branch) : undefined;
  const state = view.live ? "sandbox running" : iv?.applied ? "applied to the live board" : "no alternative helped";

  return (
    <section className="panel">
      <header>
        <h2>Counterfactual replay</h2>
        <span className="hint">{state}</span>
        <span className="spacer" />
        {views.length > 1 && (
          <div className="seg">
            {views.map((_, k) => (
              <button key={k} aria-pressed={k === index} onClick={() => setPick(k)}>Deadlock {k + 1}</button>
            ))}
          </div>
        )}
      </header>
      <div className="panel-body">
        <div className="cf-summary">
          <div className="stat">
            <span className="k">Alternatives replayed</span>
            <span className="v">{view.branches.length}{view.live ? " so far" : ""}</span>
          </div>
          <div className="stat">
            <span className="k">Best credit</span>
            <span className="v">{best ? `${best.credit >= 0 ? "+" : ""}${best.credit.toFixed(2)}` : "…"}</span>
          </div>
          <div className="stat">
            <span className="k">Applied</span>
            <span className="v">
              {view.live ? "…" : chosen && iv
                ? `${iv.agent_id}: #${chosen.target.iteration} → ${chosen.candidate.prediction}`
                : "nothing"}
            </span>
          </div>
        </div>
        {chosen && iv && (
          <p className="lesson" style={{ marginBottom: 14 }}>
            Lesson added to {iv.agent_id}'s prompt: {iv.lesson || chosen.lesson}
            {iv.weight_before !== iv.weight_after && iv.weight_before != null && iv.weight_after != null && (
              <> · voting weight {iv.weight_before.toFixed(2)} → {iv.weight_after.toFixed(2)}</>
            )}
          </p>
        )}
        <div className="cf-split">
          <div>
            <div className="col-title">Live board, up to the deadlock</div>
            <div className="timeline">
              {original.map((m) => (
                <Row key={m.message_id} m={m}
                     className={view.branches.some((b) => b.target.message_id === m.message_id) ? "diverge" : ""} />
              ))}
              <div className="end"><StatusBadge status="DEADLOCK" /> proximity {view.proximityBefore.toFixed(2)}</div>
            </div>
          </div>
          <div>
            <div className="col-title">Sandbox branches, best first</div>
            <div className="branch-list">
              {ranked.map((b) => (
                <BranchCard key={b.branch_id} b={b} before={view.proximityBefore}
                            chosen={iv?.chosen_branch === b.branch_id} />
              ))}
            </div>
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
        <span className="muted">replaces #{b.target.iteration}</span>
        <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <TagLabel tag={b.target.tag} /> <span className="mono">{b.target.prediction}</span>
          <span className="muted">→</span>
          <TagLabel tag={b.candidate.tag} /> <span className="mono">{b.candidate.prediction}</span>
        </span>
        <span className="spacer" />
        {chosen && <span className="applied">APPLIED</span>}
      </header>
      <div className="timeline">
        {b.messages.map((m, k) => (
          <Row key={m.message_id} m={m} className={k === 0 ? "diverge" : ""} />
        ))}
      </div>
      {done ? (
        <div className="credit">
          <StatusBadge status={b.status as Status} />
          <ProximityBar before={before} after={b.proximity} />
          <span>proximity {before.toFixed(2)} → {b.proximity.toFixed(2)}</span>
          <span className="big">{b.credit >= 0 ? "+" : ""}{b.credit.toFixed(2)}</span>
        </div>
      ) : (
        <div className="credit">replaying…</div>
      )}
    </div>
  );
}

function Row({ m, className = "" }: { m: MessageRecord; className?: string }) {
  return (
    <div className={`row ${className}`}>
      <span className="num">#{m.iteration}</span>
      <span>{m.agent_id}</span>
      <TagLabel tag={m.tag} />
      <span className="pred" title={m.prediction}>{m.prediction}</span>
    </div>
  );
}

/** Consensus proximity before (tick) and after (bar) on a 0-1 track. */
function ProximityBar({ before, after }: { before: number; after: number }) {
  const w = 90;
  return (
    <svg width={w} height={10} aria-hidden="true">
      <rect x={0} y={3} width={w} height={4} rx={2} fill="var(--grid)" />
      <rect x={0} y={3} width={Math.max(4, after * w)} height={4} rx={2} fill="var(--tag-revise)" />
      <line x1={before * w} x2={before * w} y1={0} y2={10} stroke="var(--ink)" strokeWidth={2} />
    </svg>
  );
}
