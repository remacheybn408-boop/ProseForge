import { render, screen, within } from "@testing-library/react";
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

  it("disables controls that cannot transition a completed workflow", () => {
    const { container } = render(<WorkflowStatus status="COMPLETED" onAction={() => undefined} />);
    for (const name of ["Pause", "Resume", "Cancel", "Retry"]) {
      expect((within(container).getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
  });
});
