import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProposalActions } from "./ProposalActions";

describe("ProposalActions", () => {
  it("supports A/R shortcuts without taking input shortcuts", () => {
    const onAction = vi.fn();
    render(<ProposalActions guardStatus="clear" onAction={onAction} />);
    const region = screen.getByRole("region", { name: "Proposal actions" });
    fireEvent.keyDown(region, { key: "a" });
    fireEvent.keyDown(region, { key: "R" });
    const input = document.createElement("input");
    region.append(input);
    fireEvent.keyDown(input, { key: "a" });

    expect(onAction).toHaveBeenNthCalledWith(1, "approve");
    expect(onAction).toHaveBeenNthCalledWith(2, "reject");
    expect(onAction).toHaveBeenCalledTimes(2);
  });

  it("disables approval and explains a blocked guard while retaining rejection", () => {
    const onAction = vi.fn();
    render(<ProposalActions guardStatus="blocked" guardReason="Source chapter changed." onAction={onAction} />);

    expect((screen.getByRole("button", { name: "Approve proposal (A)" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("alert").textContent).toContain("Source chapter changed.");
    fireEvent.click(screen.getByRole("button", { name: "Reject proposal (R)" }));
    expect(onAction).toHaveBeenCalledWith("reject");
  });
});
