import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadDraft, saveDraft } from "../../lib/drafts";
import { ChatPage } from "./ChatPage";
import { useChatStore } from "./chatStore";
import type { ChatMessage } from "./chatTypes";

vi.mock("../../lib/drafts", () => ({
  loadDraft: vi.fn(() => Promise.resolve("")),
  saveDraft: vi.fn(() => Promise.resolve()),
}));

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function stubMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

const fixture: ChatMessage[] = [
  { id: "u1", role: "user", content: "Rewrite the opening", status: "completed" },
  { id: "a1", role: "assistant", content: "Drafting", status: "streaming", branchIndex: 2, branchCount: 3 },
  { id: "a2", role: "assistant", content: "Partial draft kept", status: "failed" },
];

beforeEach(() => {
  vi.clearAllMocks();
  useChatStore.setState({ inspectorOpen: false, commandPaletteOpen: false, streaming: false });
  stubMatchMedia(false);
});

describe("ChatPage", () => {
  it("renders user, assistant and failed message states", () => {
    const { container } = renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={fixture} />);
    expect(screen.getByText("Rewrite the opening")).toBeTruthy();
    expect(screen.getByText("Drafting")).toBeTruthy();
    expect(screen.getByText("Partial draft kept")).toBeTruthy();
    expect(container.querySelector(".chat-message-user")).toBeTruthy();
    expect(container.querySelector(".chat-message-assistant")).toBeTruthy();
    expect(screen.getAllByText("止").length).toBeGreaterThan(0);
  });

  it("submits the composer draft exactly once on Enter", () => {
    const onSend = vi.fn();
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={[]} onSend={onSend} />);
    const composer = screen.getByLabelText("Message");
    fireEvent.change(composer, { target: { value: "Continue" } });
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][0]).toBe("Continue");
  });

  it("keeps Shift+Enter as a newline instead of submitting", () => {
    const onSend = vi.fn();
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={[]} onSend={onSend} />);
    const composer = screen.getByLabelText("Message");
    fireEvent.change(composer, { target: { value: "Line one" } });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("marks the inspector as a drawer on narrow viewports", () => {
    stubMatchMedia(true);
    const { container } = renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={[]} />);
    expect(container.querySelector(".workspace-inspector.drawer")).toBeTruthy();
  });

  it("shows a stop control while a reply is streaming", () => {
    const onStop = vi.fn();
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={fixture} onStop={onStop} />);
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("keeps the generated partial when retrying a failed reply", () => {
    const onRetry = vi.fn();
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={fixture} onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledWith(expect.objectContaining({ id: "a2" }));
    expect(screen.getByText("Partial draft kept")).toBeTruthy();
  });

  it("shows the cinnabar streaming cursor only while streaming", () => {
    const { container } = renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={fixture} />);
    expect(container.querySelector(".chat-message-assistant.streaming .streaming-cursor")).toBeTruthy();
    const settled = renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={[{ id: "a9", role: "assistant", content: "Done", status: "completed" }]} />);
    expect(settled.container.querySelector(".streaming-cursor")).toBeNull();
  });

  it("shows the branch switcher counter text", () => {
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={fixture} />);
    expect(screen.getByText("‹ 2/3 ›")).toBeTruthy();
  });

  it("rejects attachments larger than 2MB with a notice", () => {
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={[]} />);
    const oversized = new File([new Uint8Array(2 * 1024 * 1024 + 1)], "big.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText("Attachment file"), { target: { files: [oversized] } });
    expect(screen.getByText(/2 ?MB limit/i)).toBeTruthy();
  });

  it("restores the composer draft from IndexedDB", async () => {
    vi.mocked(loadDraft).mockResolvedValueOnce("stored draft");
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={[]} />);
    expect(await screen.findByDisplayValue("stored draft")).toBeTruthy();
    expect(loadDraft).toHaveBeenCalledWith({ conversationId: "c1", branchId: "main", draftType: "chat" });
  });

  it("persists composer edits to IndexedDB under the chat draft key", async () => {
    renderWithQuery(<ChatPage conversationId="c1" branchId="main" messages={[]} />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Unsent thought" } });
    await vi.waitFor(() => {
      expect(saveDraft).toHaveBeenCalledWith({ conversationId: "c1", branchId: "main", draftType: "chat" }, "Unsent thought");
    });
  });
});
