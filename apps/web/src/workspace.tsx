import { useEffect, useState } from "react";
import "./styles/tokens.css";
import "./styles/views.css";
import {
  activateChapterVersion, addContext, answerOutline, confirmOutline, controlWorkflow, createConversation, createProject, createWorkflow,
  getChapterDiff, importOutline, listChapters, listChapterVersions, listContext, listCredentials,
  forkConversation, listMessages, login, probeProvider, saveChapterVersion, saveCredential, sendMessage, setupAdmin, subscribeConversationEvents, updateContext,
  getWorkflow, listModelProfiles, logout, requestExport, saveModelProfile, type Chapter, type ChapterVersion, type ContextItem, type Credential, type ModelProfile, type Outline, type Project, type Workflow,
} from "./lib/api/client";
import { loadDraft, saveDraft } from "./lib/drafts";
import { ProjectVersionHistory } from "./features/VersionHistory";
import { chapterDraftKey as makeChapterDraftKey, shouldApplyServerVersion } from "./features/editor/documentState";
import { useLanguage } from "./lib/i18n";
import { useHealthQuery, useModelsQuery, useProjectsQuery, useProvidersQuery, useUsageSummaryQuery, queryClient } from "./app/query";
import { navigateRoute, useAppRoute, type AppView } from "./app/router";
import { ApiError } from "./lib/api/client";
import { ContextBudgetBar } from "./features/usage/ContextBudgetBar";
import { TokenMeter } from "./features/usage/TokenMeter";
import { UsagePage } from "./features/usage/UsagePage";

function newClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const { t } = useLanguage();
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
  return <section className="auth-card"><p className="eyebrow">{t("appName")}</p><h1>{setup ? t("createOwner") : t("signInTitle")}</h1><p className="auth-copy">{t("authIntro")}</p><label>Email<input value={email} onChange={event => setEmail(event.target.value)} type="email" autoComplete="email" /></label><label>Password<input value={password} onChange={event => setPassword(event.target.value)} type="password" autoComplete={setup ? "new-password" : "current-password"} /></label><button className="primary wide" onClick={submit}>{setup ? t("createOwner") : t("signIn")}</button><button className="link" onClick={() => { setSetup(!setup); setMessage(""); }}>{setup ? t("alreadyAccount") : t("firstRun")}</button><p className="form-message" aria-live="polite">{message}</p></section>;
}

