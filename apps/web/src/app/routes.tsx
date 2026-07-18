import { createRootRoute, createRoute, Outlet, redirect, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Sidebar } from "../components/layout/Sidebar";
import { TopBar } from "../components/layout/TopBar";
import { WorkspaceSplit } from "../components/layout/WorkspaceSplit";
import { ChatPage, type CompareViewData } from "../features/chat/ChatPage";
import { branchKeys, branchTreeKeys, messageKeys, useBranches, useBranchTree, useChatConversation, useCompareBranches, useEditMessage, useRegenerate } from "../features/chat/chatQueries";
import { toChatMessage, type ChatMessage } from "../features/chat/chatTypes";
import { UsagePage } from "../features/usage/UsagePage";
import { ApiError, type BranchCompareResult, type BranchTreeMessage } from "../lib/api/client";
import { AgentsPage } from "./pages/AgentsPage";
import { ContextPage } from "./pages/ContextPage";
import { OutlinePage } from "./pages/OutlinePage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReviewPage } from "./pages/ReviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StudioPage } from "./pages/StudioPage";
import { WorkflowPage } from "./pages/WorkflowPage";

function WorkspaceShell() {
  return <div className="workspace-shell"><Sidebar /><TopBar /><Outlet /></div>;
}

function page(children: ReactNode) {
  return <WorkspaceSplit>{children}</WorkspaceSplit>;
}

const rootRoute = createRootRoute({ component: WorkspaceShell });

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => { throw redirect({ to: "/projects" }); },
});

const projectsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects",
  component: () => page(<ProjectsPage />),
});

const studioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/studio",
  component: StudioRouteComponent,
});
function StudioRouteComponent() {
  const { projectId } = studioRoute.useParams();
  return page(<StudioPage projectId={projectId} />);
}

const manuscriptRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/manuscript/$chapterId",
  component: ManuscriptRouteComponent,
});
function ManuscriptRouteComponent() {
  const { projectId, chapterId } = manuscriptRoute.useParams();
  return page(<StudioPage projectId={projectId} chapterId={chapterId} />);
}

const outlineRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/outline",
  component: OutlineRouteComponent,
});
function OutlineRouteComponent() {
  const { projectId } = outlineRoute.useParams();
  return page(<OutlinePage projectId={projectId} />);
}

const contextRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/context",
  component: ContextRouteComponent,
});
function ContextRouteComponent() {
  const { projectId } = contextRoute.useParams();
  return page(<ContextPage projectId={projectId} />);
}

const workflowRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/workflow",
  component: WorkflowRouteComponent,
});
function WorkflowRouteComponent() {
  const { projectId } = workflowRoute.useParams();
  return page(<WorkflowPage projectId={projectId} />);
}

const workflowDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/workflows/$workflowId",
  component: WorkflowDetailRouteComponent,
});
function WorkflowDetailRouteComponent() {
  const { projectId, workflowId } = workflowDetailRoute.useParams();
  return page(<WorkflowPage projectId={projectId} workflowId={workflowId} />);
}

const agentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/agents",
  component: AgentsRouteComponent,
});
function AgentsRouteComponent() {
  const { projectId } = agentsRoute.useParams();
  return page(<AgentsPage projectId={projectId} />);
}

const usageRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/usage",
  component: UsageRouteComponent,
});
function UsageRouteComponent() {
  const { projectId } = usageRoute.useParams();
  return page(<UsagePage projectId={projectId} />);
}

const reviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/review/$reportId",
  component: ReviewRouteComponent,
});
function ReviewRouteComponent() {
  const { reportId } = reviewRoute.useParams();
  return page(<ReviewPage reportId={reportId} />);
}

const settingsModelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/models",
  component: () => page(<SettingsPage />),
});

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/chat/$conversationId/$branchId",
  component: ChatRouteComponent,
});
function ChatRouteComponent() {
  const { projectId, conversationId, branchId } = chatRoute.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { messagesQuery, send, stop, retry, fork } = useChatConversation(conversationId, branchId);
  const branchesQuery = useBranches(conversationId);
  const treeQuery = useBranchTree(conversationId, branchId);
  const editMutation = useEditMessage();
  const regenerateMutation = useRegenerate();
  const [notice, setNotice] = useState("");
  const [compareWith, setCompareWith] = useState<string | null>(null);
  const compareQuery = useCompareBranches(conversationId, branchId, compareWith);
  const goToBranch = async (nextBranchId: string) => {
    await navigate({ to: "/projects/$projectId/chat/$conversationId/$branchId", params: { projectId, conversationId, branchId: nextBranchId } });
  };
  const forkBranch = async () => {
    const branch = await fork();
    if (!branch) return;
    setNotice("Alternative branch created.");
    await goToBranch(branch.id);
  };
  const editMessage = async (message: ChatMessage, content: string) => {
    try {
      const result = await editMutation.mutateAsync({ conversationId, messageId: message.id, content });
      setNotice("Edit saved as a new branch.");
      await queryClient.invalidateQueries({ queryKey: branchKeys(conversationId) });
      await goToBranch(result.branch_id);
    } catch {
      setNotice("Could not save the edit.");
    }
  };
  const regenerate = async (message: ChatMessage) => {
    try {
      await regenerateMutation.mutateAsync({ conversationId, messageId: message.id });
      setNotice("Regenerating a new candidate.");
      void queryClient.invalidateQueries({ queryKey: messageKeys(conversationId, branchId) });
      void queryClient.invalidateQueries({ queryKey: branchTreeKeys(conversationId, branchId) });
    } catch {
      setNotice("Could not regenerate this reply.");
    }
  };
  const messages = (messagesQuery.data ?? []).map(toChatMessage);
  const branches = branchesQuery.data;
  const compare = buildCompareView(branches, branchId, compareWith, compareQuery.data, treeQuery.data);
  const error = messagesQuery.error instanceof ApiError ? `HTTP ${messagesQuery.error.status}` : (messagesQuery.isError ? "CHAT_LOAD_FAILED" : undefined);
  return <ChatPage
    conversationId={conversationId}
    branchId={branchId}
    messages={messages}
    notice={notice}
    error={error}
    branches={branches}
    treeMessages={treeQuery.data}
    compare={compare}
    onSend={(text, options) => void send(text, options)}
    onStop={stop}
    onRetry={message => retry(message.id)}
    onFork={() => void forkBranch()}
    onReload={() => void messagesQuery.refetch()}
    onSelectBranch={nextBranchId => { if (nextBranchId !== branchId) void goToBranch(nextBranchId); }}
    onCompareBranch={setCompareWith}
    onEditMessage={(message, content) => void editMessage(message, content)}
    onRegenerateMessage={message => void regenerate(message)}
  />;
}

function buildCompareView(branches: { id: string; name: string }[] | undefined, branchId: string, compareWith: string | null, result: BranchCompareResult | undefined, tree: BranchTreeMessage[] | undefined): CompareViewData | undefined {
  if (!result || !compareWith || !tree) return undefined;
  const leftLabel = branches?.find(branch => branch.id === branchId)?.name ?? "Current";
  const rightLabel = branches?.find(branch => branch.id === compareWith)?.name ?? "Compared";
  return {
    leftLabel,
    rightLabel,
    result,
    prefix: tree.slice(0, result.common_count).map(message => ({ id: message.id, role: message.role, content: message.content })),
  };
}

export const routeTree = rootRoute.addChildren([
  indexRoute,
  projectsRoute,
  studioRoute,
  chatRoute,
  manuscriptRoute,
  outlineRoute,
  contextRoute,
  workflowRoute,
  workflowDetailRoute,
  agentsRoute,
  usageRoute,
  reviewRoute,
  settingsModelsRoute,
]);
