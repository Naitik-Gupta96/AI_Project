import { useCallback, useEffect, useMemo, useState } from "react";
import { api, useSessionStream } from "../api";
import { foldState, interventions, latestActivation, messages, objectionStreak, storySteps } from "../board";
import { ActivationQueue, AgentStrip } from "./AgentPanel";
import { StatusBadge, TagLegend, WarningIcon } from "./Badges";
import { BoardGraph } from "./BoardGraph";
import { CounterfactualPanel, sandboxRunning } from "./CounterfactualPanel";
import { EventLog } from "./EventLog";
import { ReasoningStream } from "./ReasoningStream";
import { Scrubber } from "./Scrubber";
import { StoryStrip } from "./StoryStrip";

/** One session: live while it runs, and inspectable event by event at any time. */
export function SessionView({ sessionId, onNew }: { sessionId: string; onNew: () => void }) {
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
  const cfAgents = useMemo(() => (state.metadata?.cf_agents as string[] | undefined) ?? [], [state.metadata]);
  const steps = useMemo(
    () => storySteps(stream.events, at, {
      cfAgents,
      sandboxRunning: follow && sandboxRunning(stream.cf),
      finished: stream.ended && at >= total,
    }),
    [stream.events, stream.cf, stream.ended, at, total, follow, cfAgents],
  );

  const streak = objectionStreak(msgs);
  const alertIds = useMemo(
    () => new Set(streak >= 2 ? msgs.slice(-streak).map((m) => m.message_id) : []),
    [msgs, streak],
  );

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
      <div className="session-head">
        <div className="title">
          <div className="question">{state.task || "Connecting…"}</div>
          <div className="sub">
            <StatusBadge status={state.status} />
            <span>{msgs.length} message{msgs.length === 1 ? "" : "s"}</span>
            {result && follow && <Outcome result={result} />}
            <span className="mono">{sessionId}</span>
          </div>
        </div>
        <div className="controls">
          {running && (
            <>
              {paused
                ? <button className="btn" onClick={() => control("resume")}>Resume</button>
                : <button className="btn" onClick={() => control("pause")}>Pause</button>}
              <button className="btn" onClick={() => control("step")} disabled={!paused}>Step round</button>
              <button className="btn" onClick={() => control("stop")}>Stop</button>
            </>
          )}
          <button className="btn" onClick={onNew}>New session</button>
        </div>
      </div>

      <StoryStrip steps={steps} />

      {streak >= 2 && (
        <div className="alert" role="status">
          <WarningIcon />
          Objection cascade: the last {streak} messages are REFUTE or REJECT.
        </div>
      )}
      {stream.error && <div className="alert" role="alert"><WarningIcon />Session crashed: {stream.error}</div>}

      <AgentStrip state={state} messages={msgs} cfAgents={cfAgents} activation={activation} />

      <div className="stage">
        <section className="panel">
          <header>
            <h2>Reasoning graph</h2>
            <span className="hint">the task at the centre; each message branches from the one it answered</span>
          </header>
          <BoardGraph agents={state.agents} messages={msgs} question={state.task} alertIds={alertIds}
                      selected={selected} onSelect={setSelected} cfAgents={cfAgents} weights={state.weights} />
          <div style={{ padding: "0 18px 12px" }}><TagLegend /></div>
          <Scrubber events={stream.events} cursor={at} follow={follow} playing={playing}
                    onCursor={moveCursor} onFollow={followLive} onPlaying={startPlaying} />
        </section>
        <CounterfactualPanel interventions={cfDone} cf={follow ? stream.cf : []}
                             liveMessages={allMsgs} cfAgents={cfAgents} />
      </div>

      <div className="details">
        <div style={{ display: "grid", gap: 20, alignContent: "start" }}>
          <ReasoningStream agents={state.agents} messages={msgs} interventions={cfDone}
                           selected={selected} onSelect={setSelected} />
          <ActivationQueue activation={activation} />
        </div>
        <EventLog events={shownEvents} selected={selected} follow={follow} onSelect={setSelected} />
      </div>
    </>
  );
}

function Outcome({ result }: { result: NonNullable<ReturnType<typeof useSessionStream>["result"]> }) {
  const usage = result.usage.total;
  const after = result.intelligibility_after_intervention?.session;
  return (
    <>
      <span>
        answer <span className="mono" style={{ color: "var(--ink)" }}>{result.final_prediction ?? "none"}</span>
        {result.score && <> ({result.score.correct ? "correct" : "not correct"})</>}
      </span>
      <span>
        intelligibility {result.intelligibility.session}{after ? `, ${after} after the fix` : ""}
      </span>
      <span>
        {usage.calls} model calls{usage.reported ? ` · ${(usage.prompt_tokens + usage.completion_tokens).toLocaleString()} tokens` : ""}
      </span>
    </>
  );
}
