import type { WorkflowDefinition, WorkflowNodeState, WorkflowRunStreamEvent } from "../../lib/api/client";
import { WORKFLOW_NODE_KINDS, type CanvasEdge, type CanvasNode, type WorkflowNodeKind, type WorkflowNodeStatus } from "./WorkflowCanvas";
import type { WorkflowRunEvent } from "./WorkflowRunTimeline";

export const workflowKeys = {
  definitions: (projectId: string) => ["workflow-definitions", projectId] as const,
  run: (runId: string | undefined) => ["workflow-run-v2", runId] as const,
  v1Run: (workflowId: string | undefined) => ["workflows", workflowId] as const,
};

// Mirrors TERMINAL_STATUSES in proseforge/application/workflows/run_service.py.
const TERMINAL_RUN_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export function isTerminalWorkflowRun(status: string) {
  return TERMINAL_RUN_STATUSES.has(status.toUpperCase());
}

export function isWorkflowRunReadOnly(status: string) {
  return !["DRAFT", "IDLE", "PAUSED"].includes(status.toUpperCase());
}

// Backend node states (workflow_v2.WorkflowNodeStateModel.status) -> canvas status.
const NODE_STATUS_MAP: Record<string, WorkflowNodeStatus> = { PENDING: "pending", RUNNING: "running", COMPLETED: "done", FAILED: "failed", BLOCKED: "blocked" };

export function toCanvasNodeStatus(status: string): WorkflowNodeStatus {
  return NODE_STATUS_MAP[status.toUpperCase()] ?? "pending";
}

export function applyNodeStates(nodes: CanvasNode[], states: WorkflowNodeState[] | undefined): CanvasNode[] {
  if (!states?.length) return nodes;
  const byKey = new Map(states.map(state => [state.node_key, toCanvasNodeStatus(state.status)]));
  return nodes.map(node => {
    const status = byKey.get(node.id);
    return status ? { ...node, data: { ...node.data, status } } : node;
  });
}

export function mergeWorkflowEvents(current: WorkflowRunEvent[], incoming: WorkflowRunEvent[]) {
  const seen = new Set(current.map(event => event.id));
  return [...current, ...incoming.filter(event => !seen.has(event.id))];
}

const EVENT_LABELS: Record<string, string> = {
  "run.started": "流程启动",
  "run.paused": "流程暂停",
  "run.resumed": "流程继续",
  "run.cancelled": "流程取消",
  "run.retried": "流程重试",
  "run.budget_blocked": "预算阻塞",
  "run.recovering": "租约过期，恢复中",
  "run.recovered": "已重新排队",
};

export function toTimelineEvent(event: WorkflowRunStreamEvent): WorkflowRunEvent {
  const status = typeof event.data.status === "string" ? event.data.status : "";
  const nodeId = typeof event.data.node_key === "string" ? event.data.node_key : undefined;
  return { id: String(event.id), label: EVENT_LABELS[event.event] ?? event.event, status, nodeId };
}

/**
 * Canvas -> API mapping. The backend validator (definition_service.validate_definition)
 * reads `id` + `kind` on each node and `{source, target}` on each edge, so the React
 * Flow view model (`type: "workflow"`, `data.kind`) must be mapped before saving —
 * posting raw canvas nodes is rejected with 422 "unsupported node kind: workflow".
 * Extra keys (position, params) are stored verbatim by the backend and round-trip
 * back to the canvas; summaries are capped at 30 chars per the blueprint.
 */
export function toApiDefinition(nodes: CanvasNode[], edges: CanvasEdge[]): WorkflowDefinition["definition"] {
  return {
    nodes: nodes.map(node => ({
      id: node.id,
      kind: node.data.kind,
      title: node.data.label,
      summary: (node.data.summary ?? "").slice(0, 30),
      position: { x: Math.round(node.position.x), y: Math.round(node.position.y) },
      ...(node.data.params && Object.keys(node.data.params).length ? { params: node.data.params } : {}),
    })),
    edges: edges.map(edge => ({ source: edge.source, target: edge.target })),
  };
}

