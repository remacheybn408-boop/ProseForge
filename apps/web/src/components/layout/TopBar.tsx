import { useRouterState } from "@tanstack/react-router";
import { useProjectsQuery } from "../../app/query";
import { useChatStore } from "../../features/chat/chatStore";

export function TopBar() {
  const pathname = useRouterState({ select: state => state.location.pathname });
  const projectId = pathname.match(/^\/projects\/([^/]+)/)?.[1];
  const projectsQuery = useProjectsQuery();
  const project = projectId ? projectsQuery.data?.find(item => item.id === projectId) : undefined;
  const toggleInspector = useChatStore(state => state.toggleInspector);
  return <header className="workspace-topbar">
    <div><p className="eyebrow">CURRENT PROJECT</p><strong>{project?.title ?? "ProseForge"}</strong></div>
    <button type="button" className="inspector-toggle" aria-label="Toggle inspector" onClick={toggleInspector}>
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" /></svg>
    </button>
  </header>;
}
