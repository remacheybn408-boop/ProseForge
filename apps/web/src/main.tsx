import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";

function App() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const send = () => { if (draft.trim()) { setMessages([...messages, draft.trim()]); setDraft(""); } };
  return <div className="shell">
    <aside className="rail"><div className="brand">P<span>F</span></div><nav><button className="nav active">▦ <span>Projects</span></button><button className="nav">✎ <span>Writing Studio</span></button><button className="nav">◌ <span>Context</span></button><button className="nav">↗ <span>Workflow</span></button></nav><div className="rail-bottom">?</div></aside>
    <main className="main"><header><div><p className="eyebrow">CURRENT PROJECT</p><h1>Moonlit Archive</h1></div><button className="ghost">Save draft</button></header><section className="workspace"><div className="manuscript"><div className="chapter-head"><span>Chapter 01</span><span className="status">● Ready</span></div><h2>The quiet after rain</h2><p className="lead">The city kept its secrets in the wet stone.</p><p>By morning, every window carried a small reflection of the night before. Mira walked slowly through the empty market, listening for the familiar rhythm beneath the silence.</p><p>Some stories begin with a door opening. This one began with the courage to stay.</p></div><div className="chat"><div className="chat-head"><strong>Writing companion</strong><span>● Online</span></div><div className="messages">{messages.map((message, i) => <div className="message" key={i}>{message}</div>)}{messages.length === 0 && <div className="empty">Ask for a scene revision, a stronger opening, or a continuity check.</div>}</div><div className="composer"><textarea value={draft} onChange={e => setDraft(e.target.value)} placeholder="Continue the conversation…" onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} /><button onClick={send}>Send <span>↗</span></button></div></div></section></main>
    <aside className="inspector"><section><h3>Context</h3><div className="context-row"><span className="dot clay"/><div><strong>Story bible</strong><small>12 pinned items</small></div><b>›</b></div><div className="context-row"><span className="dot blue"/><div><strong>Chapter plan</strong><small>Current chapter</small></div><b>›</b></div><button className="link">+ Add context</button></section><section><h3>Workflow</h3><div className="workflow"><div className="step done">✓</div><div><strong>Outline approved</strong><small>Completed just now</small></div></div><div className="workflow"><div className="step current">2</div><div><strong>Draft chapter</strong><small>In progress</small></div></div><div className="workflow muted"><div className="step">3</div><div><strong>Review and refine</strong><small>Waiting</small></div></div></section></aside>
  </div>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
