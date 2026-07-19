import { useCallback, useState } from "react";
import { WorkflowBudgetPanel } from "./WorkflowBudgetPanel";
import { WorkflowCanvas, type CanvasEdge, type CanvasNode } from "./WorkflowCanvas";
import { WorkflowRunTimeline, type WorkflowRunEvent } from "./WorkflowRunTimeline";
import { isWorkflowRunReadOnly } from "./workflowQueries";

export function WorkflowStudioPage({ nodes = [], edges = [], events = [], used = 0, limit = 1, runStatus = "DRAFT", onChange }: { nodes?: CanvasNode[]; edges?: CanvasEdge[]; events?: WorkflowRunEvent[]; used?: number; limit?: number; runStatus?: string; onChange?: (value: { nodes: CanvasNode[]; edges: CanvasEdge[] }) => void }) {
  const [focusNodeId, setFocusNodeId] = useState<string>();
  const readOnly = isWorkflowRunReadOnly(runStatus);
  // The canvas graph derives from props on every render so definition reloads
  // and live run-state updates reach the canvas; only user edits flow back up.
  const updateDefinition = useCallback((nextNodes: CanvasNode[], nextEdges: CanvasEdge[]) => { onChange?.({ nodes: nextNodes, edges: nextEdges }); }, [onChange]);
  return <section className="workflow-studio" style={{ display: "grid", gap: 20, color: "var(--ink)" }}>
    <header style={{ display: "flex", alignItems: "start", justifyContent: "space-between", gap: 16, borderBottom: "1px solid var(--ink-faint)", paddingBottom: 14 }}><div><p className="eyebrow">WORKFLOW STUDIO</p><h2 style={{ margin: 0, font: "28px var(--font-seal)", color: "var(--ink-strong)" }}>可恢复写作流程</h2></div><span className="status-stamp">{runStatus}</span></header>
    <WorkflowCanvas initialNodes={nodes} initialEdges={edges} focusNodeId={focusNodeId} readOnly={readOnly} onChange={updateDefinition} />
    <WorkflowBudgetPanel used={used} limit={limit} />
    <WorkflowRunTimeline events={events} onFocusNode={setFocusNodeId} />
  </section>;
}
