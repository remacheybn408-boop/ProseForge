import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAgentRun, getAgentRunAudit, listAgentArtifacts, listAgentEvents, listAgentReviews, type AgentRun, type AgentRunEvent, type AgentTask } from "../../lib/api/client";
import { AgentGraphView } from "./AgentGraphView";
import { AgentRunControls } from "./AgentRunControls";
import { AgentTaskTable } from "./AgentTaskTable";
import { ArtifactPanel } from "./ArtifactPanel";
import { ReviewConflictPanel } from "./ReviewConflictPanel";
import { agentEventCursor, agentRunKeys, isActiveAgentRun, isTerminalAgentRun, mergeAgentEvents } from "./agentQueries";

export const AGENT_RUN_POLL_INTERVAL_MS = 2000;

export type AgentRunAction = "pause" | "resume" | "cancel" | "retry";

// Status is dual-encoded: the stamp text is paired with a distinct seal shape per
// state (circle = running, double border = paused, filled = done, tilted outline =
// failed/cancelled/budget-exhausted, plain outline = pending).
function runStampClass(status: string) {
  const normalized = status.toUpperCase();
  if (normalized === "RUNNING") return "run-stamp run-stamp-active";
  if (normalized === "PAUSED") return "run-stamp run-stamp-paused";
  if (normalized === "COMPLETED") return "run-stamp run-stamp-done";
  if (isTerminalAgentRun(normalized)) return "run-stamp run-stamp-failed";
  return "run-stamp";
}

function formatCursor(cursor: number) {
  return "#" + String(cursor).padStart(4, "0");
}

