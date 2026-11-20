// Client-side view of a session, derived from its event log.
// `applyEvent` mirrors `apply_event` in src/ai_project/blackboard/models.py; board.test.ts checks
// it against states the Python board produced (src/__fixtures__/session.json).

import type {
  Activation,
  BoardEvent,
  BoardState,
  Intervention,
  MessageRecord,
  Tag,
} from "./types";

export function emptyState(): BoardState {
  return {
    task: "",
    status: "INITIALIZED",
    version: 0,
    iteration: 0,
    agents: [],
    weights: {},
    positions: {},
    latest_message: null,
    metadata: {},
  };
}

export function applyEvent(state: BoardState, event: BoardEvent): BoardState {
  const next: BoardState = { ...state, weights: { ...state.weights }, positions: { ...state.positions } };
  const d = event.data;
  switch (event.kind) {
    case "task":
      next.task = d.task;
      next.metadata = d.metadata ?? {};
      next.agents = d.agents ?? [];
      next.weights = Object.fromEntries(
        Object.entries((d.weights ?? {}) as Record<string, number>).map(([a, w]) => [a, Number(w)]),
      );
      for (const a of next.agents) if (!(a in next.weights)) next.weights[a] = 1.0;
      break;
    case "message": {
      const m = d.message as MessageRecord;
      next.iteration = m.iteration;
      next.latest_message = m;
      next.positions[m.agent_id] = { prediction: m.prediction, explanation: m.explanation, source: m.message_id };
      if (!(m.agent_id in next.weights)) next.weights[m.agent_id] = 1.0;
      if (next.status === "INITIALIZED") next.status = "RUNNING";
      break;
    }
    case "status":
      next.status = d.status;
      break;
    case "weight":
      next.weights[d.agent_id] = Number(d.weight);
      break;
    case "context_revision":
      next.positions[d.agent_id] = {
        prediction: d.prediction,
        explanation: d.explanation,
        source: `revision@${event.seq}`,
      };
      break;
    default:
      break; // record-only kinds
  }
  next.version = event.seq;
  return next;
}

export function foldState(events: BoardEvent[], upto = events.length): BoardState {
  let state = emptyState();
  for (const event of events.slice(0, upto)) state = applyEvent(state, event);
  return state;
}

export function messages(events: BoardEvent[], upto = events.length): MessageRecord[] {
  return events
    .slice(0, upto)
    .filter((e) => e.kind === "message")
    .map((e) => e.data.message as MessageRecord);
}

export function interventions(events: BoardEvent[], upto = events.length): Intervention[] {
  return events
    .slice(0, upto)
    .filter((e) => e.kind === "intervention")
    .map((e) => e.data as Intervention);
}

/**
 * The ranking recorded in the latest activation event, and who was selected. ``round`` counts
 * activations over the whole session (the scheduler restarts its own count after an intervention).
 */
export function latestActivation(
  events: BoardEvent[],
  upto = events.length,
): { round: number; ranking: Activation[]; selected: string[] } | null {
  const activations = events.slice(0, upto).filter((e) => e.kind === "activation");
  const last = activations[activations.length - 1];
  if (!last) return null;
  return { round: activations.length, ranking: last.data.ranking, selected: last.data.selected };
}

/** Per round: the agents selected and, once committed, the tag each posted. */
export function activationHistory(events: BoardEvent[], upto = events.length) {
  const rounds: { round: number; selected: string[]; tag: Tag | null; agent: string | null }[] = [];
  for (const e of events.slice(0, upto)) {
    if (e.kind === "activation") {
      rounds.push({ round: e.data.round, selected: e.data.selected, tag: null, agent: null });
    } else if (e.kind === "message" && rounds.length) {
      const last = rounds[rounds.length - 1];
      if (last.tag === null) {
        last.tag = e.data.message.tag;
        last.agent = e.data.message.agent_id;
      }
    }
  }
  return rounds;
}

/** Length of the run of REFUTE/REJECT messages at the end of the log. */
export function objectionStreak(msgs: MessageRecord[]): number {
  let n = 0;
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].tag === "REFUTE" || msgs[i].tag === "REJECT") n++;
    else break;
  }
  return n;
}

export interface GraphNode {
  id: string;
  kind: "root" | "message";
  depth: number;
  message?: MessageRecord;
}

export interface GraphLink {
  source: string;
  target: string;
  tag: Tag;
}

/**
 * The reasoning graph: the task is the root; every message hangs off the message it answered
 * (`in_reply_to`), and message 1 hangs off the root. Depth is the distance from the root.
 */
export function reasoningGraph(msgs: MessageRecord[]): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes: GraphNode[] = [{ id: "root", kind: "root", depth: 0 }];
  const links: GraphLink[] = [];
  const depth = new Map<string, number>([["root", 0]]);
  for (const m of msgs) {
    const parent = m.in_reply_to && depth.has(m.in_reply_to) ? m.in_reply_to : "root";
    const d = (depth.get(parent) ?? 0) + 1;
    depth.set(m.message_id, d);
    nodes.push({ id: m.message_id, kind: "message", depth: d, message: m });
    links.push({ source: parent, target: m.message_id, tag: m.tag });
  }
  return { nodes, links };
}

export const TAGS: Tag[] = ["INIT", "RATIFY", "REVISE", "REFUTE", "REJECT"];

/** Message number at the last applied intervention (0 if none), as in scheduler.epoch_start. */
export function epochStart(events: BoardEvent[], upto = events.length): number {
  let iteration = 0;
  let start = 0;
  for (const e of events.slice(0, upto)) {
    if (e.kind === "message") iteration = e.data.message.iteration;
    else if (e.kind === "intervention" && e.data.applied) start = iteration;
  }
  return start;
}
