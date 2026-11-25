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

export type StepState = "done" | "current" | "pending" | "skipped";
export type StepTone = "neutral" | "critical" | "good";

export interface StoryStep {
  key: "opening" | "discussion" | "deadlock" | "sandbox" | "fix" | "outcome";
  title: string;
  state: StepState;
  tone: StepTone;
  detail: string;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/**
 * The session as a short story, for the strip above the graph: opening message, discussion,
 * deadlock, sandbox replay, the fix applied to the live board, and the outcome. Built from the
 * events up to `upto`, so it follows the scrubber. `sandboxRunning` is true while counterfactual
 * branches are still streaming; `finished` means the view is at the end of a finished session.
 */
export function storySteps(
  events: BoardEvent[],
  upto: number,
  opts: { cfAgents: string[]; sandboxRunning: boolean; finished: boolean },
): StoryStep[] {
  const shown = events.slice(0, upto);
  const msgs = messages(shown);
  const deadlocks = shown.filter((e) => e.kind === "status" && e.data.status === "DEADLOCK");
  const ivs = interventions(shown);
  const applied = ivs.find((i) => i.applied) ?? null;
  const lastStatus = [...shown].reverse().find((e) => e.kind === "status")?.data.status as string | undefined;
  const consensus = lastStatus === "CONSENSUS";
  const stuck = opts.finished && lastStatus === "DEADLOCK";
  const settled = consensus || stuck;

  const first = msgs[0];
  const opening: StoryStep = first
    ? { key: "opening", title: "Opening", state: "done", tone: "neutral",
        detail: `${first.agent_id} proposes ${first.prediction}` }
    : { key: "opening", title: "Opening", state: "current", tone: "neutral", detail: "waiting for the first message" };

  const replies = msgs.slice(1);
  const objections = replies.filter((m) => m.tag === "REFUTE" || m.tag === "REJECT").length;
  const agreements = replies.filter((m) => m.tag === "RATIFY").length;
  const revisions = replies.filter((m) => m.tag === "REVISE").length;
  const counts = [
    objections && plural(objections, "objection"),
    agreements && plural(agreements, "agreement"),
    revisions && plural(revisions, "revision"),
  ].filter(Boolean).join(" · ");
  const discussion: StoryStep = {
    key: "discussion", title: "Discussion", tone: "neutral",
    state: !replies.length ? (first ? "current" : "pending") : deadlocks.length || settled ? "done" : "current",
    detail: replies.length ? counts : "agents reply with PXP tags",
  };

  const firstDeadlock = deadlocks[0];
  const deadlock: StoryStep = firstDeadlock
    ? { key: "deadlock", title: "Deadlock", state: "done", tone: "critical",
        detail: String(firstDeadlock.data.reason ?? "the board is stuck").split(":")[0] }
    : { key: "deadlock", title: "Deadlock", tone: "neutral", state: settled ? "skipped" : "pending",
        detail: settled ? "not reached" : "REJECT, a REFUTE loop, or no progress" };

  let sandbox: StoryStep;
  if (ivs.length) {
    const branches = ivs.reduce((n, i) => n + i.branches.length, 0);
    sandbox = { key: "sandbox", title: "Sandbox replay", state: "done", tone: "neutral",
                detail: `${plural(branches, "alternative")} replayed` };
  } else if (firstDeadlock && opts.sandboxRunning) {
    sandbox = { key: "sandbox", title: "Sandbox replay", state: "current", tone: "neutral",
                detail: "replaying alternatives to past messages" };
  } else if (firstDeadlock && !opts.cfAgents.length) {
    sandbox = { key: "sandbox", title: "Sandbox replay", state: "skipped", tone: "neutral",
                detail: "no counterfactual-capable agent" };
  } else {
    sandbox = { key: "sandbox", title: "Sandbox replay", tone: "neutral",
                state: settled && !firstDeadlock ? "skipped" : "pending",
                detail: opts.cfAgents.length ? `${opts.cfAgents.join(", ")} can replay` : "no counterfactual-capable agent" };
  }

  let fix: StoryStep;
  if (applied) {
    const chosen = applied.branches.find((b) => b.branch_id === applied.chosen_branch);
    const change = chosen ? ` #${chosen.target.iteration} → ${chosen.candidate.prediction}` : "";
    fix = { key: "fix", title: "Fix applied", state: "done", tone: "neutral",
            detail: `${applied.agent_id}${change}, credit +${applied.credit.toFixed(2)}` };
  } else if (ivs.length) {
    fix = { key: "fix", title: "Fix applied", state: "done", tone: "critical",
            detail: "no alternative raised consensus" };
  } else {
    fix = { key: "fix", title: "Fix applied", tone: "neutral",
            state: sandbox.state === "skipped" ? "skipped" : "pending", detail: "lesson, position and weight" };
  }

  const answer = msgs[msgs.length - 1]?.prediction;
  const outcome: StoryStep = consensus
    ? { key: "outcome", title: "Consensus", state: "done", tone: "good", detail: `agreed on ${answer}` }
    : stuck
      ? { key: "outcome", title: "Still deadlocked", state: "done", tone: "critical", detail: "the session ended stuck" }
      : { key: "outcome", title: "Outcome", state: "pending", tone: "neutral", detail: "consensus or deadlock" };

  return [opening, discussion, deadlock, sandbox, fix, outcome];
}

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
