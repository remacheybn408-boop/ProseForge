import { useEffect, useMemo, useState, type DragEvent } from "react";
import {
  addEdge,
  Background,
  ConnectionLineType,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

export const WORKFLOW_NODE_KINDS = ["intake", "plan", "write", "review", "rewrite", "export"] as const;
export type WorkflowNodeKind = (typeof WORKFLOW_NODE_KINDS)[number];
export type WorkflowNodeStatus = "pending" | "running" | "done" | "failed" | "blocked";
export type WorkflowNodeData = {
  kind: WorkflowNodeKind;
  label: string;
  summary?: string;
  status?: WorkflowNodeStatus;
  params?: Record<string, string>;
};
export type CanvasNode = Node<WorkflowNodeData, "workflow">;
export type CanvasEdge = Edge;

const statusLabel: Record<WorkflowNodeStatus, string> = {
  pending: "待命",
  running: "运行中",
  done: "已完成",
  failed: "失败",
  blocked: "阻塞",
};

function WorkflowNodeCard({ data }: NodeProps<CanvasNode>) {
  const status = data.status ?? "pending";
  return <div style={{ width: 190, display: "grid", gap: 7, padding: "12px 14px", border: "1px solid var(--ink-faint)", borderRadius: "var(--radius-sm)", background: "var(--paper-raised)", color: "var(--ink)", boxShadow: "var(--shadow-raise)" }}>
    <Handle type="target" position={Position.Top} style={{ background: "var(--ink-mid)", border: "1px solid var(--paper)" }} />
    <div style={{ display: "flex", alignItems: "start", justifyContent: "space-between", gap: 8 }}>
      <strong style={{ fontFamily: "var(--font-seal)", fontWeight: 500 }}>{data.label}</strong>
      <span aria-label={`状态：${statusLabel[status]}`} title={statusLabel[status]} style={{ display: "grid", placeItems: "center", minWidth: 25, minHeight: 25, padding: "0 4px", border: "1px solid var(--ink-light)", color: status === "failed" || status === "blocked" ? "var(--cinnabar)" : "var(--ink-mid)", background: "var(--paper)", font: "12px/1 var(--font-seal)" }}>{statusLabel[status]}</span>
    </div>
    <small style={{ color: "var(--ink-mid)", font: "11px/1.45 var(--font-ui)" }}>{data.summary?.slice(0, 30) || `${data.kind} 节点`}</small>
    <Handle type="source" position={Position.Bottom} style={{ background: "var(--ink-mid)", border: "1px solid var(--paper)" }} />
  </div>;
}

const nodeTypes = { workflow: WorkflowNodeCard };
const edgeStyle = { stroke: "var(--ink-mid)", strokeWidth: 1.5 };

export function connectionCreatesCycle(edges: CanvasEdge[], source: string, target: string) {
  if (source === target) return true;
  const seen = new Set<string>();
  const visit = (nodeId: string): boolean => {
    if (nodeId === source) return true;
    if (seen.has(nodeId)) return false;
    seen.add(nodeId);
    return edges.filter(edge => edge.source === nodeId).some(edge => visit(edge.target));
  };
  return visit(target);
}

export function WorkflowCanvas({ initialNodes = [], initialEdges = [], focusNodeId, readOnly = false, onChange }: {
  initialNodes?: CanvasNode[];
  initialEdges?: CanvasEdge[];
  focusNodeId?: string;
  readOnly?: boolean;
  onChange?: (nodes: CanvasNode[], edges: CanvasEdge[]) => void;
}) {
  const [nodes, setNodes] = useState<CanvasNode[]>(initialNodes);
  const [edges, setEdges] = useState<CanvasEdge[]>(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [notice, setNotice] = useState("");
  const [flow, setFlow] = useState<ReactFlowInstance<CanvasNode, CanvasEdge>>();

  useEffect(() => { setNodes(initialNodes); }, [initialNodes]);
  useEffect(() => { setEdges(initialEdges); }, [initialEdges]);
  useEffect(() => { onChange?.(nodes, edges); }, [nodes, edges, onChange]);
  useEffect(() => { if (focusNodeId && nodes.some(node => node.id === focusNodeId)) setSelectedNodeId(focusNodeId); }, [focusNodeId, nodes]);

  const selectedNode = nodes.find(node => node.id === selectedNodeId);
  const updateNode = (patch: Partial<WorkflowNodeData>) => setNodes(current => current.map(node => node.id === selectedNodeId ? { ...node, data: { ...node.data, ...patch } } : node));
  const connect = (connection: Connection) => {
    if (readOnly || !connection.source || !connection.target) return;
    if (connectionCreatesCycle(edges, connection.source, connection.target)) { setNotice("连接会形成回环，未保存。"); return; }
    setEdges(current => addEdge({ ...connection, type: "bezier", style: edgeStyle, markerEnd: { type: MarkerType.ArrowClosed, color: "var(--ink-mid)" } }, current));
    setNotice("");
  };
  const dropNode = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (readOnly || !flow) return;
    const kind = event.dataTransfer.getData("application/proseforge-workflow") as WorkflowNodeKind;
    if (!WORKFLOW_NODE_KINDS.includes(kind)) return;
    const position = flow.screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const id = `${kind}-${Date.now()}`;
    setNodes(current => [...current, { id, type: "workflow", position, data: { kind, label: kind, summary: `${kind} 节点`, status: "pending", params: {} } }]);
  };
  const deleteNode = () => {
    if (!selectedNode || readOnly || !window.confirm(`删除“${selectedNode.data.label}”及其连接？`)) return;
    setNodes(current => current.filter(node => node.id !== selectedNode.id));
    setEdges(current => current.filter(edge => edge.source !== selectedNode.id && edge.target !== selectedNode.id));
    setSelectedNodeId(undefined);
  };
  const palette = useMemo(() => WORKFLOW_NODE_KINDS.map(kind => <button key={kind} type="button" draggable={!readOnly} onDragStart={event => event.dataTransfer.setData("application/proseforge-workflow", kind)} disabled={readOnly} style={{ border: "1px solid var(--ink-faint)", background: "var(--paper-raised)", color: "var(--ink-mid)", padding: "6px 9px", borderRadius: "var(--radius-sm)", cursor: readOnly ? "not-allowed" : "grab", font: "12px var(--font-ui)" }}>{kind}</button>), [readOnly]);

  return <section aria-label="Workflow canvas" style={{ display: "grid", gridTemplateColumns: selectedNode ? "minmax(0, 1fr) 250px" : "1fr", gap: 16 }}>
    <div style={{ display: "grid", gap: 10 }}>
      <div aria-label="节点库" style={{ display: "flex", flexWrap: "wrap", gap: 7, alignItems: "center" }}><span style={{ color: "var(--ink-mid)", font: "12px var(--font-seal)" }}>节点库</span>{palette}{readOnly && <span style={{ color: "var(--cinnabar)", fontSize: 12 }}>运行态：只读</span>}</div>
      {notice && <p role="status" style={{ margin: 0, color: "var(--cinnabar)", fontSize: 12 }}>{notice}</p>}
      <div onDragOver={event => event.preventDefault()} onDrop={dropNode} style={{ height: 560, border: "1px solid var(--ink-faint)", background: "var(--paper)" }}>
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onInit={setFlow} onConnect={connect} onNodeClick={(_, node) => setSelectedNodeId(node.id)} onNodesChange={changes => { if (!readOnly) setNodes(current => changes.reduce<CanvasNode[]>((items, change) => change.type === "position" && change.position ? items.map(item => item.id === change.id ? { ...item, position: change.position! } : item) : change.type === "remove" ? items.filter(item => item.id !== change.id) : items, current)); }} onEdgesChange={changes => { if (!readOnly) setEdges(current => changes.reduce<CanvasEdge[]>((items, change) => change.type === "remove" ? items.filter(item => item.id !== change.id) : items, current)); }} nodesDraggable={!readOnly} nodesConnectable={!readOnly} edgesReconnectable={!readOnly} deleteKeyCode={null} connectionLineType={ConnectionLineType.Bezier} defaultEdgeOptions={{ type: "bezier", style: edgeStyle, markerEnd: { type: MarkerType.ArrowClosed, color: "var(--ink-mid)" } }} fitView>
          <Background gap={24} size={1} color="var(--ink-faint)" />
          <Controls showInteractive={!readOnly} />
        </ReactFlow>
      </div>
    </div>
    {selectedNode && <aside aria-label="Node editor" style={{ display: "grid", alignContent: "start", gap: 12, padding: 14, border: "1px solid var(--ink-faint)", background: "var(--paper-raised)" }}>
      <strong style={{ fontFamily: "var(--font-seal)", fontWeight: 500 }}>节点参数</strong>
      <label style={{ display: "grid", gap: 4, color: "var(--ink-mid)", fontSize: 12 }}>标题<input aria-label="节点标题" value={selectedNode.data.label} disabled={readOnly} onChange={event => updateNode({ label: event.target.value })} style={{ border: "1px solid var(--ink-faint)", background: "var(--paper)", color: "var(--ink)", padding: 7 }} /></label>
      <label style={{ display: "grid", gap: 4, color: "var(--ink-mid)", fontSize: 12 }}>摘要（最多 30 字）<textarea aria-label="节点摘要" value={selectedNode.data.summary ?? ""} maxLength={30} disabled={readOnly} onChange={event => updateNode({ summary: event.target.value })} style={{ minHeight: 80, border: "1px solid var(--ink-faint)", background: "var(--paper)", color: "var(--ink)", padding: 7, resize: "vertical" }} /></label>
      <span className="status-stamp">{statusLabel[selectedNode.data.status ?? "pending"]}</span>
      {!readOnly && <button type="button" onClick={deleteNode} style={{ border: "1px solid var(--cinnabar)", background: "transparent", color: "var(--cinnabar)", padding: "6px 9px", cursor: "pointer" }}>删除节点</button>}
    </aside>}
  </section>;
}
