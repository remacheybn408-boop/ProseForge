import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FactEditor } from "./FactEditor";

describe("FactEditor", () => {
  it("saves character voice, triggers, and a budget as structured values", () => {
    const onSave = vi.fn();
    render(<FactEditor onSave={onSave} />);
    fireEvent.change(screen.getByLabelText("Fact key"), { target: { value: "Mira" } });
    fireEvent.change(screen.getByLabelText("Triggers"), { target: { value: "Mira, harbor" } });
    fireEvent.change(screen.getByLabelText("Voice register"), { target: { value: "formal" } });
    fireEvent.click(screen.getByRole("button", { name: "Save fact" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      kind: "character",
      key: "Mira",
      value: expect.objectContaining({ triggers: ["Mira", "harbor"], budget_tokens: expect.any(Number), voice: expect.objectContaining({ register: "formal" }) }),
    }));
  });
});
