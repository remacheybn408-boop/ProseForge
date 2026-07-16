import { useEffect, useState } from "react";
import "./styles/tokens.css";
import "./styles/views.css";
import { getWorkflow, logout, type Project, type Workflow } from "./lib/api/client";
import { ProjectVersionHistory } from "./features/VersionHistory";
import { ContextView } from "./features/context/ContextView";
import { useLanguage } from "./lib/i18n";
import { useHealthQuery, useProjectsQuery, useUsageSummaryQuery, queryClient } from "./app/query";
import { navigateRoute, useAppRoute, type AppView } from "./app/router";
import { ApiError } from "./lib/api/client";
import { TokenMeter } from "./features/usage/TokenMeter";
import { UsagePage } from "./features/usage/UsagePage";
import { Login } from "./features/auth/Login";
import { Projects } from "./features/projects/Projects";
import { OutlineView } from "./features/outlines/OutlineView";
import { Studio } from "./features/editor/Studio";
import { WorkflowView } from "./features/workflows/WorkflowView";
import { SettingsView } from "./features/providers/SettingsView";

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

