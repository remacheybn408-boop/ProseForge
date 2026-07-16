import { useState } from "react";
import { createProject, type Project } from "../../lib/api/client";
import { useLanguage } from "../../lib/i18n";

export function Projects({ projects, onOpen, onCreated }: { projects: Project[]; onOpen: (project: Project) => void; onCreated: (project: Project) => void }) {
  const { t } = useLanguage();
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const create = async () => {
    try {
      const project = await createProject({ title, slug: slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") });
      onCreated(project);
      setCreating(false);
      setTitle("");
      setSlug("");
    } catch {
      // The form remains available for correction.
    }
  };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">{t("yourWorkspaces")}</p><h2>{t("projects")}</h2><p>{t("chooseProject")}</p></div><div className="detail-list">{projects.map(project => <div className="detail-card" key={project.id}><div><strong>{project.title}</strong><span>{project.genre || t("writingProject")} · {project.status}</span></div><button onClick={() => onOpen(project)}>{t("open")}</button></div>)}{projects.length === 0 && <p className="empty">{t("noProjects")}</p>}</div>{creating ? <div className="settings-form"><label>{t("projectTitle")}<input value={title} onChange={event => setTitle(event.target.value)} placeholder={t("projectTitlePlaceholder")} /></label><label>{t("urlSlug")}<input value={slug} onChange={event => setSlug(event.target.value)} placeholder={t("urlSlugPlaceholder")} /></label><div className="workflow-actions"><button className="primary" onClick={create} disabled={!title}>{t("createProject")}</button><button onClick={() => setCreating(false)}>{t("cancel")}</button></div></div> : <button className="primary create-button" onClick={() => setCreating(true)}>{t("newProject")}</button>}</section>;
}
