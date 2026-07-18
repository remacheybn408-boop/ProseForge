import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { createProject, type Project } from "../../lib/api/client";
import { useProjectsQuery } from "../query";

export function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectsQuery = useProjectsQuery();
  const projects = projectsQuery.data ?? [];
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const open = (project: Project) => {
    window.localStorage.setItem("proseforge.current-project", project.id);
    void navigate({ to: "/projects/$projectId/studio", params: { projectId: project.id } });
  };
  const create = async () => {
    try {
      const project = await createProject({ title, slug: slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      window.localStorage.setItem("proseforge.current-project", project.id);
      setCreating(false);
      setTitle("");
      setSlug("");
      await navigate({ to: "/projects/$projectId/outline", params: { projectId: project.id } });
    } catch { /* the form remains available for correction */ }
  };
  return <section className="detail-view"><div className="detail-heading"><p className="eyebrow">YOUR WORKSPACES</p><h2>Projects</h2><p>Choose a project to continue writing, or start a new one from an outline.</p></div><div className="detail-list">{projects.map(project => <div className="detail-card" key={project.id}><div><strong>{project.title}</strong><span>{project.genre || "Writing project"} · {project.status}</span></div><button onClick={() => open(project)}>Open</button></div>)}{projects.length === 0 && <p className="empty">No projects yet. Create your first writing space below.</p>}</div>{creating ? <div className="settings-form"><label>Project title<input value={title} onChange={event => setTitle(event.target.value)} placeholder="The Moonlit Archive" /></label><label>URL slug<input value={slug} onChange={event => setSlug(event.target.value)} placeholder="moonlit-archive" /></label><div className="workflow-actions"><button className="primary" onClick={create} disabled={!title}>Create project</button><button onClick={() => setCreating(false)}>Cancel</button></div></div> : <button className="primary create-button" onClick={() => setCreating(true)}>＋ New project</button>}</section>;
}
