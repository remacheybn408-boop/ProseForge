import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewFilters } from "./ReviewFilters";
import { ReviewPage } from "./ReviewPage";

describe("ReviewFilters", () => {
  it("filters by severity and jumps to supplied evidence", () => {
    const onSeverityChange = vi.fn();
    const onEvidenceJump = vi.fn();
    render(<ReviewFilters severity="all" onSeverityChange={onSeverityChange} evidence={[{ id: "e1", label: "Paragraph 3" }]} onEvidenceJump={onEvidenceJump} />);

    fireEvent.change(screen.getByLabelText("Severity"), { target: { value: "blocking" } });
    fireEvent.click(screen.getByRole("button", { name: "Jump to evidence: Paragraph 3" }));
    expect(onSeverityChange).toHaveBeenCalledWith("blocking");
    expect(onEvidenceJump).toHaveBeenCalledWith({ id: "e1", label: "Paragraph 3" });
  });
});

describe("ReviewPage", () => {
  it("shows only the selected finding severity and delegates evidence jumps", () => {
    const onEvidenceJump = vi.fn();
    render(<ReviewPage onEvidenceJump={onEvidenceJump} findings={[
      { id: "f1", severity: "blocking", title: "Continuity break", detail: "The timeline conflicts.", evidence: { id: "e1", label: "Paragraph 3" } },
      { id: "f2", severity: "nit", title: "Punctuation", detail: "Use an em dash." },
    ]} />);

    fireEvent.change(screen.getByLabelText("Severity"), { target: { value: "blocking" } });
    expect(screen.getByText("Continuity break")).toBeTruthy();
    expect(screen.queryByText("Punctuation")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "View evidence" }));
    expect(onEvidenceJump).toHaveBeenCalledWith({ id: "e1", label: "Paragraph 3" });
  });
});
