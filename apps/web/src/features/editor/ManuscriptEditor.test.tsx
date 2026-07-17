import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ManuscriptEditor } from "./ManuscriptEditor";

describe("ManuscriptEditor", () => {
  it("returns a selection-aware proposal without mutating the document", () => {
    const onProposal = vi.fn();
    render(<ManuscriptEditor initialContent="Mira enters the room." onProposal={onProposal} />);
    const editor = screen.getByLabelText("Manuscript") as HTMLTextAreaElement;
    editor.setSelectionRange(0, 4); fireEvent.select(editor);
    fireEvent.click(screen.getByRole("button", { name: "rewrite" }));
    expect(onProposal.mock.calls[0][0].selected_text).toBe("Mira");
    expect(editor.value).toBe("Mira enters the room.");
  });
});
