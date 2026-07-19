import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import {
  controlWorkflow,
  controlWorkflowRun,
  createWorkflowDefinition,
  getWorkflow,
  getWorkflowRun,
  listWorkflowDefinitions,
  startWorkflowDefinition,
  subscribeWorkflowRunEvents,
  updateWorkflowDefinition,
  type Workflow,
} from "../../lib/api/client";
import type { CanvasEdge, CanvasNode } from "../../features/workflows/WorkflowCanvas";
import type { WorkflowRunEvent } from "../../features/workflows/WorkflowRunTimeline";
import {
  applyNodeStates,
  canvasGraphEqual,
  fromApiDefinition,
  isTerminalWorkflowRun,
  mergeWorkflowEvents,
  toApiDefinition,
  toTimelineEvent,
  workflowKeys,
} from "../../features/workflows/workflowQueries";
import { useProjectsQuery } from "../query";

const WorkflowStudioPage = lazy(() => import("../../features/workflows/WorkflowStudioPage").then(module => ({ default: module.WorkflowStudioPage })));

const starterNodes: CanvasNode[] = [
  { id: "intake", type: "workflow", position: { x: 30, y: 80 }, data: { kind: "intake", label: "素材接入" } },
  { id: "plan", type: "workflow", position: { x: 280, y: 80 }, data: { kind: "plan", label: "章节规划" } },
  { id: "write", type: "workflow", position: { x: 530, y: 80 }, data: { kind: "write", label: "正文生成" } },
  { id: "review", type: "workflow", position: { x: 780, y: 80 }, data: { kind: "review", label: "质量审稿" } },
  { id: "export", type: "workflow", position: { x: 1030, y: 80 }, data: { kind: "export", label: "发布导出" } },
];
const starterEdges: CanvasEdge[] = ["intake-plan", "plan-write", "write-review", "review-export"].map(key => { const [source, target] = key.split("-"); return { id: key, source, target }; });

