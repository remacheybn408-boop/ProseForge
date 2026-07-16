import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider, languageStorageKey } from "../../lib/i18n";
import { Studio } from "./Studio";

vi.mock("../../lib/api/client", () => ({
  activateChapterVersion: vi.fn(),
  createConversation: vi.fn(),
  forkConversation: vi.fn(),
  getChapterDiff: vi.fn(),
  listChapters: vi.fn(),
  listChapterVersions: vi.fn(),
  listMessages: vi.fn(),
  listModelProfiles: vi.fn(),
  requestExport: vi.fn(),
  saveChapterVersion: vi.fn(),
  sendMessage: vi.fn(),
  subscribeConversationEvents: vi.fn(),
}));

vi.mock("../../lib/drafts", () => ({
  loadDraft: vi.fn().mockResolvedValue(""),
  saveDraft: vi.fn().mockResolvedValue(undefined),
}));

const project = { id: "project-1", slug: "project", title: "Project", genre: "", style: "", language: "en-US", status: "ACTIVE" };

describe("Studio assistant disclosure", () => {
  afterEach(cleanup);

  beforeEach(async () => {
    localStorage.setItem(languageStorageKey, "en-US");
    const client = await import("../../lib/api/client");
    vi.mocked(client.listChapters).mockResolvedValue([]);
    vi.mocked(client.listModelProfiles).mockResolvedValue([]);
  });

  it("keeps a keyboard-accessible assistant entry while its content is collapsed", () => {
    render(<LanguageProvider><Studio project={project} /></LanguageProvider>);

    const toggle = screen.getByRole("button", { name: "Collapse assistant" });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("Writing companion")).toBeTruthy();

    fireEvent.click(toggle);

    const expand = screen.getByRole("button", { name: "Expand assistant" });
    expect(expand.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("Writing companion")).toBeTruthy();
  });
});
