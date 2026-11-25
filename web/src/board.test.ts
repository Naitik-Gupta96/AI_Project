import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/session.json";
import {
  activationHistory,
  epochStart,
  foldState,
  interventions,
  messages,
  objectionStreak,
  reasoningGraph,
  storySteps,
} from "./board";
import type { BoardEvent, BoardState } from "./types";

const events = fixture.events as BoardEvent[];
const states = fixture.states as unknown as BoardState[];

describe("applyEvent mirrors the Python board", () => {
  it("matches the Python state after every event", () => {
    for (let v = 0; v < states.length; v++) {
      expect(foldState(events, v)).toEqual(states[v]);
    }
  });
});

describe("derived views", () => {
  it("lists messages in order", () => {
    const msgs = messages(events);
    expect(msgs.map((m) => m.iteration)).toEqual(msgs.map((_, i) => i + 1));
    expect(msgs[0].tag).toBe("INIT");
  });

  it("builds a reasoning tree rooted at the task", () => {
    const { nodes, links } = reasoningGraph(messages(events));
    expect(nodes[0].kind).toBe("root");
    expect(links).toHaveLength(nodes.length - 1);
    const ids = new Set(nodes.map((n) => n.id));
    for (const l of links) expect(ids.has(l.source) && ids.has(l.target)).toBe(true);
    expect(nodes.find((n) => n.message?.iteration === 1)?.depth).toBe(1);
  });

  it("finds the applied intervention and the epoch it starts", () => {
    const [intervention] = interventions(events);
    expect(intervention.applied).toBe(true);
    expect(intervention.agent_id).toBe("analyst");
    expect(epochStart(events)).toBe(intervention.at_iteration);
  });

  it("pairs every activation round with the tag that was posted", () => {
    const rounds = activationHistory(events);
    expect(rounds.length).toBe(messages(events).length);
    expect(rounds.every((r) => r.selected.includes(r.agent ?? ""))).toBe(true);
  });

  it("tells the session as a story that follows the scrubber", () => {
    const opts = { cfAgents: ["analyst"], sandboxRunning: false, finished: true };
    const end = storySteps(events, events.length, opts);
    expect(end.map((s) => s.key)).toEqual(["opening", "discussion", "deadlock", "sandbox", "fix", "outcome"]);
    expect(end.every((s) => s.state === "done")).toBe(true);
    expect(end.find((s) => s.key === "deadlock")?.tone).toBe("critical");
    expect(end.find((s) => s.key === "fix")?.detail).toContain("analyst");
    expect(end.find((s) => s.key === "outcome")?.tone).toBe("good");

    const atDeadlock = events.findIndex((e) => e.kind === "status" && e.data.status === "DEADLOCK") + 1;
    const mid = storySteps(events, atDeadlock, { ...opts, finished: false });
    expect(mid.find((s) => s.key === "deadlock")?.state).toBe("done");
    expect(mid.find((s) => s.key === "fix")?.state).toBe("pending");
    expect(mid.find((s) => s.key === "outcome")?.state).toBe("pending");

    const noCf = storySteps(events, atDeadlock, { cfAgents: [], sandboxRunning: false, finished: false });
    expect(noCf.find((s) => s.key === "sandbox")?.state).toBe("skipped");
  });

  it("measures the objection streak at the end of the log", () => {
    const msgs = messages(events);
    const atDeadlock = msgs.findIndex((m) => m.tag === "REJECT") + 1;
    expect(objectionStreak(msgs.slice(0, atDeadlock))).toBe(1);
    expect(objectionStreak(msgs)).toBe(0);
  });
});
