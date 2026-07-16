import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowStatus } from "./WorkflowStatus";
import { LanguageProvider, languageStorageKey } from "../../lib/i18n";

describe("WorkflowStatus", () => {
  it("shows durable status controls", () => {
    const onAction = vi.fn();
    localStorage.setItem(languageStorageKey, "en-US");
    render(<LanguageProvider><WorkflowStatus status="RUNNING" onAction={onAction} /></LanguageProvider>);
    screen.getByRole("button", { name: "Pause" }).click();
    expect(onAction).toHaveBeenCalledWith("pause");
    expect(screen.getByText("RUNNING")).toBeTruthy();
  });

  it("disables controls that cannot transition a completed workflow", () => {
    localStorage.setItem(languageStorageKey, "en-US");
    const { container } = render(<LanguageProvider><WorkflowStatus status="COMPLETED" onAction={() => undefined} /></LanguageProvider>);
    for (const name of ["Pause", "Resume", "Cancel", "Retry"]) {
      expect((within(container).getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
  });
});
