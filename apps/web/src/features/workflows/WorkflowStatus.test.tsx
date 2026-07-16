import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowStatus } from "./WorkflowStatus";

describe("WorkflowStatus", () => {
  it("shows durable status controls", () => {
    const onAction = vi.fn();
    render(<WorkflowStatus status="RUNNING" onAction={onAction} />);
    screen.getByRole("button", { name: "Pause" }).click();
    expect(onAction).toHaveBeenCalledWith("pause");
    expect(screen.getByText("RUNNING")).toBeTruthy();
  });
});
