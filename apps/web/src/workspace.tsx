import { useEffect, useState } from "react";
import "./styles/tokens.css";
import "./styles/views.css";
import {
  deleteCredential, getWorkflow, listCredentials, listModelProfiles, logout, probeProvider, saveCredential, saveModelProfile, type Credential, type ModelProfile, type Project, type Workflow,
} from "./lib/api/client";
import { ProjectVersionHistory } from "./features/VersionHistory";
import { ContextView } from "./features/context/ContextView";
import { useLanguage } from "./lib/i18n";
import { useHealthQuery, useModelsQuery, useProjectsQuery, useProvidersQuery, useUsageSummaryQuery, queryClient } from "./app/query";
import { navigateRoute, useAppRoute, type AppView } from "./app/router";
import { ApiError } from "./lib/api/client";
import { TokenMeter } from "./features/usage/TokenMeter";
import { UsagePage } from "./features/usage/UsagePage";
import { removeCredential, upsertCredential } from "./features/providers/credentialState";
import { Login } from "./features/auth/Login";
import { Projects } from "./features/projects/Projects";
import { OutlineView } from "./features/outlines/OutlineView";
import { Studio } from "./features/editor/Studio";
import { WorkflowView } from "./features/workflows/WorkflowView";

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
  const save = async () => { if (!apiKey.trim()) return setMessage(t("apiKeyHelp")); try { const record = await saveCredential({ provider, api_key: apiKey, base_url: baseUrl || undefined }); setCredentials(current => upsertCredential(current, record)); setApiKey(""); setMessage(t("configured")); } catch { setMessage(t("genericError")); } };
  const removeConfigured = async (item: Credential) => { if (!window.confirm(`${t("removeCredentialConfirm")} ${item.provider}?`)) return; try { await deleteCredential(item.id); setCredentials(current => removeCredential(current, item.id)); setMessage(t("credentialRemoved")); } catch { setMessage(t("genericError")); } };
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
    <section className="settings-section"><div className="settings-section-heading"><h3>{t("configured")}</h3><p>{t("secretsNeverPrefilled")}</p></div><div className="settings-list">{credentials.length === 0 && <p className="empty">{t("notConnected")}</p>}{credentials.map(item => { const state = probeStates[item.id]; return <div className="settings-row" key={item.id}><div><strong>{item.provider}</strong><span>{item.masked_key}</span></div><span className={`connection-status ${state ?? "unknown"}`}>{state === "connected" ? t("connected") : state === "failed" ? t("checkFailed") : t("notConnected")}</span><button onClick={() => probe(item)}>{t("testConnection")}</button><button className="danger" aria-label={`${t("removeCredential")} ${item.provider}`} onClick={() => removeConfigured(item)}>{t("removeCredential")}</button></div>; })}</div></section>
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
  return <div className="shell"><aside className="rail"><div className="brand">P<span>F</span></div><nav>{nav("projects", t("projects"))}{nav("studio", t("writingStudio"))}{nav("outline", t("outlineIntake"))}{nav("context", t("context"))}{nav("workflow", t("workflow"))}{nav("settings", t("settings"))}{nav("usage", t("usage"))}</nav><div className="rail-bottom"><div className="language-switcher" aria-label="Language"><button className={language === "zh-CN" ? "selected" : ""} onClick={() => setLanguage("zh-CN")}>{t("languageChinese")}</button><span>/</span><button className={language === "en-US" ? "selected" : ""} onClick={() => setLanguage("en-US")}>{t("languageEnglish")}</button></div><span>{connection === "Online" ? t("apiOnline") : connection === "Offline" ? t("apiOffline") : t("connectionChecking")}</span></div></aside><main className="main"><header><div><p className="eyebrow">{t("currentProject")}</p><h1>{project?.title ?? t("projects")}</h1></div>{usageQuery.data && <TokenMeter actual={usageQuery.data.actual.total_tokens} estimated={usageQuery.data.estimated.total_tokens} cost={usageQuery.data.actual.cost_usd} />}{project && <button className="ghost" onClick={() => navigateRoute({ view: "projects" })}>{t("allProjects")}</button>}</header>{view === "projects" && <Projects projects={projects} onOpen={item => { setProject(item); window.localStorage.setItem("proseforge.current-project", item.id); navigateRoute({ view: "studio", projectId: item.id }); }} onCreated={item => { void queryClient.invalidateQueries({ queryKey: ["projects"] }); setProject(item); window.localStorage.setItem("proseforge.current-project", item.id); navigateRoute({ view: "outline", projectId: item.id }); }} />}{project && view === "studio" && <><Studio project={project} /><ProjectVersionHistory project={project} /></>}{project && view === "outline" && <OutlineView project={project} onWorkflow={item => { setWorkflow(item); navigateRoute({ view: "workflow", projectId: project.id }); }} />}{project && view === "context" && <ContextView project={project} />}{project && view === "workflow" && <WorkflowView project={project} workflow={workflow} onWorkflow={setWorkflow} />}{view === "settings" && <SettingsView />}{view === "usage" && <UsagePage projectId={project?.id} />}</main><aside className="inspector"><section><h3>{t("projectStatus")}</h3><p>{project ? t("readyToContinue") : t("noProjects")}</p><small>{t("dockerSaved")}</small></section><section><h3>{t("workflow")}</h3><p>{workflow ? workflow.status : t("notStarted")}</p><button className="link" onClick={() => project && navigateRoute({ view: "workflow", projectId: project.id })}>{t("openWorkflow")}</button></section></aside></div>;
}