function Projects({ projects, onOpen, onCreated }: { projects: Project[]; onOpen: (project: Project) => void; onCreated: (project: Project) => void }) {
  const { t } = useLanguage();
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const create = async () => { try { const project = await createProject({ title, slug: slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") }); onCreated(project); setCreating(false); setTitle(""); setSlug(""); } catch { /* the form remains available for correction */ } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("yourWorkspaces")}</p><h2>{t("projects")}</h2><p>{t("chooseProject")}</p></div><div className="detail-list">{projects.map(project => <div className="detail-card" key={project.id}><div><strong>{project.title}</strong><span>{project.genre || t("writingProject")} · {project.status}</span></div><button onClick={() => onOpen(project)}>{t("open")}</button></div>)}{projects.length === 0 && <p className="empty">{t("noProjects")}</p>}</div>{creating ? <div className="settings-form"><label>{t("projectTitle")}<input value={title} onChange={event => setTitle(event.target.value)} placeholder={t("projectTitlePlaceholder")} /></label><label>{t("urlSlug")}<input value={slug} onChange={event => setSlug(event.target.value)} placeholder={t("urlSlugPlaceholder")} /></label><div className="workflow-actions"><button className="primary" onClick={create} disabled={!title}>{t("createProject")}</button><button onClick={() => setCreating(false)}>{t("cancel")}</button></div></div> : <button className="primary create-button" onClick={() => setCreating(true)}>＋ {t("newProject")}</button>}</section>;
}

function Studio({ project }: { project: Project }) {
  const { t } = useLanguage();
  const [versions, setVersions] = useState<ChapterVersion[]>([]); const [diff, setDiff] = useState<string[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]); const [chapter, setChapter] = useState<Chapter | null>(null); const [content, setContent] = useState(""); const [baseVersion, setBaseVersion] = useState<number | undefined>(); const [loadedChapterId, setLoadedChapterId] = useState<string | null>(null); const [loadedVersionId, setLoadedVersionId] = useState<string | null>(null); const [dirty, setDirty] = useState(false); const [message, setMessage] = useState(t("loadingChapters"));
  const [conversation, setConversation] = useState<{ id: string; branch_id: string } | null>(null); const [chat, setChat] = useState<{ id: string; role: string; content: string; status: string }[]>([]); const [draft, setDraft] = useState(""); const [profiles, setProfiles] = useState<ModelProfile[]>([]); const [profileId, setProfileId] = useState("");
  useEffect(() => { listChapters(project.id).then(items => { setChapters(items); setChapter(items[0] ?? null); setMessage(items.length ? t("readyToWrite") : t("importOutlineToCreate")); }).catch(() => setMessage(t("unableLoad"))); listModelProfiles().then(items => { setProfiles(items); setProfileId(items[0]?.id ?? ""); }).catch(() => undefined); }, [project.id, t]);
  useEffect(() => { if (!chapter) return; let active = true; let timer: number | undefined; const loadVersions = async () => { try { const items = await listChapterVersions(chapter.id); if (!active) return; setVersions(items); const current = items.find(item => item.id === chapter.active_version_id) ?? items.at(-1); const server = { chapterId: chapter.id, versionId: current?.id ?? "empty" }; if (shouldApplyServerVersion({ chapterId: loadedChapterId, loadedVersionId, dirty }, server)) { setContent(current?.content ?? ""); setLoadedChapterId(chapter.id); setLoadedVersionId(current?.id ?? null); setDirty(false); } setBaseVersion(current?.version_no); setDiff([]); if (items.length) setMessage(`Loaded saved version ${current?.version_no ?? items.at(-1)?.version_no}`); else timer = window.setTimeout(() => { void loadVersions(); }, 1000); } catch { if (active) { setMessage("Unable to load the saved chapter"); timer = window.setTimeout(() => { void loadVersions(); }, 1000); } } }; void loadVersions(); return () => { active = false; if (timer) window.clearTimeout(timer); }; }, [chapter?.id, chapter?.active_version_id]);
  const currentChapterDraftKey = chapter ? makeChapterDraftKey(project.id, chapter.id) : null;
  useEffect(() => { if (!currentChapterDraftKey) return; loadDraft(currentChapterDraftKey).then(value => { if (value.trim()) { setContent(current => current.trim() ? current : value); setDirty(true); } }).catch(() => undefined); }, [currentChapterDraftKey?.projectId, currentChapterDraftKey?.chapterId]);
  useEffect(() => { if (!currentChapterDraftKey || !content.trim() || !dirty) return; const timer = window.setTimeout(() => { saveDraft(currentChapterDraftKey, content).catch(() => undefined); }, 600); return () => window.clearTimeout(timer); }, [currentChapterDraftKey?.projectId, currentChapterDraftKey?.chapterId, content, dirty]);
  const draftKey = { conversationId: conversation?.id ?? `project:${project.id}`, branchId: conversation?.branch_id ?? "main", draftType: "chat" as const };
  useEffect(() => { let active = true; loadDraft(draftKey).then(value => { if (active && value) setDraft(value); }).catch(() => undefined); return () => { active = false; }; }, [draftKey.conversationId, draftKey.branchId, project.id]);
  useEffect(() => { saveDraft(draftKey, draft).catch(() => undefined); }, [draft, draftKey.conversationId, draftKey.branchId, project.id]);
  const save = async () => { if (!chapter) return; try { const version = await saveChapterVersion(chapter.id, content, baseVersion); setVersions(items => [...items, version]); setBaseVersion(version.version_no); setLoadedChapterId(chapter.id); setLoadedVersionId(version.id); setDirty(false); if (currentChapterDraftKey) await saveDraft(currentChapterDraftKey, ""); setMessage(`Saved version ${version.version_no}`); } catch { setMessage("Save conflict: reload the latest version"); } };
  const restore = async (version: ChapterVersion) => { if (!chapter) return; try { await activateChapterVersion(chapter.id, version.id); setContent(version.content); setBaseVersion(version.version_no); setLoadedChapterId(chapter.id); setLoadedVersionId(version.id); setDirty(false); setMessage(`Restored version ${version.version_no}`); } catch { setMessage("Could not restore that version"); } };
  const showDiff = async (version: ChapterVersion) => { if (!chapter || !baseVersion || version.version_no === baseVersion) return setDiff([]); try { const result = await getChapterDiff(chapter.id, version.version_no, baseVersion); setDiff(result.diff); setMessage(`Diff loaded: ${result.diff.length} changed lines`); } catch { setMessage("Could not load the version diff"); } };
  const send = async () => { if (!draft.trim()) return; let closeEvents: (() => void) | undefined; try { const active = conversation ?? await createConversation(project.id); setConversation(active); const text = draft.trim(); const selected = profiles.find(item => item.id === profileId); setDraft(""); setChat(items => [...items, { id: newClientId(), role: "user", content: text, status: "COMPLETED" }, { id: newClientId(), role: "assistant", content: "", status: "PENDING" }]); closeEvents = subscribeConversationEvents(active.id, event => { if (event.event !== "content.delta" || !event.message_id) return; setChat(items => items.map(item => item.id === event.message_id ? { ...item, content: `${item.content}${event.text ?? ""}`, status: "STREAMING" } : item)); }); const queued = await sendMessage(active.id, { branch_id: active.branch_id, content: text, client_request_id: newClientId(), provider: String(selected?.config.provider ?? "openai"), model: String(selected?.config.model ?? "gpt-4.1-mini") }); setChat(items => items.map(item => item.role === "assistant" && item.status === "PENDING" ? { ...item, id: queued.assistant_message_id } : item)); for (let attempt = 0; attempt < 20; attempt += 1) { const messages = await listMessages(active.id, active.branch_id); setChat(messages); const assistant = [...messages].reverse().find(item => item.role === "assistant"); if (assistant && ["COMPLETED", "FAILED", "PARTIAL", "CANCELLED"].includes(assistant.status)) break; await new Promise(resolve => setTimeout(resolve, 500)); } } catch { setMessage("Chat could not be queued; check the worker and provider settings."); } finally { closeEvents?.(); } };
  const fork = async () => { if (!conversation || !chat.length) return; try { const latest = await listMessages(conversation.id, conversation.branch_id); const point = [...latest].reverse().find(item => item.role === "assistant") ?? latest.at(-1); if (!point) return; const branch = await forkConversation(conversation.id, point.id, `Alternative ${new Date().toLocaleTimeString()}`); setConversation({ id: conversation.id, branch_id: branch.id }); setChat(await listMessages(conversation.id, branch.id)); setMessage("Alternative branch created."); } catch { setMessage("Could not create an alternative branch."); } };
  const downloadMarkdown = async () => { try { const result = await requestExport(project.id, "md"); window.open(result.download_url, "_blank", "noopener,noreferrer"); } catch { setMessage("Export could not be prepared."); } };
  return <section className="studio-layout"><aside className="chapter-tree"><strong>{t("chapters")}</strong>{chapters.map(item => <button className={chapter?.id === item.id ? "selected" : ""} key={item.id} onClick={() => setChapter(item)}>{String(item.chapter_no).padStart(2, "0")} · {item.title}</button>)}{!chapters.length && <small>{message}</small>}</aside><div className="editor-pane"><div className="chapter-head"><span>{chapter ? `${t("chapters")} ${String(chapter.chapter_no).padStart(2, "0")}` : project.title}</span><span className="status">{message}</span></div><textarea className="editor" value={content} onChange={event => { setContent(event.target.value); setDirty(true); }} placeholder={t("waitingForWorker")} /><div className="version-actions">{versions.map(version => <span key={version.id}><button onClick={() => restore(version)}>v{version.version_no}</button><button onClick={() => showDiff(version)} aria-label={`Diff version ${version.version_no}`}>Diff</button></span>)}</div>{diff.length > 0 && <pre className="diff-preview">{diff.join("\n")}</pre>}<button className="primary" onClick={save} disabled={!chapter}>{t("saveVersion")}</button><button onClick={downloadMarkdown}>{t("downloadMarkdown")}</button></div><div className="review-pane chat-pane"><strong>{t("writingCompanion")}</strong>{profiles.length > 0 && <label>{t("modelProfile")}<select value={profileId} onChange={event => setProfileId(event.target.value)}>{profiles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}<div className="chat-messages">{chat.length === 0 && <p>{t("askCompanion")}</p>}{chat.map(item => <div className={`chat-message ${item.role}`} key={item.id}>{item.content || t("waitingForWorker")}<small>{item.status}</small></div>)}</div><div className="chat-composer"><textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder={t("askCompanion")} /><button onClick={fork} disabled={!conversation || !chat.length}>{t("forkBranch")}</button><button className="primary" onClick={send}>{t("send")}</button></div></div></section>;
}

function OutlineView({ project, onWorkflow }: { project: Project; onWorkflow: (workflow: Workflow) => void }) {
  const { t } = useLanguage();
  const [outline, setOutline] = useState<Outline | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [startChapter, setStartChapter] = useState(1);
  const [endChapter, setEndChapter] = useState(1);
  const [message, setMessage] = useState("Import an outline or describe your story below.");
  const submit = async () => { try { const item = await importOutline(project.id, { title: title || "Untitled outline", content }); setOutline(item); setMessage(item.missing_questions.length ? "A few answers are needed before confirmation." : "Ready to confirm."); } catch { setMessage("Outline import failed"); } };
  const answerField = (question: string, index: number) => outline?.missing_fields[index] ?? question.match(/：(.+)/)?.[1] ?? `question_${index}`;
  const answerMissing = async () => { if (!outline || !Object.values(answers).some(value => value.trim())) return; try { const normalized = Object.fromEntries(Object.entries(answers).map(([key, value]) => [key, /^\d+$/.test(value) ? Number(value) : key === "characters" ? [value] : value])); const item = await answerOutline(outline.id, normalized); setOutline(item); setAnswers({}); setMessage(item.missing_questions.length ? "More answers are needed." : "Ready to confirm."); } catch { setMessage("Could not save the answer"); } };
  const confirm = async () => { if (!outline) return; try { await confirmOutline(outline.id); const workflow = await createWorkflow(project.id, Array.from({ length: Math.max(1, endChapter - startChapter + 1) }, (_, index) => startChapter + index)); onWorkflow(workflow); setMessage("Outline confirmed; workflow created."); } catch { setMessage("Complete the required answers first."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("outlineIntake")}</p><h2>{t("outlineHero")}</h2><p>{t("outlineIntro")}</p></div><div className="settings-form"><label>{t("outlineTitle")}<input value={title} onChange={event => setTitle(event.target.value)} placeholder={t("outlineTitlePlaceholder")} /></label><label>{t("outlineNotes")}<textarea value={content} onChange={event => setContent(event.target.value)} placeholder={t("outlineNotesPlaceholder")} /></label><button className="primary" onClick={submit}>{t("importAnalyze")}</button></div>{outline && <div className="outline-status"><strong>{outline.title}</strong><span>{t("status")}: {outline.status}</span>{outline.missing_questions.map((question, index) => <label key={question}>{question}<input value={answers[answerField(question, index)] ?? ""} onChange={event => setAnswers(current => ({ ...current, [answerField(question, index)]: event.target.value }))} placeholder={t("answerMissing")} /></label>)}{outline.missing_questions.length > 0 && <button onClick={answerMissing}>{t("saveAnswer")}</button>}{outline.missing_questions.length === 0 && <><div className="answer-row"><label>Start chapter<input type="number" min="1" value={startChapter} onChange={event => setStartChapter(Number(event.target.value))} /></label><label>End chapter<input type="number" min={startChapter} value={endChapter} onChange={event => setEndChapter(Number(event.target.value))} /></label></div><button className="primary" onClick={confirm}>{t("confirmWorkflow")}</button></>}</div>}<p className="form-message" aria-live="polite">{message}</p></section>;
}

function ContextView({ project }: { project: Project }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<ContextItem[]>([]); const [used, setUsed] = useState(0); const [contextWindow, setContextWindow] = useState(128000); const [content, setContent] = useState(""); const [profileId, setProfileId] = useState("");
  const reload = () => listContext(project.id, profileId ? { profileId } : {}).then(result => { setItems(result.items); setUsed(result.used_tokens); setContextWindow(result.context_window); }).catch(() => undefined);
  useEffect(() => { listModelProfiles().then(items => { setProfileId(current => current || items[0]?.id || ""); }).catch(() => undefined); }, []);
  useEffect(() => { void reload(); }, [project.id, profileId]);
  const add = async () => { if (!content.trim()) return; const item = await addContext(project.id, content); setItems([...items, item]); setContent(""); };
  const pin = async (item: ContextItem) => { const updated = await updateContext(item.id, { pinned: !item.pinned }); setItems(items.map(value => value.id === item.id ? updated : value)); };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("context")}</p><h2>{t("contextHero")}</h2><p>{t("contextIntro")}</p><ContextBudgetBar used={used} available={Math.max(0, contextWindow - used)} total={contextWindow} /></div><div className="settings-form"><label>{t("addMemory")}<textarea value={content} onChange={event => setContent(event.target.value)} placeholder={t("addMemoryPlaceholder")} /></label><button className="primary" onClick={add}>{t("addContext")}</button></div><div className="detail-list">{items.map(item => <div className="detail-card" key={item.id}><div><strong>{item.pinned ? "📌 " : ""}{item.source_type}</strong><span>{item.content}</span></div><button onClick={() => pin(item)}>{item.pinned ? t("unpin") : t("pin")}</button></div>)}</div></section>;
}

function WorkflowView({ project, workflow, onWorkflow }: { project: Project; workflow: Workflow | null; onWorkflow: (workflow: Workflow) => void }) {
  const { t } = useLanguage();
  const [current, setCurrent] = useState(workflow); const [message, setMessage] = useState("No workflow has been started yet.");
  useEffect(() => { if (workflow) { setCurrent(workflow); return; } }, [workflow]);
  const action = async (name: "pause" | "resume" | "cancel" | "retry") => { if (!current) return; try { const result = await controlWorkflow(current.id, name); setCurrent(result); onWorkflow(result); setMessage(`Workflow ${result.status.toLowerCase()}.`); } catch { setMessage("That action is not available in the current state."); } };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("workflow")}</p><h2>{current ? t("workflowHero") : t("notStarted")}</h2><p>{current ? `${project.title} · ${current.status}` : message}</p></div>{current ? <><div className="timeline"><div className="timeline-item done"><b>1</b><div><strong>{t("outlineConfirmed")}</strong><span>{t("savedToPostgres")}</span></div></div><div className="timeline-item current"><b>2</b><div><strong>{t("draftChapter")}</strong><span>{current.status}</span></div></div><div className="timeline-item"><b>3</b><div><strong>{t("reviewCommit")}</strong><span>{t("waiting")}</span></div></div></div><div className="workflow-actions"><button onClick={() => action("pause")}>{t("pause")}</button><button onClick={() => action("resume")}>{t("resume")}</button><button onClick={() => action("cancel")}>{t("cancel")}</button><button onClick={() => action("retry")}>{t("retry")}</button></div></> : <p className="form-message">{t("outlineIntake")}</p>}</section>;
}

function SettingsView() {
  const { t } = useLanguage();
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileName, setProfileName] = useState("");
  const [modelId, setModelId] = useState("");
  const [profileRole, setProfileRole] = useState<"writer" | "editor">("writer");
  const [probeStates, setProbeStates] = useState<Record<string, "connected" | "failed">>({});
  const [message, setMessage] = useState(t("secretsNeverPrefilled"));
  const providersQuery = useProvidersQuery();
  const modelsQuery = useModelsQuery(provider);
  useEffect(() => { listCredentials().then(setCredentials).catch(() => undefined); listModelProfiles().then(setProfiles).catch(() => undefined); }, []);
  const save = async () => { if (!apiKey.trim()) return setMessage(t("apiKeyHelp")); try { const record = await saveCredential({ provider, api_key: apiKey, base_url: baseUrl || undefined }); setCredentials([...credentials, record]); setApiKey(""); setMessage(t("configured")); } catch { setMessage(t("genericError")); } };
  const probe = async (item: Credential) => { setMessage(`${item.provider}…`); try { await probeProvider(item.provider); setProbeStates(states => ({ ...states, [item.id]: "connected" })); setMessage(`${item.provider} · ${t("connected")}`); } catch { setProbeStates(states => ({ ...states, [item.id]: "failed" })); setMessage(`${item.provider} · ${t("checkFailed")}`); } };
  const saveProfile = async () => { if (!profileName.trim() || !modelId.trim()) return setMessage(t("modelIdHelp")); try { const profile = await saveModelProfile({ name: profileName.trim(), role: profileRole, config: { provider, model: modelId.trim() } }); setProfiles([...profiles, profile]); setProfileName(""); setModelId(""); setMessage(t("configured")); } catch { setMessage(t("genericError")); } };
  const providers = providersQuery.data?.map(item => item.id) ?? [];
  return <section className="detail-view settings-page">
    <div className="detail-heading"><p className="eyebrow">{t("modelSettings")}</p><h2>{t("providerConnections")}</h2><p>{t("providerIntro")}</p></div>
    <section className="settings-section"><div className="settings-section-heading"><h3>{t("providerConnections")}</h3><p>{t("apiKeyHelp")}</p></div><div className="settings-form">
      <label>{t("provider")}<select value={provider} onChange={event => setProvider(event.target.value)}>{providers.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
      <label>{t("apiKey")}<input type="password" value={apiKey} onChange={event => setApiKey(event.target.value)} autoComplete="new-password" placeholder="sk-…" /></label><small className="field-help">{t("apiKeyHelp")}</small>
      <label>{t("baseUrl")}<input value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" /></label><small className="field-help">{t("baseUrlHelp")}</small>
      <button className="primary" onClick={save}>{t("saveProvider")}</button><p className="form-message" aria-live="polite">{message}</p>
    </div></section>
    <section className="settings-section"><div className="settings-section-heading"><h3>{t("configured")}</h3><p>{t("secretsNeverPrefilled")}</p></div><div className="settings-list">{credentials.length === 0 && <p className="empty">{t("notConnected")}</p>}{credentials.map(item => { const state = probeStates[item.id]; return <div className="settings-row" key={item.id}><div><strong>{item.provider}</strong><span>{item.masked_key}</span></div><span className={`connection-status ${state ?? "unknown"}`}>{state === "connected" ? t("connected") : state === "failed" ? t("checkFailed") : t("notConnected")}</span><button onClick={() => probe(item)}>{t("testConnection")}</button></div>; })}</div></section>
    <section className="settings-section"><div className="settings-section-heading"><h3>{t("writerEditor")}</h3><p>{t("writerEditorIntro")}</p></div><div className="settings-form">
      <label>{t("writerEditor")}<select value={profileRole} onChange={event => setProfileRole(event.target.value as "writer" | "editor")}><option value="writer">{t("writerModel")}</option><option value="editor">{t("editorModel")}</option></select></label>
      <label>{t("profileName")}<input value={profileName} onChange={event => setProfileName(event.target.value)} placeholder={t("profileNamePlaceholder")} /></label>
      <label>{t("modelId")}<input list="model-options" value={modelId} onChange={event => setModelId(event.target.value)} placeholder="gpt-4.1-mini" /></label><datalist id="model-options">{modelsQuery.data?.map(item => <option key={`${item.provider}:${item.model_id}`} value={item.model_id}>{item.display_name}</option>)}</datalist><small className="field-help">{t("modelIdHelp")}</small>
      <button onClick={saveProfile}>{t("saveProfile")}</button>
    </div><div className="settings-list">{profiles.map(profile => <div className="settings-row" key={profile.id}><div><strong>{String(profile.config.role ?? "writer") === "writer" ? t("writerModel") : t("editorModel")} · {profile.name}</strong><span>{String(profile.config.provider)} / {String(profile.config.model)}</span></div><span className="connection-status connected">{t("configured")}</span></div>)}</div></section>
  </section>;
}

export function App() {
  const { t, language, setLanguage } = useLanguage();
  const route = useAppRoute();
  const projectsQuery = useProjectsQuery();
  const healthQuery = useHealthQuery();
  const [authenticated, setAuthenticated] = useState<boolean | null>(null); const [project, setProject] = useState<Project | null>(null); const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const projects = projectsQuery.data ?? [];
  const usageQuery = useUsageSummaryQuery(project?.id);
  const connection = healthQuery.isSuccess ? "Online" : healthQuery.isError ? "Offline" : "Checking";
  const signOut = async () => { await logout(); queryClient.clear(); setProject(null); setWorkflow(null); window.localStorage.removeItem("proseforge.current-workflow"); setAuthenticated(false); navigateRoute({ view: "projects" }); };
  const load = async () => {
    const result = await projectsQuery.refetch();
    if (result.error) {
      setAuthenticated(result.error instanceof ApiError && result.error.status === 401 ? false : true);
      return;
    }
    setAuthenticated(true);
  };
  useEffect(() => {
    if (projectsQuery.isSuccess) {
      const savedId = window.localStorage.getItem("proseforge.current-project");
      const restored = projects.find(item => item.id === savedId) ?? projects[0] ?? null;
      setProject(current => current ?? restored);
      if (restored && route.view === "projects" && window.location.pathname === "/") {
        window.localStorage.setItem("proseforge.current-project", restored.id);
        navigateRoute({ view: "studio", projectId: restored.id });
      }
      setAuthenticated(true);
    } else if (projectsQuery.error instanceof ApiError && projectsQuery.error.status === 401) {
      setAuthenticated(false);
    }
  }, [projectsQuery.isSuccess, projectsQuery.error, projects, route.view]);
  useEffect(() => {
    if (authenticated !== true) return;
    const workflowId = window.localStorage.getItem("proseforge.current-workflow");
    if (!workflowId) return;
    getWorkflow(workflowId).then(setWorkflow).catch(() => window.localStorage.removeItem("proseforge.current-workflow"));
  }, [authenticated]);
  useEffect(() => {
    if (workflow) window.localStorage.setItem("proseforge.current-workflow", workflow.id);
  }, [workflow]);
  if (authenticated === false) return <main className="auth-shell"><Login onLoggedIn={load} /></main>;
  if (authenticated === null) return <main className="auth-shell"><p>{t("connectionChecking")}…</p></main>;
  const view = route.view;
  const nav = (next: AppView, label: string) => <><button onClick={() => navigateRoute(project && next !== "projects" && next !== "settings" && next !== "usage" ? { view: next, projectId: project.id } : { view: next })} className={`nav ${view === next ? "active" : ""}`}>{label}</button>{next === "usage" && <button onClick={signOut} className="nav">{t("logout")}</button>}</>;
  return <div className="shell"><aside className="rail"><div className="brand">P<span>F</span></div><nav>{nav("projects", t("projects"))}{nav("studio", t("writingStudio"))}{nav("outline", t("outlineIntake"))}{nav("context", t("context"))}{nav("workflow", t("workflow"))}{nav("settings", t("settings"))}{nav("usage", "Usage")}</nav><div className="rail-bottom"><div className="language-switcher" aria-label="Language"><button className={language === "zh-CN" ? "selected" : ""} onClick={() => setLanguage("zh-CN")}>{t("languageChinese")}</button><span>/</span><button className={language === "en-US" ? "selected" : ""} onClick={() => setLanguage("en-US")}>{t("languageEnglish")}</button></div><span>{connection === "Online" ? t("apiOnline") : connection === "Offline" ? t("apiOffline") : t("connectionChecking")}</span></div></aside><main className="main"><header><div><p className="eyebrow">{t("currentProject")}</p><h1>{project?.title ?? t("projects")}</h1></div>{usageQuery.data && <TokenMeter actual={usageQuery.data.actual.total_tokens} estimated={usageQuery.data.estimated.total_tokens} cost={usageQuery.data.actual.cost_usd} />}{project && <button className="ghost" onClick={() => navigateRoute({ view: "projects" })}>{t("allProjects")}</button>}</header>{view === "projects" && <Projects projects={projects} onOpen={item => { setProject(item); window.localStorage.setItem("proseforge.current-project", item.id); navigateRoute({ view: "studio", projectId: item.id }); }} onCreated={item => { void queryClient.invalidateQueries({ queryKey: ["projects"] }); setProject(item); window.localStorage.setItem("proseforge.current-project", item.id); navigateRoute({ view: "outline", projectId: item.id }); }} />}{project && view === "studio" && <><Studio project={project} /><ProjectVersionHistory project={project} /></>}{project && view === "outline" && <OutlineView project={project} onWorkflow={item => { setWorkflow(item); navigateRoute({ view: "workflow", projectId: project.id }); }} />}{project && view === "context" && <ContextView project={project} />}{project && view === "workflow" && <WorkflowView project={project} workflow={workflow} onWorkflow={setWorkflow} />}{view === "settings" && <SettingsView />}{view === "usage" && <UsagePage projectId={project?.id} />}</main><aside className="inspector"><section><h3>{t("projectStatus")}</h3><p>{project ? t("readyToContinue") : t("noProjects")}</p><small>{t("dockerSaved")}</small></section><section><h3>{t("workflow")}</h3><p>{workflow ? workflow.status : t("notStarted")}</p><button className="link" onClick={() => project && navigateRoute({ view: "workflow", projectId: project.id })}>{t("openWorkflow")}</button></section></aside></div>;
}

