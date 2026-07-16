import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../../lib/i18n";
import { ContextView } from "./ContextView";
import { listContext, listModelProfiles } from "../../lib/api/client";

vi.mock("../../lib/api/client", () => ({
  addContext: vi.fn(),
  listContext: vi.fn(),
  listModelProfiles: vi.fn(),
  updateContext: vi.fn(),
}));

const project = { id: "project-1", slug: "project", title: "Project", genre: "", style: "", language: "en-US", status: "ACTIVE" };

describe("ContextView", () => {
  afterEach(cleanup);

  beforeEach(() => {
    localStorage.setItem("proseforge.web.language", "en-US");
    vi.mocked(listModelProfiles).mockResolvedValue([]);
  });

  it("does not display a fixed context window while the model budget is loading", () => {
    vi.mocked(listContext).mockImplementation(() => new Promise(() => undefined));

    render(<LanguageProvider><ContextView project={project} /></LanguageProvider>);

    expect(screen.queryByText("128K available")).toBeNull();
  });

  it("renders the context window returned for the selected model", async () => {
    vi.mocked(listContext).mockResolvedValue({ items: [], used_tokens: 5000, context_window: 20000, available_tokens: 11000, system_reserved_tokens: 0, history_tokens: 0, output_reserve_tokens: 4000 });

    render(<LanguageProvider><ContextView project={project} /></LanguageProvider>);

    await waitFor(() => expect(screen.getByText("11K available")).toBeTruthy());
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("31");
  });
});