export function AgentRunPage({ run, tasks = [], onAction = () => undefined, onRetryTask, onSelectConflict, pollIntervalMs = AGENT_RUN_POLL_INTERVAL_MS }: {
  run: AgentRun;
  tasks?: AgentTask[];
  onAction?: (action: AgentRunAction) => void;
  onRetryTask?: (taskId: string) => void;
  onSelectConflict?: (reviewId: string) => void;
  pollIntervalMs?: number;
}) {
  const [liveRun, setLiveRun] = useState(run);
  const [events, setEvents] = useState<AgentRunEvent[]>([]);
  const [view, setView] = useState<"graph" | "table">("table");
  const cursorRef = useRef(0);

  // The parent refreshes the run after each control action; mirror it locally so
  // the ledger header follows without waiting for the next poll tick.
  useEffect(() => { setLiveRun(run); }, [run]);

  // Seed the ledger from the durable audit replay, then tail `events?after=` from
  // that cursor — a reopened page backfills everything it missed instead of only
  // showing events written after mount.
  useEffect(() => {
    setEvents([]);
    cursorRef.current = 0;
    let cancelled = false;
    void getAgentRunAudit(run.id).then(entries => {
      if (cancelled) return;
      const seeded: AgentRunEvent[] = entries.map(entry => ({ sequence: entry.sequence, event: entry.event, data: entry.payload }));
      setEvents(current => mergeAgentEvents(current, seeded));
      cursorRef.current = Math.max(cursorRef.current, agentEventCursor(seeded));
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [run.id]);

  const active = isActiveAgentRun(liveRun.status);

  // Poll while the run is active (PENDING/RUNNING). A paused or terminal run stops
  // advancing; resuming restarts the interval from the last cursor via cursorRef.
  useEffect(() => {
    if (!active) return;
    let stopped = false;
    const tick = async () => {
      try {
        const [page, latest] = await Promise.all([listAgentEvents(run.id, cursorRef.current), getAgentRun(run.id)]);
        if (stopped) return;
        if (page.events.length) setEvents(current => mergeAgentEvents(current, page.events));
        cursorRef.current = Math.max(cursorRef.current, page.next_cursor);
        setLiveRun(latest);
      } catch { /* the next tick retries from the same cursor */ }
    };
    const timer = window.setInterval(() => { void tick(); }, pollIntervalMs);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [active, run.id, pollIntervalMs]);

  const artifactsQuery = useQuery({ queryKey: agentRunKeys.artifacts(run.id), queryFn: () => listAgentArtifacts(run.id), refetchInterval: active ? pollIntervalMs : false, retry: false });
  const reviewsQuery = useQuery({ queryKey: agentRunKeys.reviews(run.id), queryFn: () => listAgentReviews(run.id), refetchInterval: active ? pollIntervalMs : false, retry: false });

  const cursor = agentEventCursor(events);
  const budgetUsed = liveRun.budget_used ?? 0;
  const budgetLimit = liveRun.budget_limit ?? 0;
  const budgetPercent = budgetLimit > 0 ? Math.round(Math.min(1, budgetUsed / budgetLimit) * 100) : 0;

  return <section className="agent-run-page" style={{ display: "grid", gap: 22, color: "var(--ink)" }}>
    <header className="agent-ledger-header" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16, borderBottom: "1px solid var(--ink-faint)", paddingBottom: 14 }}>
      <div style={{ display: "grid", gap: 4 }}>
        <h2 style={{ margin: 0, font: "28px var(--font-seal)", color: "var(--ink-strong)" }}>Agent run</h2>
        <code style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }} aria-label="Run id">{liveRun.id}</code>
      </div>
      <span className={runStampClass(liveRun.status)} data-status={liveRun.status} aria-label={"Run status: " + liveRun.status}>{liveRun.status}</span>
      <div aria-label="Budget ink pool" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div role="progressbar" aria-label="Budget used" aria-valuenow={budgetUsed} aria-valuemax={budgetLimit} style={{ width: 46, height: 46, borderRadius: "50%", display: "grid", placeItems: "center", border: "1px solid var(--ink-faint)", background: `conic-gradient(var(--ink) ${budgetPercent}%, var(--wash) ${budgetPercent}% 100%)` }}>
          <span style={{ width: 34, height: 34, borderRadius: "50%", display: "grid", placeItems: "center", background: "var(--paper-raised)", color: "var(--ink-strong)", font: "10px var(--font-mono)" }}>{budgetPercent}%</span>
        </div>
        <span style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }}>{budgetUsed.toLocaleString()} / {budgetLimit.toLocaleString()} tokens</span>
      </div>
      <span className="agent-event-cursor" aria-label="Event cursor" style={{ color: "var(--ink-strong)", font: "13px var(--font-mono)" }}>{formatCursor(cursor)}</span>
      <span aria-label="Checkpoint" style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }}>checkpoint {liveRun.checkpoint_id ? liveRun.checkpoint_id.slice(0, 8) : "—"}</span>
    </header>

    {liveRun.proposal_id && <p role="note" style={{ margin: 0, color: "var(--ink-mid)", font: "12px var(--font-mono)" }}>Proposal {liveRun.proposal_id.slice(0, 8)} handed to the V2 approval flow; no chapter version is written here.</p>}

    <AgentRunControls onAction={onAction} />

    <div role="group" aria-label="Task view" style={{ display: "flex", gap: 8 }}>
      <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>Table</button>
      <button type="button" aria-pressed={view === "graph"} onClick={() => setView("graph")}>Graph</button>
    </div>
    {view === "graph" ? <AgentGraphView tasks={tasks} /> : <AgentTaskTable tasks={tasks} onRetry={onRetryTask} />}

    <ArtifactPanel artifacts={artifactsQuery.data ?? []} error={artifactsQuery.isError} />
    <ReviewConflictPanel reviews={reviewsQuery.data ?? []} onSelect={onSelectConflict} />

    <section aria-label="Audit ledger" style={{ display: "grid", gap: 8 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontFamily: "var(--font-seal)", fontWeight: 500 }}>Audit ledger</strong>
        <span style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }}>{events.length} events</span>
      </header>
      <table className="agent-audit-table">
        <tbody>
          {events.map((event, index) => <tr key={event.sequence} className={index % 2 === 0 ? "odd" : ""}>
            <td style={{ font: "11px var(--font-mono)", color: "var(--ink-mid)" }}>{formatCursor(event.sequence)}</td>
            <td>{event.event}</td>
            <td style={{ font: "11px var(--font-mono)", color: "var(--ink-mid)", wordBreak: "break-all" }}>{JSON.stringify(event.data)}</td>
          </tr>)}
        </tbody>
      </table>
      {!events.length && <p style={{ margin: 0, color: "var(--ink-light)", fontSize: 12 }}>No events recorded yet.</p>}
    </section>
  </section>;
}
