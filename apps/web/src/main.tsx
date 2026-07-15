import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/views.css";

type View = "projects" | "studio" | "context" | "workflow";

function App() {
  const [view, setView] = useState<View>("studio");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const send = () => { if (draft.trim()) { setMessages([...messages, draft.trim()]); setDraft(""); } };
  const nav = (next: View, icon: string, label: string) => <button onClick={() => setView(next)} className={`nav ${view === next ? "active" : ""}`}>{icon} <span>{label}</span></button>;
  return <div className="shell">
    <aside className="rail"><div className="brand">P<span>F</span></div><nav>{nav("projects", "▦", "Projects")}{nav("studio", "✎", "Writing Studio")}{nav("context", "◌", "Context")}{nav("workflow", "↗", "Workflow")}</nav><div className="rail-bottom">?</div></aside>
    <main className="main"><header><div><p className="eyebrow">CURRENT PROJECT</p><h1>{view === "projects" ? "Projects" : "Moonlit Archive"}</h1></div><button className="ghost">Save draft</button></header>
      {view === "projects" && <section className="project-list"><div className="project-row"><div><strong>Moonlit Archive</strong><small>Writing project · Chapter 01 ready</small></div><button onClick={() => setView("studio")}>Open</button></div><div className="project-row"><div><strong>+ New project</strong><small>Start with an outline or a blank manuscript</small></div><button>Start</button></div></section>}
      {view !== "projects" && <section className="workspace"><div className="manuscript"><div className="chapter-head"><span>Chapter 01</span><span className="status">● Ready</span></div><h2>The quiet after rain</h2><p className="lead">The city kept its secrets in the wet stone.</p><p>By morning, every window carried a small reflection of the night before. Mira walked slowly through the empty market, listening for the familiar rhythm beneath the silence.</p><p>Some stories begin with a door opening. This one began with the courage to stay.</p></div><div className="chat"><div className="chat-head"><strong>Writing companion</strong><span>● Online</span></div><div className="messages">{messages.map((message, i) => <div className="message" key={i}>{message}</div>)}{messages.length === 0 && <div className="empty">Ask for a scene revision, a stronger opening, or a continuity check.</div>}</div><div className="composer"><textarea value={draft} onChange={e => setDraft(e.target.value)} placeholder="Continue the conversation…" onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} /><button onClick={send}>Send <span>↗</span></button></div></div></section>}
    </main>
    <aside className="inspector"><section><h3>{view === "context" ? "Context library" : "Context"}</h3><div className="context-row"><span className="dot clay"/><div><strong>Story bible</strong><small>12 pinned items</small></div><b>›</b></div><div className="context-row"><span className="dot blue"/><div><strong>Chapter plan</strong><small>Current chapter</small></div><b>›</b></div><button className="link">+ Add context</button></section><section><h3>Workflow</h3><div className="workflow"><div className="step done">✓</div><div><strong>Outline approved</strong><small>Completed just now</small></div></div><div className="workflow"><div className="step current">2</div><div><strong>Draft chapter</strong><small>In progress</small></div></div><div className="workflow muted"><div className="step">3</div><div><strong>Review and refine</strong><small>Waiting</small></div></div></section></aside>
  </div>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
