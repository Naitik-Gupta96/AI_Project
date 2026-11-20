import { useCallback, useEffect, useMemo, useState } from "react";
import { api, useSessionStream } from "../api";
import { foldState, interventions, latestActivation, messages, objectionStreak } from "../board";
import { AgentPanel } from "./AgentPanel";
import { StatusBadge, TagLegend, WarningIcon } from "./Badges";
import { BoardGraph } from "./BoardGraph";
import { CounterfactualPanel } from "./CounterfactualPanel";
import { EventLog } from "./EventLog";
import { ReasoningStream } from "./ReasoningStream";
import { Scrubber } from "./Scrubber";

/** One session: live while it runs, and inspectable event by event at any time. */
export function SessionView({ sessionId }: { sessionId: string }) {
  const stream = useSessionStream(sessionId);
  const [follow, setFollow] = useState(true);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    setFollow(true);
    setSelected(null);
    setPlaying(false);
  }, [sessionId]);

  const total = stream.events.length;
  const at = follow ? total : Math.min(cursor, total);
  const state = useMemo(() => foldState(stream.events, at), [stream.events, at]);
  const msgs = useMemo(() => messages(stream.events, at), [stream.events, at]);
  const allMsgs = useMemo(() => messages(stream.events), [stream.events]);
  const shownEvents = useMemo(() => stream.events.slice(0, at), [stream.events, at]);
  const cfDone = useMemo(() => interventions(stream.events, at), [stream.events, at]);
  const activation = useMemo(() => latestActivation(stream.events, at), [stream.events, at]);

  const streak = objectionStreak(msgs);
  const alertIds = useMemo(
    () => new Set(streak >= 2 ? msgs.slice(-streak).map((m) => m.message_id) : []),
    [msgs, streak],
  );
  const cfAgents = (state.metadata?.cf_agents as string[] | undefined) ?? [];

  const moveCursor = useCallback((v: number) => {
    setFollow(false);
    setCursor(v);
  }, []);
  const followLive = useCallback(() => {
    setFollow(true);
    setPlaying(false);
  }, []);
  const startPlaying = useCallback((p: boolean) => {
    if (p && at >= total) {
      setFollow(false);
      setCursor(0);
    }
    setPlaying(p);
  }, [at, total]);

  async function control(action: "pause" | "resume" | "step" | "stop") {
    const s = await api.control(sessionId, action);
    setPaused(Boolean(s.paused));
  }

  const result = stream.result;
  const running = !stream.ended;

  return (
    <>
      <section className="panel">
        <div className="panel-body" style={{ display: "grid", gap: 10 }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
            <StatusBadge status={state.status} />
            <span className="mono" style={{ color: "var(--muted)" }}>{sessionId}</span>
            <span style={{ color: "var(--ink-2)", flex: "1 1 320px" }}>{state.task}</span>
            {running && (
              <span style={{ display: "flex", gap: 6 }}>
                {paused
                  ? <button className="btn" onClick={() => control("resume")}>Resume</button>
                  : <button className="btn" onClick={() => control("pause")}>Pause</button>}
                <button className="btn" onClick={() => control("step")} disabled={!paused}>Step round</button>
                <button className="btn" onClick={() => control("stop")}>Stop</button>
              </span>
            )}
          </div>
          <Scrubber events={stream.events} cursor={at} follow={follow} playing={playing}
                    onCursor={moveCursor} onFollow={followLive} onPlaying={startPlaying} />
          {streak >= 2 && (
            <div className="alert" role="status">
              <WarningIcon />
              Objection cascade: the last {streak} messages are REFUTE or REJECT.
            </div>
          )}
          {stream.error && <div className="alert" role="alert"><WarningIcon />Session crashed: {stream.error}</div>}
          {result && follow && <Outcome result={result} />}
        </div>
      </section>

      <div className="session-grid">
        <section className="panel area-graph">
          <header>
            <h2>Reasoning graph</h2>
            <span className="hint">task at the centre · each message branches from the one it answered</span>
          </header>
          <BoardGraph agents={state.agents} messages={msgs} question={state.task} alertIds={alertIds}
                      selected={selected} onSelect={setSelected} />
          <TagLegend />
        </section>
        <div className="area-side">
          <AgentPanel state={state} messages={msgs} cfAgents={cfAgents} activation={activation} />
          <EventLog events={shownEvents} selected={selected} follow={follow} onSelect={setSelected} />
        </div>
        <div className="area-stream">
          <ReasoningStream agents={state.agents} messages={msgs} interventions={cfDone}
                           selected={selected} onSelect={setSelected} />
        </div>
        <div className="area-cf">
          <CounterfactualPanel interventions={cfDone} cf={follow ? stream.cf : []}
                               liveMessages={allMsgs} cfAgents={cfAgents} />
        </div>
      </div>
    </>
  );
}

function Outcome({ result }: { result: NonNullable<ReturnType<typeof useSessionStream>["result"]> }) {
  const usage = result.usage.total;
  return (
    <dl className="kv">
      <dt>Answer</dt>
      <dd>
        <span className="mono">{result.final_prediction ?? "none"}</span>
        {result.score && <> · {result.score.correct ? "correct" : "not correct"} (score {result.score.value.toFixed(2)})</>}
      </dd>
      <dt>Intelligibility</dt>
      <dd>
        {result.intelligibility.session} (whole session)
        {result.intelligibility_after_intervention &&
          ` · ${result.intelligibility_after_intervention.session} after the intervention`}
      </dd>
      <dt>Cost</dt>
      <dd>
        {result.messages} messages · {usage.calls} provider calls
        {usage.reported ? ` · ${usage.prompt_tokens + usage.completion_tokens} tokens` : " · no token counts (mock)"}
      </dd>
    </dl>
  );
}
