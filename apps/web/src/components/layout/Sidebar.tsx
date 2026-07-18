import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useState } from "react";
import { createConversation } from "../../lib/api/client";

type ProjectView = "studio" | "outline" | "context" | "workflow" | "agents" | "usage";

function projectFromPath(pathname: string): string | undefined {
  return pathname.match(/^\/projects\/([^/]+)/)?.[1];
}

export function Sidebar() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: state => state.location.pathname });
  const projectId = projectFromPath(pathname) ?? window.localStorage.getItem("proseforge.current-project") ?? undefined;
  const [openingChat, setOpeningChat] = useState(false);

  const goProjectView = (view: ProjectView) => {
    if (!projectId) return;
    void navigate({ to: `/projects/$projectId/${view}`, params: { projectId } });
  };
  const openChat = async () => {
    if (!projectId || openingChat) return;
    setOpeningChat(true);
    try {
      const conversation = await createConversation(projectId);
      await navigate({ to: "/projects/$projectId/chat/$conversationId/$branchId", params: { projectId, conversationId: conversation.id, branchId: conversation.branch_id } });
    } catch { /* the current page remains available */ } finally { setOpeningChat(false); }
  };

  const projectItem = (label: string, view: ProjectView) => {
    const active = projectId ? pathname.startsWith(`/projects/${projectId}/${view}`) : false;
    return <button key={view} type="button" className={active ? "active" : ""} onClick={() => goProjectView(view)}>{label}</button>;
  };

  return <aside className="workspace-sidebar" aria-label="Workspace navigation">
    <div className="brand">P<span>F</span></div>
    <nav>
      <button type="button" className={pathname === "/projects" ? "active" : ""} onClick={() => void navigate({ to: "/projects" })}>Projects</button>
      {projectId && projectItem("Writing Studio", "studio")}
      {projectId && <button type="button" className={pathname.includes("/chat/") ? "active" : ""} onClick={() => void openChat()} disabled={openingChat}>{openingChat ? "Opening…" : "Companion chat"}</button>}
      {projectId && projectItem("Outline intake", "outline")}
      {projectId && projectItem("Context", "context")}
      {projectId && projectItem("Workflow", "workflow")}
      {projectId && projectItem("Agent Swarm", "agents")}
      {projectId && projectItem("Usage", "usage")}
      <button type="button" className={pathname.startsWith("/settings") ? "active" : ""} onClick={() => void navigate({ to: "/settings/models" })}>Settings</button>
    </nav>
  </aside>;
}
