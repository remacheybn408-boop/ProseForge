import type { KeyboardEvent } from "react";

export type ProposalAction = "approve" | "reject";
export type ProposalGuardStatus = "clear" | "blocked" | "pending";

function isTextEntryTarget(target: EventTarget | null) {
  return target instanceof HTMLElement && Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
}

export function ProposalActions({ guardStatus, guardReason, onAction }: {
  guardStatus: ProposalGuardStatus;
  guardReason?: string;
  onAction: (action: ProposalAction) => void;
}) {
  const approveBlocked = guardStatus === "blocked";
  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || isTextEntryTarget(event.target)) return;
    const action = event.key.toLowerCase() === "a" ? "approve" : event.key.toLowerCase() === "r" ? "reject" : undefined;
    if (!action || (action === "approve" && approveBlocked)) return;
    event.preventDefault();
    onAction(action);
  };

  return <section aria-label="Proposal actions" tabIndex={0} onKeyDown={handleKeyDown}>
    {approveBlocked && <p role="alert">Approval blocked: {guardReason ?? "A guard check has not passed."}</p>}
    <button type="button" disabled={approveBlocked} onClick={() => onAction("approve")}>Approve proposal (A)</button>
    <button type="button" onClick={() => onAction("reject")}>Reject proposal (R)</button>
  </section>;
}
