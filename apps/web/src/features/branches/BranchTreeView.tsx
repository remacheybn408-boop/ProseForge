import { SealBadge } from "../../components/ink/Ink";
import type { BranchInfo } from "../../lib/api/client";

export function BranchTreeView({ branches, activeBranchId, showArchived, onSelect, onCompare, onToggleArchived }: {
  branches: BranchInfo[];
  activeBranchId?: string;
  showArchived?: boolean;
  onSelect?: (branchId: string) => void;
  onCompare?: (branchId: string) => void;
  onToggleArchived?: () => void;
}) {
  const byId = new Map(branches.map(branch => [branch.id, branch]));
  return <section className="branch-tree" aria-label="Branch tree">
    <h4>Branches</h4>
    {onToggleArchived && <button type="button" className="branch-tree-toggle-archived" aria-pressed={Boolean(showArchived)} onClick={onToggleArchived}>显示已归档 / Show archived</button>}
    <ul>
      {branches.map(branch => {
        const parent = branch.parent_branch_id ? byId.get(branch.parent_branch_id) : undefined;
        const archived = branch.status === "ARCHIVED";
        return <li key={branch.id} className={`branch-tree-item${branch.id === activeBranchId ? " active" : ""}${archived ? " archived" : ""}`}>
          <button type="button" className="branch-name" disabled={!onSelect} aria-current={branch.id === activeBranchId} onClick={() => onSelect?.(branch.id)}>
            {branch.name}
            {parent && <span className="branch-parent-edge"> from {parent.name}</span>}
          </button>
          {archived && <SealBadge aria-label="Archived">档</SealBadge>}
          {onCompare && branch.id !== activeBranchId && <button type="button" className="branch-compare-trigger" onClick={() => onCompare(branch.id)}>Compare</button>}
        </li>;
      })}
    </ul>
  </section>;
}
