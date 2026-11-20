import type { Status, Tag } from "../types";

export function TagLabel({ tag }: { tag: Tag | string }) {
  return (
    <span className="tag" data-tag={tag}>
      {tag}
    </span>
  );
}

const STATUS_TEXT: Record<Status, string> = {
  INITIALIZED: "Initialized",
  RUNNING: "Running",
  CONSENSUS: "Consensus",
  DEADLOCK: "Deadlock",
  FAILED: "Failed",
};

export function StatusBadge({ status }: { status: Status | null }) {
  if (!status) return null;
  return (
    <span className="status" data-status={status}>
      <StatusIcon status={status} />
      {STATUS_TEXT[status]}
    </span>
  );
}

function StatusIcon({ status }: { status: Status }) {
  const common = { width: 14, height: 14, viewBox: "0 0 16 16", "aria-hidden": true } as const;
  if (status === "CONSENSUS") {
    return (
      <svg {...common}>
        <circle cx="8" cy="8" r="7" fill="currentColor" />
        <path d="M4.5 8.2l2.2 2.2 4.8-4.8" stroke="var(--surface)" strokeWidth="1.8" fill="none" />
      </svg>
    );
  }
  if (status === "DEADLOCK" || status === "FAILED") {
    return (
      <svg {...common}>
        <circle cx="8" cy="8" r="7" fill="currentColor" />
        <path d="M5.2 5.2l5.6 5.6M10.8 5.2l-5.6 5.6" stroke="var(--surface)" strokeWidth="1.8" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="8" cy="8" r="2.2" fill="currentColor" />
    </svg>
  );
}

export function WarningIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 1.5l7 12.5H1z" fill="currentColor" />
      <path d="M8 6v4" stroke="var(--surface)" strokeWidth="1.6" />
      <circle cx="8" cy="12" r="0.9" fill="var(--surface)" />
    </svg>
  );
}

/** Stroke and fill for a tag's mark in SVG (REFUTE is hollow, REJECT solid). */
export function tagPaint(tag: string): { stroke: string; fill: string } {
  switch (tag) {
    case "RATIFY":
      return { stroke: "var(--tag-ratify)", fill: "var(--tag-ratify)" };
    case "REVISE":
      return { stroke: "var(--tag-revise)", fill: "var(--tag-revise)" };
    case "REFUTE":
      return { stroke: "var(--tag-objection)", fill: "var(--surface)" };
    case "REJECT":
      return { stroke: "var(--tag-objection)", fill: "var(--tag-objection)" };
    default:
      return { stroke: "var(--tag-init)", fill: "var(--tag-init)" };
  }
}

export function TagLegend() {
  return (
    <div className="legend" aria-label="Tag legend">
      {["INIT", "RATIFY", "REVISE", "REFUTE", "REJECT"].map((t) => (
        <TagLabel key={t} tag={t} />
      ))}
    </div>
  );
}
