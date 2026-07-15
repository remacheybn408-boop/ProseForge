import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/views.css";
import { getHealth, listCredentials, saveCredential, type Credential } from "./lib/api/client";

type View = "projects" | "studio" | "context" | "workflow" | "settings";

function Studio({ messages, draft, setDraft, send }: { messages: string[]; draft: string; setDraft: (value: string) => void; send: () => void }) {
  return <section className="workspace"><div className="manuscript"><div className="chapter-head"><span>Chapter 01</span><span className="status">Ready</span></div><h2>The quiet after rain</h2><p className="lead">The city kept its secrets in the wet stone.</p><p>By morning, every window carried a small reflection of the night before. Mira walked slowly through the empty market, listening for the familiar rhythm beneath the silence.</p><p>Some stories begin with a door opening. This one began with the courage to stay.</p></div><div className="chat"><div className="chat-head"><strong>Writing companion</strong><span>Online</span></div><div className="messages">{messages.map((message, index) => <div className="message" key={index}>{message}</div>)}{messages.length === 0 && <div className="empty">Ask for a scene revision, a stronger opening, or a continuity check.</div>}</div><div className="composer"><textarea value={draft} onChange={event => setDraft(event.target.value)} placeholder="Continue the conversation..." onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} /><button onClick={send}>Send</button></div></div></section>;
}

function ContextView() {
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">PROJECT MEMORY</p><h2>Context library</h2><p>Keep the facts and references that should remain visible while you write.</p></div><div className="detail-list"><div className="detail-card"><strong>Story bible</strong><span>12 pinned items</span><button>Open</button></div><div className="detail-card"><strong>Chapter plan</strong><span>Current chapter · 8 items</span><button>Open</button></div><div className="detail-card"><strong>Recent references</strong><span>3 attachments</span><button>Review</button></div></div></section>;
}

function WorkflowView() {
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">NOVEL WORKFLOW</p><h2>Drafting chapter 01</h2><p>Each step is saved so you can pause and return without losing work.</p></div><div className="timeline"><div className="timeline-item done"><b>1</b><div><strong>Outline approved</strong><span>Completed</span></div></div><div className="timeline-item current"><b>2</b><div><strong>Draft chapter</strong><span>In progress</span></div></div><div className="timeline-item"><b>3</b><div><strong>Rule quality check</strong><span>Waiting</span></div></div><div className="timeline-item"><b>4</b><div><strong>Commit version</strong><span>Waiting</span></div></div></div><div className="workflow-actions"><button>Pause after chapter</button><button className="primary">Continue</button></div></section>;
}

function SettingsView() {
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [message, setMessage] = useState("Secrets are never prefilled.");
  useEffect(() => { if (typeof fetch !== "undefined") listCredentials().then(setCredentials).catch(() => undefined); }, []);
  const save = async () => { if (!apiKey.trim()) return setMessage("Enter an API key to continue."); try { const record = await saveCredential({ provider, api_key: apiKey, base_url: baseUrl || undefined }); setCredentials([...credentials, record]); setApiKey(""); setMessage("Saved securely. The key is now masked."); } catch { setMessage("Sign in to save provider settings."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">MODEL SETTINGS</p><h2>Provider connections</h2><p>Connect a provider once, then choose models by role in your writing workflow.</p></div><div className="settings-form"><label>Provider<select value={provider} onChange={event => setProvider(event.target.value)}><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="ollama">Ollama</option></select></label><label>API key<input type="password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder="sk-..." autoComplete="new-password" /></label><label>Base URL (optional)<input value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder="https://api.example.com" /></label><button className="primary" onClick={save}>Save provider</button><p className="form-message" aria-live="polite">{message}</p></div><div className="detail-list">{credentials.map(item => <div className="detail-card" key={item.id}><strong>{item.provider}</strong><span>{item.masked_key}</span><span>Configured</span></div>)}</div></section>;
}

function App() {
  const [view, setView] = useState<View>("studio");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [connection, setConnection] = useState("Checking");
  useEffect(() => {
    if (typeof fetch === "undefined") return;
    getHealth().then(() => setConnection("Online")).catch(() => setConnection("Offline demo"));
  }, []);
  const send = () => { if (draft.trim()) { setMessages([...messages, draft.trim()]); setDraft(""); } };
  const nav = (next: View, icon: string, label: string) => <button onClick={() => setView(next)} className={`nav ${view === next ? "active" : ""}`}>{icon} <span>{label}</span></button>;
  return <div className="shell"><aside className="rail"><div className="brand">P<span>F</span></div><nav>{nav("projects", "[ ]", "Projects")}{nav("studio", ">", "Writing Studio")}{nav("context", "@", "Context")}{nav("workflow", "#", "Workflow")}{nav("settings", "⚙", "Settings")}</nav><div className="rail-bottom">?</div></aside><main className="main"><header><div><p className="eyebrow">CURRENT PROJECT</p><h1>{view === "projects" ? "Projects" : view === "settings" ? "Settings" : "Moonlit Archive"}</h1></div><button className="ghost">Save draft</button></header>{view === "projects" && <section className="project-list"><div className="project-row"><div><strong>Moonlit Archive</strong><small>Writing project - Chapter 01 ready</small></div><button onClick={() => setView("studio")}>Open</button></div><div className="project-row"><div><strong>+ New project</strong><small>Start with an outline or a blank manuscript</small></div><button>Start</button></div></section>}{view === "studio" && <Studio messages={messages} draft={draft} setDraft={setDraft} send={send}/>} {view === "context" && <ContextView/>}{view === "workflow" && <WorkflowView/>}{view === "settings" && <SettingsView/>}</main><aside className="inspector"><section><h3>Context</h3><div className="context-row"><span className="dot clay"/><div><strong>Story bible</strong><small>12 pinned items</small></div><b>&gt;</b></div><div className="context-row"><span className="dot blue"/><div><strong>Chapter plan</strong><small>Current chapter</small></div><b>&gt;</b></div><button className="link">+ Add context</button></section><section><h3>Workflow</h3><div className="workflow"><div className="step done">1</div><div><strong>Outline approved</strong><small>Completed just now</small></div></div><div className="workflow"><div className="step current">2</div><div><strong>Draft chapter</strong><small>In progress</small></div></div><div className="workflow muted"><div className="step">3</div><div><strong>Review and refine</strong><small>Waiting</small></div></div><div className="connection" aria-live="polite">API: {connection}</div></section></aside></div>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