export function WorkflowPage({ projectId, workflowId }: { projectId: string; workflowId?: string }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const project = useProjectsQuery().data?.find(item => item.id === projectId);
  const definitions = useQuery({ queryKey: workflowKeys.definitions(projectId), queryFn: () => listWorkflowDefinitions(projectId) });
  const [startedRunId, setStartedRunId] = useState<string>();
  const runId = workflowId ?? startedRunId;
  const v2Run = useQuery({ queryKey: workflowKeys.run(runId), queryFn: () => getWorkflowRun(runId!), enabled: Boolean(runId), retry: false });
  const v1Run = useQuery({ queryKey: workflowKeys.v1Run(workflowId), queryFn: () => getWorkflow(workflowId!), enabled: Boolean(workflowId) && v2Run.isError, retry: false });
  const [message, setMessage] = useState("设计可恢复流程，保存后即可运行。");
  const [graph, setGraph] = useState<{ nodes: CanvasNode[]; edges: CanvasEdge[] }>({ nodes: starterNodes, edges: starterEdges });
  const [events, setEvents] = useState<WorkflowRunEvent[]>([]);
  const [liveStatus, setLiveStatus] = useState<string>();

  const selectedDefinition = definitions.data?.[0];
  const snapshot = v2Run.data;
  const current: Workflow | undefined = snapshot?.run ?? v1Run.data;
  const runStatus = liveStatus ?? current?.status ?? "DRAFT";

  // Load the latest saved definition onto the canvas once per definition id;
  // later canvas edits stay local until the user saves a new revision.
  const loadedDefinitionRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!selectedDefinition || loadedDefinitionRef.current === selectedDefinition.id) return;
    loadedDefinitionRef.current = selectedDefinition.id;
    setGraph(fromApiDefinition(selectedDefinition.definition));
  }, [selectedDefinition]);

  // Snapshot -> live tail: fetch {run, nodes, event_cursor}, then resume the SSE
  // stream from the cursor. The server ends the stream once the run is terminal;
  // any other close is treated as a disconnect and resumed from the last event id.
  useEffect(() => {
    setEvents([]);
    setLiveStatus(undefined);
    if (!runId || v2Run.isError) return;
    let closed = false;
    let stop: (() => void) | undefined;
    let resumeTimer: number | undefined;
    let cursor = 0;
    let terminal = false;
    const open = () => {
      stop = subscribeWorkflowRunEvents(runId, {
        lastEventId: cursor,
        onEvent: event => {
          cursor = Math.max(cursor, event.id);
          setEvents(current => mergeWorkflowEvents(current, [toTimelineEvent(event)]));
          const status = typeof event.data.status === "string" ? event.data.status : undefined;
          if (status) {
            setLiveStatus(status);
            if (isTerminalWorkflowRun(status)) terminal = true;
          }
          // Node states are not embedded in run events; refresh the snapshot so
          // canvas node stamps and the budget panel follow the durable state.
          void queryClient.invalidateQueries({ queryKey: workflowKeys.run(runId) });
        },
        onClose: () => {
          if (closed || terminal) return;
          void queryClient.fetchQuery({ queryKey: workflowKeys.run(runId), queryFn: () => getWorkflowRun(runId), retry: false }).then(latest => {
            if (closed) return;
            setLiveStatus(latest.run.status);
            if (!isTerminalWorkflowRun(latest.run.status)) resumeTimer = window.setTimeout(open, 2000);
          }).catch(() => undefined);
        },
      });
    };
    void queryClient.fetchQuery({ queryKey: workflowKeys.run(runId), queryFn: () => getWorkflowRun(runId), retry: false }).then(latest => {
      if (closed) return;
      cursor = latest.event_cursor;
      setLiveStatus(latest.run.status);
      if (!isTerminalWorkflowRun(latest.run.status)) open();
    }).catch(() => undefined);
    return () => {
      closed = true;
      stop?.();
      if (resumeTimer !== undefined) window.clearTimeout(resumeTimer);
    };
  }, [runId, v2Run.isError, queryClient]);

  const nodes = useMemo(() => applyNodeStates(graph.nodes, snapshot?.nodes), [graph.nodes, snapshot?.nodes]);
  const edges = graph.edges;

  const handleCanvasChange = useCallback((value: { nodes: CanvasNode[]; edges: CanvasEdge[] }) => {
    setGraph(current => (canvasGraphEqual(current, value) ? current : value));
  }, []);

  const save = useMutation({
    mutationFn: () => {
      const definition = toApiDefinition(graph.nodes, graph.edges);
      return selectedDefinition
        ? updateWorkflowDefinition(selectedDefinition.id, { definition })
        : createWorkflowDefinition(projectId, { name: "Professional writing", definition });
    },
    onSuccess: async saved => {
      loadedDefinitionRef.current = saved.id;
      setMessage("流程定义已保存。");
      await queryClient.invalidateQueries({ queryKey: workflowKeys.definitions(projectId) });
    },
    onError: () => setMessage("流程定义未保存，请检查节点连接。"),
  });
  const start = useMutation({
    mutationFn: async () => {
      const definition = selectedDefinition ?? await createWorkflowDefinition(projectId, { name: `Professional writing ${Date.now()}`, definition: toApiDefinition(graph.nodes, graph.edges) });
      return startWorkflowDefinition(definition.id, { token_limit: 120000, cost_limit: 20 });
    },
    onSuccess: async result => {
      setMessage(`流程已启动：${result.run.id}`);
      setStartedRunId(result.run.id);
      queryClient.setQueryData(workflowKeys.run(result.run.id), { run: result.run, nodes: result.nodes, event_cursor: 0 });
      await queryClient.invalidateQueries({ queryKey: workflowKeys.run(result.run.id) });
      await navigate({ to: "/projects/$projectId/workflows/$workflowId", params: { projectId, workflowId: result.run.id } }).catch(() => undefined);
    },
    onError: () => setMessage("流程启动失败。"),
  });
  const action = async (name: "pause" | "resume" | "cancel" | "retry") => {
    if (!current) return;
    try {
      if (snapshot) await controlWorkflowRun(current.id, name);
      else await controlWorkflow(current.id, name);
      setMessage(`流程状态已更新：${name}`);
      await queryClient.invalidateQueries({ queryKey: snapshot ? workflowKeys.run(current.id) : workflowKeys.v1Run(current.id) });
    } catch { setMessage("当前状态不允许执行该操作。"); }
  };

  return <section className="detail-view">
    <div className="detail-heading"><p className="eyebrow">WORKFLOW STUDIO</p><h2>{project?.title ?? "可恢复写作流程"}</h2><p aria-live="polite">{message}</p></div>
    <Suspense fallback={<p className="form-message">正在加载流程画布…</p>}>
      <WorkflowStudioPage nodes={nodes} edges={edges} events={events} runStatus={runStatus} used={snapshot?.nodes.reduce((sum, node) => sum + node.used_tokens, 0) ?? 0} limit={snapshot?.run.token_limit ?? 120000} onChange={handleCanvasChange} />
    </Suspense>
    <div className="workflow-actions">
      {!current && <><button onClick={() => save.mutate()} disabled={save.isPending}>{selectedDefinition ? "保存新版本" : "保存流程"}</button><button className="primary" onClick={() => start.mutate()} disabled={start.isPending}>启动流程</button></>}
      {current && <><button onClick={() => action("pause")}>暂停</button><button onClick={() => action("resume")}>继续</button><button onClick={() => action("cancel")}>取消</button><button onClick={() => action("retry")}>重试</button></>}
    </div>
  </section>;
}
