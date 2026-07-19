import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProposalDiff } from "./ProposalDiff";

describe("ProposalDiff", () => {
  it("renders inline additions/removals and exposes individual hunk selection", () => {
    const onSelectionChange = vi.fn();
    render(<ProposalDiff hunks={[{ id: "h1", label: "Opening", before: "Mira walks", after: "Mira runs" }]} selectedHunkIds={[]} onSelectionChange={onSelectionChange} />);

    expect(screen.getByText("Mira walks").tagName).toBe("DEL");
    expect(screen.getByText("Mira runs").tagName).toBe("INS");
    fireEvent.click(screen.getByRole("checkbox", { name: "Opening" }));
    expect(onSelectionChange).toHaveBeenCalledWith("h1", true);
  });
});
