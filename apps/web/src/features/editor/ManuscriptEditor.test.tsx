import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ManuscriptEditor } from "./ManuscriptEditor";

describe("ManuscriptEditor", () => {
  it("uses the plain-text adapter when requested and returns an action without mutating the document", async () => {
    const onProposal = vi.fn();
    render(<ManuscriptEditor forcePlain initialContent="Mira enters the room." baseVersionId="version-1" onProposal={onProposal} />);
    const editor = screen.getByLabelText("Manuscript") as HTMLTextAreaElement;
    editor.setSelectionRange(0, 4); fireEvent.select(editor);
    fireEvent.click(screen.getByRole("button", { name: "rewrite" }));
    await waitFor(() => expect(onProposal).toHaveBeenCalledTimes(1));
    expect(onProposal.mock.calls[0][0]).toMatchObject({ action: "rewrite", from: 0, to: 4, selectedText: "Mira", content: "Mira enters the room.", baseVersionId: "version-1" });
    expect(editor.value).toBe("Mira enters the room.");
  });

  it("renders a real Tiptap editing surface by default", () => {
    render(<ManuscriptEditor initialContent="Mira enters the room." />);
    expect(screen.getByTestId("tiptap-manuscript").getAttribute("contenteditable")).toBe("true");
    expect(screen.queryByRole("textbox", { name: "Manuscript" })?.tagName).not.toBe("TEXTAREA");
  });
});
