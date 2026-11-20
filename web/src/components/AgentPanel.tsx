import type { Activation, BoardState, MessageRecord } from "../types";
import { TagLabel } from "./Badges";

/** Each agent's weight, position and latest tag, plus the arbiter's current ranking. */
export function AgentPanel({
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
    <section className="panel">
      <header>
        <h2>Agents</h2>
        <span className="hint">weight · position · latest tag</span>
      </header>
      <div className="panel-body agents">
        {state.agents.map((agent) => {
          const weight = state.weights[agent] ?? 1;
          const position = state.positions[agent];
          const last = latest.get(agent);
          return (
            <div key={agent} className={`agent${selected.has(agent) ? " active" : ""}`}>
              <div>
                <span className="name">{agent}</span>
                {cfAgents.includes(agent) && <span className="cf" title="Counterfactual-capable">CF</span>}
              </div>
              <div className="weight" title="Voting weight">
                <span className="bar"><i style={{ width: `${Math.min(1, weight) * 100}%` }} /></span>
                {weight.toFixed(2)}
              </div>
              <div className="pos">
                {position ? (
                  <>
                    <span className="mono">{position.prediction}</span>
                    {position.source.startsWith("revision") && " (revised by intervention)"}
                  </>
                ) : (
                  "no position yet"
                )}
                {last && (
                  <span style={{ marginLeft: 8 }}>
                    <TagLabel tag={last.tag} />
                  </span>
                )}
              </div>
            </div>
          );
        })}
        {activation && (
          <div className="queue" aria-label="Activation queue">
            <h2 style={{ marginTop: 6 }}>Activation queue · round {activation.round}</h2>
            <ol>
              {activation.ranking.map((a) => (
                <li key={a.agent_id} className={selected.has(a.agent_id) ? "selected" : ""}
                    title={a.reasons.join("\n")}>
                  <span>{a.agent_id}</span>
                  <span className="mono">{a.eligible ? a.score.toFixed(1) : "—"}</span>
                  <span>{a.reasons[0] ?? ""}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </section>
  );
}
