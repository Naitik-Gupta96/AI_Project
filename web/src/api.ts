import { useEffect, useRef, useState } from "react";
import type {
  BoardEvent,
  Catalog,
  ProviderOption,
  SessionResult,
  SessionSummary,
  StreamMessage,
} from "./types";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  catalog: () => fetch("/api/catalog").then(json<Catalog>),
  providers: () => fetch("/api/providers").then(json<ProviderOption[]>),
  sessions: () => fetch("/api/sessions").then(json<SessionSummary[]>),
  start: (body: Record<string, unknown>) =>
    fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<SessionSummary>),
  control: (id: string, action: "pause" | "resume" | "step" | "stop") =>
    fetch(`/api/sessions/${id}/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    }).then(json<SessionSummary>),
  experiments: () => fetch("/api/experiments").then(json<ExperimentSummary[]>),
  experiment: (name: string) => fetch(`/api/experiments/${name}`).then(json<ExperimentDetail>),
};

export interface CfMessage {
  kind: string;
  data: Record<string, any>;
}

export interface SessionStream {
  events: BoardEvent[];
  cf: CfMessage[];
  result: SessionResult | null;
  ended: boolean;
  error: string | null;
  connected: boolean;
}

/** Subscribe to a session's WebSocket: backlog first, then live messages. */
export function useSessionStream(sessionId: string | null): SessionStream {
  const [stream, setStream] = useState<SessionStream>(emptyStream());
  const buffer = useRef<SessionStream>(emptyStream());

  useEffect(() => {
    buffer.current = emptyStream();
    setStream(emptyStream());
    if (!sessionId) return;
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/ws/sessions/${sessionId}`);
    let frame = 0;
    const flush = () => {
      frame = 0;
      const b = buffer.current;
      setStream({ ...b, events: b.events.slice(), cf: b.cf.slice() });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(flush);
    };
    ws.onopen = () => {
      buffer.current.connected = true;
      schedule();
    };
    ws.onmessage = (msg) => {
      const m = JSON.parse(msg.data) as StreamMessage;
      const b = buffer.current;
      if (m.type === "board") b.events.push(m.event);
      else if (m.type === "cf") b.cf.push({ kind: m.kind, data: m.data });
      else if (m.type === "end") {
        b.result = m.result;
        b.ended = true;
      } else if (m.type === "error") {
        b.error = m.message;
        b.ended = true;
      }
      schedule();
    };
    ws.onclose = () => {
      buffer.current.connected = false;
      schedule();
    };
    return () => {
      if (frame) cancelAnimationFrame(frame);
      ws.close();
    };
  }, [sessionId]);

  return stream;
}

function emptyStream(): SessionStream {
  return { events: [], cf: [], result: null, ended: false, error: null, connected: false };
}

export interface ExperimentSummary {
  name: string;
  provider: string;
  trials: number;
  created: string;
}

export interface GroupRow {
  group: string;
  cf_fraction: number;
  benchmark: string;
  trials: number;
  convergence_success: number;
  convergence_ci: [number, number];
  consensus: number;
  accuracy: number;
  deadlock: number;
  recovered: number;
  ultra_strong: number;
  strong: number;
  one_way: number;
  none: number;
  tokens_mean: number | null;
  tokens_ci: [number, number] | null;
  live_tokens_mean: number | null;
  sandbox_tokens_mean: number | null;
  messages_mean: number;
}

export interface ExperimentDetail {
  name: string;
  meta: Record<string, any>;
  groups: GroupRow[];
  tests: { comparison: string; benchmark: string; b: number; c: number; p_value: number }[];
}
