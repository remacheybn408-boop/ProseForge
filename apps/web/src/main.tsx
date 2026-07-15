import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/views.css";
import {
  addContext, answerOutline, confirmOutline, controlWorkflow, createConversation, createProject, createWorkflow,
  getHealth, getWorkflow, importOutline, listChapters, listContext, listCredentials, listOutlines,
  listMessages, listProjects, login, saveChapterVersion, saveCredential, sendMessage, setupAdmin, updateContext,
  type Chapter, type ContextItem, type Credential, type Outline, type Project, type Workflow,
} from "./lib/api/client";

type View = "projects" | "studio" | "outline" | "context" | "workflow" | "settings";

function newClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [setup, setSetup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const submit = async () => {
    try {
      if (setup) await setupAdmin({ email, password });
      await login({ email, password });
      onLoggedIn();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to sign in"); }
  };
  return <section className="auth-card"><p className="eyebrow">WELCOME TO PROSEFORGE</p><h1>{setup ? "Create your owner account" : "Sign in to your writing space"}</h1><p className="auth-copy">Your projects, drafts, context and provider settings stay in your Docker-backed workspace.</p><label>Email<input value={email} onChange={event => setEmail(event.target.value)} type="email" autoComplete="email" /></label><label>Password<input value={password} onChange={event => setPassword(event.target.value)} type="password" autoComplete={setup ? "new-password" : "current-password"} /></label><button className="primary wide" onClick={submit}>{setup ? "Create account" : "Sign in"}</button><button className="link" onClick={() => { setSetup(!setup); setMessage(""); }}>{setup ? "I already have an account" : "First run? Create the owner account"}</button><p className="form-message" aria-live="polite">{message}</p></section>;
}

function Projects({ projects, onOpen, onCreated }: { projects: Project[]; onOpen: (project: Project) => void; onCreated: (project: Project) => void }) {
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const create = async () => { try { const project = await createProject({ title, slug: slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") }); onCreated(project); setCreating(false); setTitle(""); setSlug(""); } catch { /* the form remains available for correction */ } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">YOUR WORKSPACES</p><h2>Projects</h2><p>Choose a project to continue writing, or start a new one from an outline.</p></div><div className="detail-list">{projects.map(project => <div className="detail-card" key={project.id}><div><strong>{project.title}</strong><span>{project.genre || "Writing project"} · {project.status}</span></div><button onClick={() => onOpen(project)}>Open</button></div>)}{projects.length === 0 && <p className="empty">No projects yet. Create your first writing space below.</p>}</div>{creating ? <div className="settings-form"><label>Project title<input value={title} onChange={event => setTitle(event.target.value)} placeholder="The Moonlit Archive" /></label><label>URL slug<input value={slug} onChange={event => setSlug(event.target.value)} placeholder="moonlit-archive" /></label><div className="workflow-actions"><button className="primary" onClick={create} disabled={!title}>Create project</button><button onClick={() => setCreating(false)}>Cancel</button></div></div> : <button className="primary create-button" onClick={() => setCreating(true)}>＋ New project</button>}</section>;
}

function Studio({ project }: { project: Project }) {
  const [chapters, setChapters] = useState<Chapter[]>([]); const [chapter, setChapter] = useState<Chapter | null>(null); const [content, setContent] = useState(""); const [baseVersion, setBaseVersion] = useState<number | undefined>(); const [message, setMessage] = useState("Loading chapters…");
  const [conversation, setConversation] = useState<{ id: string; branch_id: string } | null>(null); const [chat, setChat] = useState<{ id: string; role: string; content: string; status: string }[]>([]); const [draft, setDraft] = useState("");
  useEffect(() => { listChapters(project.id).then(items => { setChapters(items); setChapter(items[0] ?? null); setMessage(items.length ? "Ready to write" : "Import an outline to create chapters"); }).catch(() => setMessage("Unable to load chapters")); }, [project.id]);
  const save = async () => { if (!chapter) return; try { const version = await saveChapterVersion(chapter.id, content, baseVersion); setBaseVersion(version.version_no); setMessage(`Saved version ${version.version_no}`); } catch { setMessage("Save conflict: reload the latest version"); } };
  const send = async () => { if (!draft.trim()) return; try { const active = conversation ?? await createConversation(project.id); setConversation(active); const text = draft.trim(); setDraft(""); setChat(items => [...items, { id: newClientId(), role: "user", content: text, status: "COMPLETED" }, { id: newClientId(), role: "assistant", content: "", status: "PENDING" }]); await sendMessage(active.id, { branch_id: active.branch_id, content: text, client_request_id: newClientId() }); setTimeout(() => listMessages(active.id, active.branch_id).then(setChat).catch(() => undefined), 800); } catch { setMessage("Chat could not be queued; check the worker and provider settings."); } };
  return <section className="studio-layout"><aside className="chapter-tree"><strong>Chapters</strong>{chapters.map(item => <button className={chapter?.id === item.id ? "selected" : ""} key={item.id} onClick={() => setChapter(item)}>{String(item.chapter_no).padStart(2, "0")} · {item.title}</button>)}{!chapters.length && <small>{message}</small>}</aside><div className="editor-pane"><div className="chapter-head"><span>{chapter ? `Chapter ${String(chapter.chapter_no).padStart(2, "0")}` : project.title}</span><span className="status">{message}</span></div><textarea className="editor" value={content} onChange={event => setContent(event.target.value)} placeholder="Your chapter will appear here…" /><button className="primary" onClick={save} disabled={!chapter}>Save version</button></div><div className="review-pane chat-pane"><strong>Writing companion</strong><div className="chat-messages">{chat.length === 0 && <p>Ask for a scene revision or continuity check.</p>}{chat.map(item => <div className={`chat-message ${item.role}`} key={item.id}>{item.content || "Waiting for the worker…"}<small>{item.status}</small></div>)}</div><div className="chat-composer"><textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder="Ask your companion…" /><button className="primary" onClick={send}>Send</button></div></div></section>;
}

function OutlineView({ project, onWorkflow }: { project: Project; onWorkflow: (workflow: Workflow) => void }) {
  const [outline, setOutline] = useState<Outline | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [answer, setAnswer] = useState("");
  const [message, setMessage] = useState("Import an outline or describe your story below.");
  const submit = async () => { try { const item = await importOutline(project.id, { title: title || "Untitled outline", content }); setOutline(item); setMessage(item.missing_questions.length ? "A few answers are needed before confirmation." : "Ready to confirm."); } catch { setMessage("Outline import failed"); } };
  const answerMissing = async () => { if (!outline || !answer.trim()) return; try { const item = await answerOutline(outline.id, { characters: [answer], genre: "小说", point_of_view: "third-person", title: outline.title, planned_chapters: 12, chapter_word_target: 1500 }); setOutline(item); setAnswer(""); setMessage(item.missing_questions.length ? "More answers are needed." : "Ready to confirm."); } catch { setMessage("Could not save the answer"); } };
  const confirm = async () => { if (!outline) return; try { await confirmOutline(outline.id); const workflow = await createWorkflow(project.id, [1]); onWorkflow(workflow); setMessage("Outline confirmed; workflow created."); } catch { setMessage("Complete the required answers first."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">OUTLINE INTAKE</p><h2>Start from your story idea</h2><p>ProseForge saves the outline before asking only the questions it still needs.</p></div><div className="settings-form"><label>Outline title<input value={title} onChange={event => setTitle(event.target.value)} placeholder="The Moonlit Archive" /></label><label>Outline or story notes<textarea value={content} onChange={event => setContent(event.target.value)} placeholder="Paste your outline, characters and ending…" /></label><button className="primary" onClick={submit}>Import and analyze</button></div>{outline && <div className="outline-status"><strong>{outline.title}</strong><span>Status: {outline.status}</span>{outline.missing_questions.map(question => <span key={question}>{question}</span>)}{outline.missing_questions.length > 0 && <div className="answer-row"><input value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Answer the missing requirement" /><button onClick={answerMissing}>Save answer</button></div>}{outline.missing_questions.length === 0 && <button className="primary" onClick={confirm}>Confirm and create workflow</button>}</div>}<p className="form-message" aria-live="polite">{message}</p></section>;
}

function ContextView({ project }: { project: Project }) {
  const [items, setItems] = useState<ContextItem[]>([]); const [used, setUsed] = useState(0); const [content, setContent] = useState("");
  const reload = () => listContext(project.id).then(result => { setItems(result.items); setUsed(result.used_tokens); }).catch(() => undefined);
  useEffect(reload, [project.id]);
  const add = async () => { if (!content.trim()) return; const item = await addContext(project.id, content); setItems([...items, item]); setContent(""); };
  const pin = async (item: ContextItem) => { const updated = await updateContext(item.id, { pinned: !item.pinned }); setItems(items.map(value => value.id === item.id ? updated : value)); };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">PROJECT MEMORY</p><h2>Context library</h2><p>{used.toLocaleString()} tokens currently selected. Pin facts you never want the writer to forget.</p></div><div className="settings-form"><label>Add a memory<textarea value={content} onChange={event => setContent(event.target.value)} placeholder="Mira is afraid of deep water…" /></label><button className="primary" onClick={add}>Add context</button></div><div className="detail-list">{items.map(item => <div className="detail-card" key={item.id}><div><strong>{item.pinned ? "📌 " : ""}{item.source_type}</strong><span>{item.content}</span></div><button onClick={() => pin(item)}>{item.pinned ? "Unpin" : "Pin"}</button></div>)}</div></section>;
}

function WorkflowView({ project, workflow, onWorkflow }: { project: Project; workflow: Workflow | null; onWorkflow: (workflow: Workflow) => void }) {
  const [current, setCurrent] = useState(workflow); const [message, setMessage] = useState("No workflow has been started yet.");
  useEffect(() => { if (workflow) { setCurrent(workflow); return; } }, [workflow]);
  const action = async (name: "pause" | "resume" | "cancel" | "retry") => { if (!current) return; try { const result = await controlWorkflow(current.id, name); setCurrent(result); onWorkflow(result); setMessage(`Workflow ${result.status.toLowerCase()}.`); } catch { setMessage("That action is not available in the current state."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">DURABLE WORKFLOW</p><h2>{current ? "Chapter workflow" : "No active workflow"}</h2><p>{current ? `Project: ${project.title} · ${current.status}` : message}</p></div>{current ? <><div className="timeline"><div className="timeline-item done"><b>1</b><div><strong>Outline confirmed</strong><span>Saved to PostgreSQL</span></div></div><div className="timeline-item current"><b>2</b><div><strong>Draft chapter</strong><span>{current.status}</span></div></div><div className="timeline-item"><b>3</b><div><strong>Review and commit</strong><span>Waiting</span></div></div></div><div className="workflow-actions"><button onClick={() => action("pause")}>Pause</button><button onClick={() => action("resume")}>Resume</button><button onClick={() => action("cancel")}>Cancel</button><button onClick={() => action("retry")}>Retry</button></div></> : <p className="form-message">Open Outline Intake to start a workflow.</p>}</section>;
}

function SettingsView() {
  const [provider, setProvider] = useState("openai"); const [apiKey, setApiKey] = useState(""); const [baseUrl, setBaseUrl] = useState(""); const [credentials, setCredentials] = useState<Credential[]>([]); const [message, setMessage] = useState("Secrets are never prefilled.");
  useEffect(() => { listCredentials().then(setCredentials).catch(() => undefined); }, []);
  const save = async () => { if (!apiKey.trim()) return setMessage("Enter an API key to continue."); try { const record = await saveCredential({ provider, api_key: apiKey, base_url: baseUrl || undefined }); setCredentials([...credentials, record]); setApiKey(""); setMessage("Saved securely. The key is now masked."); } catch { setMessage("Sign in to save provider settings."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">MODEL SETTINGS</p><h2>Provider connections</h2><p>Connect a provider once. The raw secret is never rendered back into the browser.</p></div><div className="settings-form"><label>Provider<select value={provider} onChange={event => setProvider(event.target.value)}>{["openai", "anthropic", "google", "deepseek", "kimi", "dashscope", "zhipu", "volcengine", "baidu", "tencent", "minimax", "xai", "mistral", "cohere", "ollama", "vllm"].map(item => <option key={item} value={item}>{item}</option>)}</select></label><label>API key<input type="password" value={apiKey} onChange={event => setApiKey(event.target.value)} autoComplete="new-password" /></label><label>Base URL (optional)<input value={baseUrl} onChange={event => setBaseUrl(event.target.value)} /></label><button className="primary" onClick={save}>Save provider</button><p className="form-message" aria-live="polite">{message}</p></div><div className="detail-list">{credentials.map(item => <div className="detail-card" key={item.id}><strong>{item.provider}</strong><span>{item.masked_key}</span><span>Configured</span></div>)}</div></section>;
}

function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null); const [projects, setProjects] = useState<Project[]>([]); const [project, setProject] = useState<Project | null>(null); const [view, setView] = useState<View>("projects"); const [workflow, setWorkflow] = useState<Workflow | null>(null); const [connection, setConnection] = useState("Checking");
  const load = () => { listProjects().then(items => { setProjects(items); setProject(current => current ?? items[0] ?? null); setAuthenticated(true); }).catch(() => setAuthenticated(false)); };
  useEffect(() => { getHealth().then(() => setConnection("Online")).catch(() => setConnection("Offline")); load(); }, []);
  if (authenticated === false) return <main className="auth-shell"><Login onLoggedIn={load} /></main>;
  if (authenticated === null) return <main className="auth-shell"><p>Connecting to your Docker workspace…</p></main>;
  const nav = (next: View, label: string) => <button onClick={() => setView(next)} className={`nav ${view === next ? "active" : ""}`}>{label}</button>;
  return <div className="shell"><aside className="rail"><div className="brand">P<span>F</span></div><nav>{nav("projects", "Projects")}{nav("studio", "Writing Studio")}{nav("outline", "Outline intake")}{nav("context", "Context")}{nav("workflow", "Workflow")}{nav("settings", "Settings")}</nav><div className="rail-bottom">API: {connection}</div></aside><main className="main"><header><div><p className="eyebrow">CURRENT PROJECT</p><h1>{project?.title ?? "Projects"}</h1></div>{project && <button className="ghost" onClick={() => setView("projects")}>All projects</button>}</header>{view === "projects" && <Projects projects={projects} onOpen={item => { setProject(item); setView("studio"); }} onCreated={item => { setProjects([...projects, item]); setProject(item); setView("outline"); }} />}{project && view === "studio" && <Studio project={project} />}{project && view === "outline" && <OutlineView project={project} onWorkflow={item => { setWorkflow(item); setView("workflow"); }} />}{project && view === "context" && <ContextView project={project} />}{project && view === "workflow" && <WorkflowView project={project} workflow={workflow} onWorkflow={setWorkflow} />}{view === "settings" && <SettingsView />}</main><aside className="inspector"><section><h3>Project status</h3><p>{project ? "Ready to continue" : "Create a project first"}</p><small>Everything is saved in your Docker-backed workspace.</small></section><section><h3>Workflow</h3><p>{workflow ? workflow.status : "Not started"}</p><button className="link" onClick={() => setView("workflow")}>Open workflow</button></section></aside></div>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
