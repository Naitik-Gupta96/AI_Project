import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Analytics } from "./components/Analytics";
import { NewSession } from "./components/NewSession";
import { SessionView } from "./components/SessionView";
import type { SessionSummary } from "./types";

type View = "session" | "analytics";
type Theme = "light" | "dark";

function readHash(): { view: View; session: string | null } {
  const [view, session] = location.hash.replace(/^#\/?/, "").split("/");
  return { view: view === "analytics" ? "analytics" : "session", session: session || null };
}

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // storage can be unavailable (private windows); fall back to the system setting
  }
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function App() {
  const [{ view, session }, setRoute] = useState(readHash);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("theme", theme);
    } catch {
      // not persisted; the toggle still works for this visit
    }
  }, [theme]);

  const refresh = useCallback(() => {
    api.sessions().then(setSessions).catch(() => setSessions([]));
  }, []);
  useEffect(refresh, [refresh, session]);

  const go = (v: View, s: string | null = session) => {
    location.hash = s && v === "session" ? `/session/${s}` : `/${v}`;
  };

  return (
    <div className="shell">
      <div className="topbar">
        <div className="brand">
          <Mark />
          <h1>Blackboard</h1>
          <span>PXP agents with counterfactual replay</span>
        </div>
        <nav className="tabs" role="tablist">
          <button className="tab" role="tab" aria-selected={view === "session"} onClick={() => go("session")}>
            Sessions
          </button>
          <button className="tab" role="tab" aria-selected={view === "analytics"} onClick={() => go("analytics")}>
            Analytics
          </button>
        </nav>
        <span className="spacer" />
        {view === "session" && sessions.length > 0 && (
          <select aria-label="Open a session" value={session ?? ""} onFocus={refresh}
                  onChange={(e) => go("session", e.target.value || null)} style={{ maxWidth: 300 }}>
            <option value="">New session</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} · {(s.status ?? s.state).toString().toLowerCase()}
              </option>
            ))}
          </select>
        )}
        <button className="btn ghost" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
      </div>
      <main>
        {view === "analytics" ? (
          <Analytics />
        ) : session ? (
          <SessionView sessionId={session} onNew={() => go("session", null)} />
        ) : (
          <NewSession onStarted={(id) => go("session", id)} />
        )}
      </main>
    </div>
  );
}

/** Three agents around a shared board. */
function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <circle cx="11" cy="11" r="4.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="11" cy="2.8" r="2.2" fill="var(--tag-revise)" />
      <circle cx="18.1" cy="15.1" r="2.2" fill="var(--tag-ratify)" />
      <circle cx="3.9" cy="15.1" r="2.2" fill="var(--tag-objection)" />
    </svg>
  );
}
