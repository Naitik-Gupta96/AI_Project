import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Analytics } from "./components/Analytics";
import { NewSession } from "./components/NewSession";
import { SessionView } from "./components/SessionView";
import type { SessionSummary } from "./types";

type View = "session" | "analytics";

function readHash(): { view: View; session: string | null } {
  const [view, session] = location.hash.replace(/^#\/?/, "").split("/");
  return { view: view === "analytics" ? "analytics" : "session", session: session || null };
}

export function App() {
  const [{ view, session }, setRoute] = useState(readHash);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

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
        <h1>Blackboard <span>· PXP with counterfactual agents</span></h1>
        <nav className="tabs" role="tablist">
          <button className="tab" role="tab" aria-selected={view === "session"} onClick={() => go("session")}>
            Sessions
          </button>
          <button className="tab" role="tab" aria-selected={view === "analytics"} onClick={() => go("analytics")}>
            Analytics
          </button>
        </nav>
        <span className="spacer" />
        {view === "session" && (
          <label className="field" style={{ gridAutoFlow: "column", alignItems: "center", gap: 8 }}>
            Open
            <select value={session ?? ""} onFocus={refresh} onChange={(e) => go("session", e.target.value || null)}
                    style={{ maxWidth: 360 }}>
              <option value="">— new session —</option>
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} · {s.status ?? s.state}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <main>
        {view === "analytics" ? (
          <Analytics />
        ) : (
          <>
            {!session && <NewSession onStarted={(id) => go("session", id)} />}
            {session && <SessionView sessionId={session} />}
          </>
        )}
      </main>
    </div>
  );
}
