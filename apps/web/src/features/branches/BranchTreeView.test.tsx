import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { BranchInfo } from "../../lib/api/client";
import { BranchTreeView } from "./BranchTreeView";

const branches: BranchInfo[] = [
  { id: "b1", conversation_id: "c1", name: "Main", parent_branch_id: null, forked_from_message_id: null, status: "ACTIVE", title: null },
  { id: "b2", conversation_id: "c1", name: "Edited message", parent_branch_id: "b1", forked_from_message_id: "u1", status: "ACTIVE", title: null },
  { id: "b3", conversation_id: "c1", name: "Old draft", parent_branch_id: "b1", forked_from_message_id: "u1", status: "ARCHIVED", title: null },
];

describe("BranchTreeView", () => {
  it("renders branches with their parent edges", () => {
    render(<BranchTreeView branches={branches} activeBranchId="b1" />);
    expect(screen.getByText("Main")).toBeTruthy();
    expect(screen.getByText("Edited message")).toBeTruthy();
    expect(screen.getAllByText(/from Main/).length).toBe(2);
  });

  it("marks archived branches with a badge", () => {
    render(<BranchTreeView branches={branches} activeBranchId="b1" />);
    const badge = screen.getByLabelText("Archived");
    expect(badge).toBeTruthy();
    const activeItems = screen.getAllByRole("listitem").filter(item => item.textContent?.includes("Main"));
    expect(activeItems[0].textContent).not.toContain("档");
  });

  it("marks the active branch and notifies selection", () => {
    const onSelect = vi.fn();
    render(<BranchTreeView branches={branches} activeBranchId="b1" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Edited message/ }));
    expect(onSelect).toHaveBeenCalledWith("b2");
  });

  it("offers compare against the active branch", () => {
    const onCompare = vi.fn();
    render(<BranchTreeView branches={branches} activeBranchId="b1" onCompare={onCompare} />);
    const compareButtons = screen.getAllByRole("button", { name: "Compare" });
    fireEvent.click(compareButtons[0]);
    expect(onCompare).toHaveBeenCalledWith("b2");
  });
});
