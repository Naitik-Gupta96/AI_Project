import type { Activation, BoardState, MessageRecord } from "../types";
import { TagLabel } from "./Badges";

/** One card per agent: counterfactual capability, current position, latest tag and voting weight. */
export function AgentStrip({
  state,
  messages,
  cfAgents,
  activation,
}: {
  state: BoardState;
  messages: MessageRecord[];
  cfAgents: string[];
  activation: { round: number; ranking: Activation[]; selected: string[] } | null;
}) {
  const latest = new Map<string, MessageRecord>();
  for (const m of messages) latest.set(m.agent_id, m);
  const selected = new Set(activation?.selected ?? []);
  return (
    <div className="agent-row" aria-label="Agents">
      {state.agents.map((agent) => {
        const weight = state.weights[agent] ?? 1;
        const position = state.positions[agent];
        const last = latest.get(agent);
        const revised = position?.source.startsWith("revision");
        return (
          <div key={agent} className={`agent-card${selected.has(agent) ? " active" : ""}`}>
            <div className="name">
              {agent}
              {cfAgents.includes(agent) && <span className="cf-badge" title="Counterfactual-capable">CF</span>}
            </div>
            <div className={`weight${weight < 1 ? " changed" : ""}`} title="Voting weight">
              <span className="bar"><i style={{ width: `${Math.min(1, weight) * 100}%` }} /></span>
              {weight.toFixed(2)}
            </div>
            <div className="pos">
              {position ? <span className="mono" title={position.prediction}>{position.prediction}</span> : <span>no position yet</span>}
              {last && <TagLabel tag={last.tag} />}
              {revised && <span className="muted">revised by the sandbox</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** The priority arbiter's latest ranking: who acts next, and why. */
export function ActivationQueue({
  activation,
}: {
  activation: { round: number; ranking: Activation[]; selected: string[] } | null;
}) {
  const selected = new Set(activation?.selected ?? []);
  return (
    <section className="panel">
      <header>
        <h2>Scheduler</h2>
        <span className="hint">{activation ? `priority ranking, round ${activation.round}` : "no round yet"}</span>
      </header>
      <div className="panel-body">
        {activation ? (
          <ol className="queue" aria-label="Activation queue">
            {activation.ranking.map((a) => (
              <li key={a.agent_id} className={selected.has(a.agent_id) ? "selected" : ""} title={a.reasons.join("\n")}>
                <span>{a.agent_id}</span>
                <span className="mono">{a.eligible ? a.score.toFixed(1) : "–"}</span>
                <span>{a.reasons[0] ?? ""}</span>
              </li>
            ))}
          </ol>
        ) : (
          <div className="muted">The arbiter ranks the agents before every round.</div>
        )}
      </div>
    </section>
  );
}