type ApiNode = { id: string; kind: WorkflowNodeKind; title?: string; summary?: string; position?: { x: number; y: number }; params?: Record<string, string> };

function parseApiNode(raw: Record<string, unknown>): ApiNode | null {
  if (typeof raw.id !== "string" || !raw.id) return null;
  if (typeof raw.kind !== "string" || !(WORKFLOW_NODE_KINDS as readonly string[]).includes(raw.kind)) return null;
  const position = raw.position as { x?: unknown; y?: unknown } | undefined;
  return {
    id: raw.id,
    kind: raw.kind as WorkflowNodeKind,
    title: typeof raw.title === "string" ? raw.title : undefined,
    summary: typeof raw.summary === "string" ? raw.summary : undefined,
    position: typeof position?.x === "number" && typeof position?.y === "number" ? { x: position.x, y: position.y } : undefined,
    params: raw.params && typeof raw.params === "object" ? raw.params as Record<string, string> : undefined,
  };
}

/**
 * API -> canvas mapping. Saved definitions carry no React Flow view model, so nodes
 * without a stored `position` get a deterministic layered layout: topological depth
 * (longest path from a source) is the column, first-seen order within a layer is the
 * row. Definitions are validated acyclic server-side, so the relaxation terminates.
 */
export function fromApiDefinition(definition: WorkflowDefinition["definition"]): { nodes: CanvasNode[]; edges: CanvasEdge[] } {
  const parsed = (Array.isArray(definition.nodes) ? definition.nodes : []).map(parseApiNode).filter((node): node is ApiNode => node !== null);
  const ids = new Set(parsed.map(node => node.id));
  const edges: CanvasEdge[] = (Array.isArray(definition.edges) ? definition.edges : [])
    .map(raw => ({ source: typeof raw.source === "string" ? raw.source : "", target: typeof raw.target === "string" ? raw.target : "" }))
    .filter(edge => edge.source && edge.target && edge.source !== edge.target && ids.has(edge.source) && ids.has(edge.target))
    .map(edge => ({ id: `${edge.source}-${edge.target}`, source: edge.source, target: edge.target }));
  const depth = new Map(parsed.map(node => [node.id, 0]));
  for (let pass = 0; pass < parsed.length; pass += 1) {
    for (const edge of edges) {
      const next = (depth.get(edge.source) ?? 0) + 1;
      if (next > (depth.get(edge.target) ?? 0)) depth.set(edge.target, next);
    }
  }
  const rowInLayer = new Map<number, number>();
  const nodes: CanvasNode[] = parsed.map(node => {
    const layer = depth.get(node.id) ?? 0;
    const row = rowInLayer.get(layer) ?? 0;
    rowInLayer.set(layer, row + 1);
    return {
      id: node.id,
      type: "workflow",
      position: node.position ?? { x: 30 + layer * 250, y: 60 + row * 150 },
      data: { kind: node.kind, label: node.title || node.kind, summary: node.summary ?? "", status: "pending", params: node.params ?? {} },
    };
  });
  return { nodes, edges };
}

/**
 * Structural equality used to break the canvas -> onChange -> props -> canvas sync
 * loop: when the graph did not actually change, the previous state object is kept
 * and React bails out of the re-render.
 */
export function canvasGraphEqual(a: { nodes: CanvasNode[]; edges: CanvasEdge[] }, b: { nodes: CanvasNode[]; edges: CanvasEdge[] }): boolean {
  if (a.nodes.length !== b.nodes.length || a.edges.length !== b.edges.length) return false;
  const edgeKeys = new Set(a.edges.map(edge => `${edge.source}->${edge.target}`));
  if (!b.edges.every(edge => edgeKeys.has(`${edge.source}->${edge.target}`))) return false;
  const byId = new Map(a.nodes.map(node => [node.id, node]));
  return b.nodes.every(node => {
    const other = byId.get(node.id);
    if (!other) return false;
    return other.data.kind === node.data.kind
      && other.data.label === node.data.label
      && (other.data.summary ?? "") === (node.data.summary ?? "")
      && (other.data.status ?? "pending") === (node.data.status ?? "pending")
      && other.position.x === node.position.x
      && other.position.y === node.position.y;
  });
}
