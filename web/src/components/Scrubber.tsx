import { useEffect } from "react";
import type { BoardEvent } from "../types";

/**
 * Step through the session's event log. At the head it follows the live session; moving back
 * freezes every view at that version. Arrow keys step one event; Home/End jump.
 */
export function Scrubber({
  events,
  cursor,
  follow,
  playing,
  onCursor,
  onFollow,
  onPlaying,
}: {
  events: BoardEvent[];
  cursor: number;
  follow: boolean;
  playing: boolean;
  onCursor: (v: number) => void;
  onFollow: () => void;
  onPlaying: (p: boolean) => void;
}) {
  const max = events.length;
  const at = events[cursor - 1];

  useEffect(() => {
    if (!playing) return;
    if (cursor >= max) {
      onPlaying(false);
      return;
    }
    const timer = setTimeout(() => onCursor(nextMessage(events, cursor)), 450);
    return () => clearTimeout(timer);
  }, [playing, cursor, max, events, onCursor, onPlaying]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "INPUT" && (e.target as HTMLInputElement).type !== "range") return;
      if (e.key === "ArrowLeft") onCursor(Math.max(0, cursor - 1));
      else if (e.key === "ArrowRight") onCursor(Math.min(max, cursor + 1));
      else if (e.key === "Home") onCursor(0);
      else if (e.key === "End") onFollow();
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cursor, max, onCursor, onFollow]);

  return (
    <div className="scrubber">
      <button className="btn" onClick={() => onCursor(prevMessage(events, cursor))} disabled={cursor <= 1}
              title="Previous message">◀ msg</button>
      <button className="btn" onClick={() => onCursor(Math.max(0, cursor - 1))} disabled={cursor <= 0}
              title="Previous event (←)">◀</button>
      <input type="range" min={0} max={max} value={cursor} aria-label="Event position"
             onChange={(e) => onCursor(Number(e.target.value))} />
      <button className="btn" onClick={() => onCursor(Math.min(max, cursor + 1))} disabled={cursor >= max}
              title="Next event (→)">▶</button>
      <button className="btn" onClick={() => onCursor(nextMessage(events, cursor))} disabled={cursor >= max}
              title="Next message">msg ▶</button>
      <button className="btn" onClick={() => onPlaying(!playing)} disabled={cursor >= max && !playing}>
        {playing ? "Pause replay" : "Replay"}
      </button>
      <button className="btn" onClick={onFollow} disabled={follow}>Follow live</button>
      <span className="pos">
        event {cursor}/{max}
        {at ? ` · ${at.kind}${at.kind === "message" ? ` #${at.data.message.iteration}` : ""}` : ""}
      </span>
    </div>
  );
}

function nextMessage(events: BoardEvent[], cursor: number): number {
  for (let i = cursor; i < events.length; i++) if (events[i].kind === "message") return i + 1;
  return events.length;
}

function prevMessage(events: BoardEvent[], cursor: number): number {
  for (let i = cursor - 2; i >= 0; i--) if (events[i].kind === "message") return i + 1;
  return 0;
}
