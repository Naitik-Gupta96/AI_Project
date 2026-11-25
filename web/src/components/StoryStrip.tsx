import type { StoryStep } from "../board";

/** The session in six steps, from the opening message to the outcome; follows the scrubber. */
export function StoryStrip({ steps }: { steps: StoryStep[] }) {
  return (
    <ol className="story" aria-label="Session progress" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {steps.map((s, i) => (
        <li key={s.key} className="step" data-state={s.state} data-tone={s.tone}>
          <div className="bar" />
          <div className="label">
            <span className="num" aria-hidden="true">{i + 1}</span>
            {s.title}
          </div>
          <div className="detail">{s.detail}</div>
        </li>
      ))}
    </ol>
  );
}
