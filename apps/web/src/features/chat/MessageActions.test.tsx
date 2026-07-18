import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MessageActions } from "./MessageActions";
import type { ChatMessage } from "./chatTypes";

const userMessage: ChatMessage = { id: "u1", role: "user", content: "original question", status: "completed" };
const assistantMessage: ChatMessage = { id: "a2", role: "assistant", content: "second take", status: "completed" };

describe("MessageActions", () => {
  it("opens an inline editor from the edit button and submits the new content", () => {
    const onEdit = vi.fn();
    render(<MessageActions message={userMessage} onEdit={onEdit} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const editor = screen.getByLabelText("Edit message");
    expect((editor as HTMLTextAreaElement).value).toBe("original question");
    fireEvent.change(editor, { target: { value: "rewritten question" } });
    fireEvent.click(screen.getByRole("button", { name: "Save edit" }));
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledWith("rewritten question");
  });

  it("keeps the original content when the edit is cancelled", () => {
    const onEdit = vi.fn();
    render(<MessageActions message={userMessage} onEdit={onEdit} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Edit message"), { target: { value: "discarded" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onEdit).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Edit message")).toBeNull();
  });

  it("does not submit an empty edit", () => {
    const onEdit = vi.fn();
    render(<MessageActions message={userMessage} onEdit={onEdit} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Edit message"), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Save edit" }));
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("offers regenerate on assistant messages", () => {
    const onRegenerate = vi.fn();
    render(<MessageActions message={assistantMessage} onRegenerate={onRegenerate} />);
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(onRegenerate).toHaveBeenCalledTimes(1);
  });

  it("pages through candidates with the switcher", () => {
    const onSwitch = vi.fn();
    render(<MessageActions message={assistantMessage} candidateIndex={1} candidateCount={2} onSwitchCandidate={onSwitch} />);
    expect(screen.getByText("1/2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next candidate" }));
    expect(onSwitch).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByRole("button", { name: "Previous candidate" }));
    expect(onSwitch).toHaveBeenCalledWith(-1);
  });

  it("hides the candidate switcher when there is only one candidate", () => {
    render(<MessageActions message={assistantMessage} candidateIndex={1} candidateCount={1} onSwitchCandidate={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Next candidate" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Previous candidate" })).toBeNull();
  });
});
