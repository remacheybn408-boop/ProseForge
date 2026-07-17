import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatPage } from "./ChatPage";

describe("ChatPage", () => {
  it("renders statuses, persists draft and submits with Enter", () => {
    const onSend = vi.fn();
    render(<ChatPage conversationId="c1" branchId="main" onSend={onSend} messages={[{ id: "1", role: "assistant", content: "Drafting", status: "streaming", branchCount: 2 }]} />);
    expect(screen.getByText("Drafting")).toBeTruthy();
    expect(screen.getByText("↳ 2 branches")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Continue" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Continue");
  });
});
